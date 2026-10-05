"""AI 上下文翻译：解决逐段独立翻译导致的术语不一致、指代乱翻。

流程：
1. `build_context(full_text, target_lang)` 调一次 LLM，产出
   `{"summary": "...", "terms": [{"source":..., "target":...}, ...]}`（严格 JSON）；
2. 结果按 (内容 hash, target_lang) 缓存到 data 目录，24h 有效；
3. `render_context_block()` 把「摘要 + 术语表」渲染成 system prompt 片段；
4. `TranslationSystem.translate(..., use_context=True)` 注入该片段，
   同时把术语写进 Glossary。

成本控制：每篇文档只多一次 LLM 调用（有缓存时零次）。
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional


# 上下文缓存有效期：24 小时
CONTEXT_TTL = 24 * 3600

# build_context 的 prompt
_CONTEXT_SYSTEM_PROMPT = (
    "你是一名资深翻译项目经理。在翻译开始前，你需要通读原文并为后续译者准备参考信息。"
    "只输出一个 JSON 对象，不要输出任何其他文字、解释或代码块标记。"
)
_CONTEXT_USER_PROMPT = (
    "请通读以下{to}文档的原文，输出严格 JSON（不要用代码块包裹），结构为：\n"
    '{"summary": "用{to}写的全文摘要，200字以内", '
    '"terms": [{"source": "原文术语", "target": "统一的{to}译法"}, ...]}\n'
    "要求：\n"
    "1. terms 提取 3~15 个全文反复出现或关键的术语（人名、机构、专业词），译法要统一；\n"
    "2. 除 JSON 外不要输出任何其他内容；\n"
    "3. JSON 必须可以被 json.loads 解析。\n\n"
    "原文如下：\n{doc}"
)


class ContextBuildError(RuntimeError):
    """上下文构建失败（LLM 不可用或返回非法 JSON）。"""


def _content_hash(full_text: str) -> str:
    """文档内容 hash（用于缓存 key）。"""
    normalized = "\n".join(line.rstrip() for line in full_text.splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def parse_context_json(text: str) -> Dict:
    """严格解析 LLM 返回的 JSON（容错：剥离代码块围栏 / 前后杂讯）。"""
    if not text or not text.strip():
        raise ContextBuildError("LLM returned empty context")
    s = text.strip()
    # 剥离 ```json ... ``` 围栏
    fence = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n?```$", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    # 容错：截取第一个 { 到最后一个 }
    if not s.startswith("{"):
        start = s.find("{")
        end = s.rfind("}")
        if start < 0 or end <= start:
            raise ContextBuildError("No JSON object found in LLM output")
        s = s[start:end + 1]
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise ContextBuildError(f"Invalid JSON from LLM: {e}") from e
    if not isinstance(data, dict) or "summary" not in data:
        raise ContextBuildError("Context JSON must contain 'summary'")
    terms_raw = data.get("terms", [])
    terms: List[Dict[str, str]] = []
    if isinstance(terms_raw, list):
        for t in terms_raw:
            if isinstance(t, dict) and t.get("source") and t.get("target"):
                terms.append({"source": str(t["source"]), "target": str(t["target"])})
    return {"summary": str(data["summary"]), "terms": terms}


def render_context_block(ctx: Dict) -> str:
    """把上下文渲染为 system prompt 片段。"""
    parts: List[str] = []
    summary = (ctx or {}).get("summary", "").strip()
    if summary:
        parts.append(f"全文摘要（供翻译参考，请保持全文术语与指代一致）：\n{summary}")
    terms = (ctx or {}).get("terms") or []
    if terms:
        lines = ["全文统一术语表（译文必须严格采用这些译法）："]
        for t in terms:
            lines.append(f'- "{t["source"]}" 必须译为 "{t["target"]}"')
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


class ContextCache:
    """(内容 hash, target_lang) → 上下文 JSON 的磁盘缓存，默认 24h 有效。"""

    def __init__(self, cache_file: str, ttl: float = CONTEXT_TTL):
        self.cache_file = Path(cache_file)
        self.ttl = ttl
        self._data: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.cache_file.exists():
                with self.cache_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data = data
        except (OSError, json.JSONDecodeError):
            self._data = {}

    def _save(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_file.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False)
        except OSError:
            pass

    @staticmethod
    def _key(content_hash: str, target_lang: str) -> str:
        return f"{content_hash}|{target_lang}"

    def get(self, content_hash: str, target_lang: str) -> Optional[Dict]:
        entry = self._data.get(self._key(content_hash, target_lang))
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > self.ttl:
            return None
        return entry.get("context")

    def set(self, content_hash: str, target_lang: str, context: Dict) -> None:
        self._data[self._key(content_hash, target_lang)] = {
            "context": context,
            "ts": time.time(),
        }
        self._save()

    def clear(self) -> None:
        self._data.clear()
        self._save()


# llm_fn(system_prompt, user_prompt) -> str，便于测试注入 mock
LLMFn = Callable[[str, str], str]


def build_context(
    full_text: str,
    target_lang: str,
    llm_fn: Optional[LLMFn] = None,
    cache: Optional[ContextCache] = None,
    max_chars: int = 4000,
) -> Dict:
    """调一次 LLM 产出文档摘要 + 术语表，并缓存 24h。

    - `llm_fn`：LLM 调用函数 (system_prompt, user_prompt) -> str。
      为 None 且缓存未命中时抛出 ContextBuildError。
    - `max_chars`：送给 LLM 的原文最大字符数（成本控制），超出截断。
    - 每篇文档只多一次 LLM 调用：缓存命中时零调用。
    """
    if not full_text or not full_text.strip():
        return {"summary": "", "terms": []}

    h = _content_hash(full_text)
    if cache is not None:
        cached = cache.get(h, target_lang)
        if cached is not None:
            return cached

    if llm_fn is None:
        raise ContextBuildError("No LLM available for context building")

    from .languages import lang_name
    doc = full_text if len(full_text) <= max_chars else full_text[:max_chars]
    # 用 replace 而不是 format：prompt 里含 JSON 花括号
    user_prompt = (_CONTEXT_USER_PROMPT
                   .replace("{to}", lang_name(target_lang))
                   .replace("{doc}", doc))
    try:
        raw = llm_fn(_CONTEXT_SYSTEM_PROMPT, user_prompt)
    except Exception as e:  # noqa: BLE001
        # LLM 不可用（如免费源不支持 chat）→ 统一包装，由调用方降级
        raise ContextBuildError(f"LLM call failed: {e}") from e
    ctx = parse_context_json(raw)

    if cache is not None:
        cache.set(h, target_lang, ctx)
    return ctx
