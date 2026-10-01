"""翻译历史与收藏。"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional


class HistoryEntry:
    def __init__(
        self,
        original: str,
        translated: str,
        from_lang: str = "auto",
        to_lang: str = "zh-CN",
        provider: str = "",
        favorite: bool = False,
        ts: Optional[float] = None,
    ):
        self.original = original
        self.translated = translated
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.provider = provider
        self.favorite = favorite
        self.ts = ts if ts is not None else time.time()

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(**{k: data[k] for k in data if k in cls.__init__.__code__.co_varnames})


class TranslationHistory:
    """翻译历史，支持收藏与导出，JSON 持久化。"""

    def __init__(self, history_file: str, max_entries: int = 1000):
        self.history_file = Path(history_file)
        self.max_entries = max_entries
        self._entries: List[HistoryEntry] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if self.history_file.exists():
                with self.history_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._entries = [HistoryEntry.from_dict(d) for d in data]
        except (OSError, json.JSONDecodeError):
            self._entries = []

    def _save(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with self.history_file.open("w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in self._entries], f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def record(self, original: str, translated: str, from_lang: str = "auto",
               to_lang: str = "zh-CN", provider: str = "") -> HistoryEntry:
        entry = HistoryEntry(original, translated, from_lang, to_lang, provider)
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]
            self._save()
        return entry

    def all(self, limit: Optional[int] = None) -> List[HistoryEntry]:
        with self._lock:
            entries = list(reversed(self._entries))
        return entries[:limit] if limit else entries

    def favorites(self) -> List[HistoryEntry]:
        return [e for e in self.all() if e.favorite]

    def toggle_favorite(self, index: int) -> bool:
        """按倒序索引切换收藏状态，返回新状态。"""
        with self._lock:
            entries = list(reversed(self._entries))
            if 0 <= index < len(entries):
                entries[index].favorite = not entries[index].favorite
                self._save()
                return entries[index].favorite
        return False

    def clear(self) -> None:
        with self._lock:
            self._entries = [e for e in self._entries if e.favorite]
            self._save()

    def export_json(self, path: str) -> None:
        with self._lock:
            data = [e.to_dict() for e in self._entries]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def size(self) -> int:
        return len(self._entries)
