"""朗读服务 — 逐段合成播放、进度事件、断点续读。

播放方式：逐段合成为 MP3 → pygame 顺序播放，段间按解析出的停顿 sleep。
不引入 pydub/ffmpeg；导出时按顺序拼接 MP3 字节（best-effort）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from butler.core.constants import DATA_DIR
from butler.core.reading.script_parser import Segment, parse
from butler.core.reading.tts_edge import EdgeTTSEngine
from butler.core.reading.voices import (
    DEFAULT_FEMALE,
    DEFAULT_MALE,
    DEFAULT_NARRATOR,
    assign_voices,
    load_role_map,
)

logger = logging.getLogger("ReadingService")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    book_hash TEXT PRIMARY KEY,
    file_path TEXT,
    segment INTEGER DEFAULT 0,
    offset INTEGER DEFAULT 0,
    profile TEXT,
    updated_at TEXT
);
"""


class ReadingService:
    """一本（或一篇）文本的朗读会话。"""

    def __init__(self, tts: EdgeTTSEngine | None = None, db_path: Path | None = None):
        self.tts = tts or EdgeTTSEngine()
        self.db_path = (
            Path(db_path) if db_path else DATA_DIR / "system_data" / "reading_sessions.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.book: dict[str, Any] | None = None
        self._index = 0
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread = None
        self._native_engine = None

    # ── 初始化 ──────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _cfg(key: str, default: Any) -> Any:
        try:
            from package.core_utils.config_loader import config_loader

            value = config_loader.get(key, default)
            return default if value is None else value
        except Exception:
            return default

    # ── 打开文本 ────────────────────────────────────────────

    def open(
        self,
        source: str | Path,
        role_map_path: str | Path | None = None,
        default_rate: float | None = None,
        ai: bool = False,
    ) -> dict[str, Any]:
        """打开任意文字来源：本地文件、网页 URL、'-'（标准输入）。"""
        from butler.core.reading.sources import load_source

        text, display = load_source(str(source))
        return self._load(text, display, role_map_path, default_rate, ai)

    def open_text(
        self,
        text: str,
        name: str = "剪贴板",
        role_map_path: str | Path | None = None,
        default_rate: float | None = None,
        ai: bool = False,
    ) -> dict[str, Any]:
        """直接朗读一段文本（剪贴板/选中内容等）。"""
        return self._load(text, name, role_map_path, default_rate, ai)

    def _load(
        self,
        text: str,
        display: str,
        role_map_path: str | Path | None = None,
        default_rate: float | None = None,
        ai: bool = False,
    ) -> dict[str, Any]:
        rate = float(
            default_rate
            if default_rate is not None
            else self._cfg("reading.default_rate", 1.0)
        )
        segments = parse(text, default_rate=rate)

        characters: list[str] = []
        for segment in segments:
            if segment.kind == "dialogue" and segment.speaker not in characters:
                characters.append(segment.speaker)

        narrator_voice = self._cfg("reading.narrator_voice", DEFAULT_NARRATOR)
        voices = assign_voices(
            characters,
            female_voices=self._cfg("reading.female_voices", DEFAULT_FEMALE),
            male_voices=self._cfg("reading.male_voices", DEFAULT_MALE),
            narrator="旁白",
            role_map=load_role_map(role_map_path),
        )
        voices["旁白"] = narrator_voice
        ai_tokens = 0
        if ai and characters:
            from butler.core.reading.ai_analysis import analyze_characters

            try:
                gender_map, ai_tokens = analyze_characters(text)
                if gender_map:
                    voices = assign_voices(
                        characters,
                        female_voices=self._cfg("reading.female_voices", DEFAULT_FEMALE),
                        male_voices=self._cfg("reading.male_voices", DEFAULT_MALE),
                        narrator="旁白",
                        role_map=load_role_map(role_map_path),
                        gender_map=gender_map,
                    )
                    voices["旁白"] = narrator_voice
            except Exception as exc:
                logger.warning("LLM 角色分析失败，回退本地规则: %s", exc)

        book_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.book = {
            "path": display,
            "hash": book_hash,
            "text": text,
            "segments": segments,
            "voices": voices,
            "characters": characters,
        }
        self._index = 0
        return {
            "path": display,
            "segments": len(segments),
            "characters": characters,
            "voices": voices,
            "resume_index": self._load_progress(),
            "ai_tokens": ai_tokens,
        }

    def _require_book(self) -> dict[str, Any]:
        if not self.book:
            raise RuntimeError("请先打开文本")
        return self.book

    # ── 断点 ────────────────────────────────────────────────

    def _load_progress(self) -> int:
        if not self.book:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT segment FROM sessions WHERE book_hash = ?",
                (self.book["hash"],),
            ).fetchone()
        return int(row[0]) if row else 0

    def _save_progress(self, index: int, profile: str = "") -> None:
        if not self.book:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (book_hash, file_path, segment, offset, profile, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(book_hash) DO UPDATE SET
                    segment=excluded.segment,
                    updated_at=excluded.updated_at
                """,
                (
                    self.book["hash"],
                    self.book["path"],
                    int(index),
                    json.dumps(self.book["voices"], ensure_ascii=False)[:2000],
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

    # ── 播放控制 ────────────────────────────────────────────

    def seek(self, index: int) -> int:
        segments = self._require_book()["segments"]
        self._index = max(0, min(int(index), max(0, len(segments) - 1)))
        return self._index

    def pause(self) -> None:
        self._pause.set()

    def resume(self) -> None:
        self._pause.clear()

    def stop(self) -> None:
        self._stop.set()
        self._pause.clear()
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def play_blocking(
        self,
        start: int | None = None,
        dry_run: bool = False,
        out_path: str | Path | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        book = self._require_book()
        segments: list[Segment] = book["segments"]
        if not segments:
            return {"played": 0, "next_index": 0, "output": None}

        if start is not None:
            index = self.seek(start)
        elif resume:
            index = self.seek(self._load_progress())
        else:
            index = 0

        self._stop.clear()
        self._pause.clear()
        buffer = bytearray()
        played = 0

        for segment in segments[index:]:
            if self._stop.is_set():
                break
            while self._pause.is_set() and not self._stop.is_set():
                time.sleep(0.1)
            if self._stop.is_set():
                break

            self._index = segment.index
            voice = book["voices"].get(segment.speaker, DEFAULT_NARRATOR)
            audio = self._synthesize(segment, voice)
            self._emit_position(segment, voice)

            if dry_run:
                if audio:
                    buffer.extend(audio)
                played += 1
            else:
                if segment.pause_before_ms:
                    time.sleep(segment.pause_before_ms / 1000)
                if audio:
                    self._play_bytes(audio)
                else:
                    self._native_speak(segment.text)
                played += 1

            self._save_progress(segment.index + 1)

        output = None
        if dry_run and out_path:
            output = Path(out_path).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(bytes(buffer))

        return {"played": played, "next_index": self._index + 1, "output": str(output) if output else None}

    def start_background(self, start: int | None = None, resume: bool = False):
        if self._thread and self._thread.is_alive():
            raise RuntimeError("朗读仍在进行中")
        self._thread = threading.Thread(
            target=self.play_blocking,
            kwargs={"start": start, "resume": resume},
            daemon=True,
        )
        self._thread.start()
        return self._thread

    # ── 合成与播放 ──────────────────────────────────────────

    def _synthesize(self, segment: Segment, voice: str) -> bytes | None:
        backend = str(self._cfg("reading.backend", "edge"))
        if backend == "native":
            return None
        return self.tts.speak(segment.text, voice=voice, rate=segment.rate)

    def _play_bytes(self, audio: bytes) -> None:
        import tempfile

        if not audio:
            return
        path = None
        try:
            import pygame

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fh:
                fh.write(audio)
                path = fh.name
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and not self._stop.is_set():
                time.sleep(0.1)
        except Exception as exc:
            logger.warning("音频播放失败，改用文本节奏模拟: %s", exc)
            time.sleep(min(6.0, max(1.0, len(audio) / 8000)))
        finally:
            if path and os.path.exists(path):
                os.unlink(path)

    def _native_speak(self, text: str) -> None:
        try:
            from butler.core.voice_service import _get_native_tts_engine, _native_tts_speak

            if self._native_engine is None:
                self._native_engine = _get_native_tts_engine()
            _native_tts_speak(self._native_engine, text)
        except Exception as exc:
            logger.warning("原生语音兜底失败: %s", exc)

    def _emit_position(self, segment: Segment, voice: str) -> None:
        payload = {
            "index": segment.index,
            "speaker": segment.speaker,
            "text": segment.text,
            "voice": voice,
            "kind": segment.kind,
            "total": len(self._require_book()["segments"]),
            "path": self._require_book()["path"],
        }
        try:
            from butler.core.event_bus import event_bus

            event_bus.emit("reading.position", payload)
        except Exception:
            pass

    # ── 状态 ────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        if not self.book:
            return {"open": False}
        running = bool(self._thread and self._thread.is_alive())
        return {
            "open": True,
            "path": self.book["path"],
            "segments": len(self.book["segments"]),
            "index": self._index,
            "playing": running and not self._pause.is_set(),
            "paused": running and self._pause.is_set(),
            "characters": self.book["characters"],
            "voices": self.book["voices"],
        }
