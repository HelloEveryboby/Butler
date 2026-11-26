"""可选 LLM 角色分析 — 仅在显式开启时启用，会消耗 token。"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("ReadingAIAnalysis")

_PROMPT = (
    "你是小说角色分析器。请阅读下面的片段，识别出场人物及其性别。\n"
    '只输出 JSON，格式：{"characters":[{"name":"角色名","gender":"male|female|unknown"}]}\n'
    "不要输出多余解释。片段：\n"
)

_VALID_GENDERS = {"male", "female"}


def analyze_characters(text: str, max_chars: int = 6000) -> tuple[dict[str, str], int]:
    """返回 ({角色名: male|female}, 消耗 token 数)。失败时抛出异常由上层降级。"""
    from butler.core.llm_providers import chat_completions, resolve_llm_config

    cfg = resolve_llm_config()
    if not cfg.is_usable:
        raise RuntimeError("LLM 未配置，无法使用 --ai 分析")

    content, _, _, tokens = chat_completions(
        cfg,
        [{"role": "user", "content": _PROMPT + text[:max_chars]}],
        max_tokens=800,
        temperature=0.0,
    )
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("模型未返回 JSON")

    data = json.loads(match.group(0))
    gender_map: dict[str, str] = {}
    for item in data.get("characters", []):
        name = str(item.get("name", "")).strip()
        gender = str(item.get("gender", "")).strip().lower()
        if name and gender in _VALID_GENDERS:
            gender_map[name] = gender
    return gender_map, int(tokens or 0)
