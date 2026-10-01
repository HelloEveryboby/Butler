"""术语表：自定义专有名词的固定译法。"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional


class Glossary:
    """术语表，JSON 持久化，线程安全。"""

    def __init__(self, glossary_file: str):
        self.glossary_file = Path(glossary_file)
        self._terms: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if self.glossary_file.exists():
                with self.glossary_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._terms = {str(k): str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError):
            self._terms = {}

    def _save(self) -> None:
        try:
            self.glossary_file.parent.mkdir(parents=True, exist_ok=True)
            with self.glossary_file.open("w", encoding="utf-8") as f:
                json.dump(self._terms, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add(self, source: str, target: str) -> None:
        with self._lock:
            self._terms[source.strip()] = target.strip()
            self._save()

    def remove(self, source: str) -> bool:
        with self._lock:
            if source in self._terms:
                del self._terms[source]
                self._save()
                return True
            return False

    def get(self, source: str) -> Optional[str]:
        return self._terms.get(source)

    def all(self) -> Dict[str, str]:
        return dict(self._terms)

    def clear(self) -> None:
        with self._lock:
            self._terms.clear()
            self._save()

    def as_prompt_block(self) -> str:
        """将术语表格式化为提示词片段，注入到翻译 system prompt。"""
        if not self._terms:
            return ""
        lines = ["术语表（遇到以下词汇请使用固定译法）："]
        for src, tgt in self._terms.items():
            lines.append(f"- {src} → {tgt}")
        return "\n".join(lines)

    def replace_in_text(self, text: str) -> str:
        """在原文中先做术语替换（可选，主要用于不支持 prompt 的免费源）。"""
        result = text
        for src, tgt in self._terms.items():
            result = result.replace(src, tgt)
        return result

    @property
    def size(self) -> int:
        return len(self._terms)
