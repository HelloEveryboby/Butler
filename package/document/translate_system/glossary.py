"""术语表：自定义专有名词的固定译法。

升级为「进 prompt + 事后校验」双保险：
1. `render_prompt_rules()` 把术语强制约束写进翻译 system prompt（事前）；
2. `apply(text)` 在译文产出后再做一次兜底替换（事后）。

`apply` 的替换算法与 frontend/translate/background/glossary.ts 对齐：
  - 单次正则替换，避免连环替换（A→B 且 B→C 时，A 只变成 B）
  - 长词优先，短词不会误吃长词（US 不会命中 USB）
  - 拉丁/数字开头的词加词边界保护（US 不会命中 focus）
  - CJK 词不加边界（中文没有空格分词）
  - 大小写不敏感匹配，但替换值保持术语表里写死的大小写
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _escape_regex(s: str) -> str:
    """转义正则元字符。"""
    return re.escape(s)


def _is_word_boundary_sensitive(source: str) -> bool:
    """是否是"词边界敏感"的词（拉丁字母 / 数字开头）。"""
    return bool(source) and bool(re.match(r"[A-Za-z0-9]", source[0]))


def _normalize_terms(terms: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """去重 + 长词优先（决定正则 alternation 的匹配顺序）。"""
    seen = set()
    unique: List[Tuple[str, str]] = []
    for src, tgt in terms:
        if not src or not tgt:
            continue
        key = src.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append((src, tgt))
    unique.sort(key=lambda p: len(p[0]), reverse=True)
    return unique


def apply_glossary(text: str, terms: List[Tuple[str, str]]) -> str:
    """对 `text` 应用术语表（source → target），纯函数，便于单测。

    采用【单次正则替换】而不是逐条替换，从而保证：
      - 替换结果不会被后续术语二次替换（防连环替换）
      - 长词优先，短词不会误吃长词
      - 词边界保护（仅拉丁/数字词需要）
    """
    if not text or not terms:
        return text

    sorted_terms = _normalize_terms(terms)
    if not sorted_terms:
        return text

    # 小写 key → 译文（匹配时不区分大小写）
    lookup = {src.lower(): tgt for src, tgt in sorted_terms}

    # 每个候选自带词边界（仅拉丁/数字词需要），合成一个正则，单次替换
    alternatives = []
    for src, _tgt in sorted_terms:
        escaped = _escape_regex(src)
        if _is_word_boundary_sensitive(src):
            alternatives.append(r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])")
        else:
            alternatives.append(escaped)
    pattern = re.compile("|".join(alternatives), re.IGNORECASE)

    return pattern.sub(lambda m: lookup.get(m.group(0).lower(), m.group(0)), text)


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

    def add_many(self, terms: Dict[str, str]) -> None:
        """批量添加术语（如来自 AI 上下文的术语表）。"""
        with self._lock:
            for src, tgt in terms.items():
                self._terms[str(src).strip()] = str(tgt).strip()
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
        return self.render_prompt_rules()

    def render_prompt_rules(self) -> str:
        """生成「术语强制约束」文本，注入 system prompt（事前约束）。

        输出形如：
            术语强制约束（必须严格遵守）：
            - "X" 必须译为 "Y"
        """
        if not self._terms:
            return ""
        lines = ["术语强制约束（必须严格遵守，译文中出现以下词汇时必须使用指定译法）："]
        for src, tgt in _normalize_terms(list(self._terms.items())):
            lines.append(f'- "{src}" 必须译为 "{tgt}"')
        return "\n".join(lines)

    def apply(self, text: str) -> str:
        """事后兜底：在译文（或原文）上执行术语替换。

        单次正则替换，防连环替换；长词优先；拉丁词有词边界保护。
        """
        with self._lock:
            items = list(self._terms.items())
        return apply_glossary(text, items)

    def replace_in_text(self, text: str) -> str:
        """兼容旧接口：等价于 `apply(text)`。"""
        return self.apply(text)

    @property
    def size(self) -> int:
        return len(self._terms)
