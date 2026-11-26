"""edge-tts 朗读引擎 — 免费微软神经音色，支持多音色与语速调节。

不消耗 LLM token；需要联网。不可用时由调用方回退到系统原生 pyttsx3。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from butler.core.voice_service import VoiceEngine

logger = logging.getLogger("EdgeTTS")


def _run_coroutine(coro):
    """在同步上下文中运行协程（兼容已有事件循环的情况）。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _runner():
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 - 需跨线程传递
            error["value"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "value" in error:
        raise error["value"]
    return result.get("value")


class EdgeTTSEngine(VoiceEngine):
    """基于 edge-tts 的语音合成引擎。"""

    name = "edge"
    display_name = "Edge TTS (神经音色)"
    category = "online"
    requires_install = True
    requires_api_key = False

    def __init__(self) -> None:
        self._available: bool | None = None
        self._voices_cache: list[dict[str, Any]] | None = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                import edge_tts  # noqa: F401

                self._available = True
            except ImportError:
                logger.info("edge-tts 未安装，朗读将回退到系统原生语音")
                self._available = False
        return self._available

    @staticmethod
    def _rate_str(rate: float) -> str:
        clamped = max(0.5, min(2.0, float(rate or 1.0)))
        return f"{int(round((clamped - 1) * 100)):+d}%"

    @staticmethod
    def _volume_str(volume: float) -> str:
        clamped = max(0.0, min(1.0, float(volume if volume is not None else 1.0)))
        return f"{int(round(clamped * 100 - 100)):+d}%"

    async def _stream(self, text: str, voice: str, rate: str, volume: str,
                      pitch: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(
            text, voice, rate=rate, volume=volume, pitch=pitch
        )
        audio = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                audio.extend(chunk.get("data", b""))
        return bytes(audio)

    def speak(
        self,
        text: str,
        voice: str | None = None,
        rate: float = 1.0,
        pitch_hz: int = 0,
        volume: float = 1.0,
    ) -> bytes | None:
        """合成语音，返回 MP3 字节；不可用或失败返回 None。"""
        if not text.strip() or not self.is_available():
            return None
        voice = voice or "zh-CN-XiaoxiaoNeural"
        try:
            audio = _run_coroutine(
                self._stream(
                    text,
                    voice,
                    self._rate_str(rate),
                    self._volume_str(volume),
                    f"{int(pitch_hz):+d}Hz",
                )
            )
            return audio or None
        except Exception as exc:  # 网络/服务异常 → 交给上层降级
            logger.warning("edge-tts 合成失败: %s", exc)
            return None

    async def _list_voices_async(self) -> list[dict[str, Any]]:
        import edge_tts

        return await edge_tts.list_voices()

    def list_voices(self, chinese_only: bool = True) -> list[dict[str, Any]]:
        """列出可用音色；离线时返回空列表。"""
        if self._voices_cache is not None:
            voices = self._voices_cache
        else:
            if not self.is_available():
                return []
            try:
                voices = _run_coroutine(self._list_voices_async()) or []
                self._voices_cache = voices
            except Exception as exc:
                logger.warning("获取 edge-tts 音色列表失败: %s", exc)
                return []
        if chinese_only:
            voices = [v for v in voices if str(v.get("ShortName", "")).startswith("zh-CN")]
        return voices
