"""翻译缓存：LRU + JSON 持久化。"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional


class TranslationCache:
    """LRU 缓存，自动持久化到 JSON 文件。"""

    def __init__(self, cache_file: str, max_size: int = 2000):
        self.cache_file = Path(cache_file)
        self.max_size = max_size
        self._data: "OrderedDict[str, dict]" = OrderedDict()
        self._load()

    @staticmethod
    def _key(text: str, to: str) -> str:
        return f"{text[:120]}|{len(text)}|{to}"

    def get(self, text: str, to: str) -> Optional[str]:
        key = self._key(text, to)
        entry = self._data.get(key)
        if entry is None:
            return None
        self._data.move_to_end(key)
        return entry["translated"]

    def set(self, text: str, to: str, translated: str, provider: str = "") -> None:
        key = self._key(text, to)
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self.max_size:
            self._data.popitem(last=False)
        self._data[key] = {
            "translated": translated,
            "provider": provider,
            "ts": time.time(),
        }

    def batch_lookup(self, texts, to: str):
        hits = {}
        misses = {}
        for idx, text in enumerate(texts):
            val = self.get(text, to)
            if val is not None:
                hits[idx] = val
            else:
                misses[idx] = text
        return hits, misses

    def batch_set(self, texts, to: str, translated_list, provider: str = "") -> None:
        for text, translated in zip(texts, translated_list):
            self.set(text, to, translated, provider)

    def clear(self) -> None:
        self._data.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()

    @property
    def size(self) -> int:
        return len(self._data)

    def persist(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_file.open("w", encoding="utf-8") as f:
                json.dump(dict(self._data), f, ensure_ascii=False)
        except OSError:
            pass

    def _load(self) -> None:
        try:
            if self.cache_file.exists():
                with self.cache_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        self._data[k] = v
        except (OSError, json.JSONDecodeError):
            pass
