"""插件能力 → Butler LLM 工具表。

连接器的 capability（name/description/schema/risk/source）转换为
主流 function-calling 格式，供 Butler 的 LLM 编排器直接注入。
描述质量决定模型工具选中率——转换时保留全部描述信息并做规范化。
"""

from __future__ import annotations

from typing import Any, Iterable


class SkillRegistry:
    """连接器能力表的 Butler 侧视图。"""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._disabled: set[str] = set()

    # ---- 同步 ----

    def sync(self, capabilities: Iterable[dict[str, Any]]) -> None:
        """全量替换（连接器 registry.sync 时调用）。"""
        self._tools = {c["name"]: dict(c) for c in capabilities}

    def upsert(self, capabilities: Iterable[dict[str, Any]]) -> None:
        for c in capabilities:
            self._tools[c["name"]] = dict(c)

    def remove(self, names: Iterable[str]) -> None:
        for n in names:
            self._tools.pop(n, None)

    # ---- 启停（Butler 侧按需启用，避免工具过多稀释选中率） ----

    def disable(self, name: str) -> bool:
        if name not in self._tools:
            return False
        self._disabled.add(name)
        return True

    def enable(self, name: str) -> bool:
        if name not in self._tools:
            return False
        self._disabled.discard(name)
        return True

    # ---- 输出 ----

    def tools_for_llm(self) -> list[dict[str, Any]]:
        """OpenAI function-calling 格式的工具定义（仅启用中的）。"""
        out = []
        for name in sorted(self._tools):
            if name in self._disabled:
                continue
            cap = self._tools[name]
            fn: dict[str, Any] = {
                "name": cap["name"],
                "description": cap.get("description", ""),
            }
            schema = cap.get("schema")
            if isinstance(schema, dict) and schema:
                fn["parameters"] = schema
            else:
                fn["parameters"] = {"type": "object", "properties": {}}
            out.append({"type": "function", "function": fn})
        return out

    def capabilities(self) -> list[dict[str, Any]]:
        return [dict(self._tools[n]) for n in sorted(self._tools)]

    def is_disabled(self, name: str) -> bool:
        return name in self._disabled

    def size(self) -> int:
        return len(self._tools)

    def risk_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for cap in self._tools.values():
            risk = str(cap.get("risk", "unknown"))
            counts[risk] = counts.get(risk, 0) + 1
        return counts
