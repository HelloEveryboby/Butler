"""把核心能力注册为 LLM 工具。

与 ``skill_tools`` 并列但独立：能力来自 ``butler/core/capabilities`` 注册表，
不经过 ``SkillManager``，也不依赖 ``skills/`` 目录。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from butler.core.capabilities import capability_registry

from .tool_registry import ToolRegistry
from .types import PermissionLevel

logger = logging.getLogger(__name__)

_MAX_RESULT_CHARS = 8000


def _make_handler(name: str):
    def handler(arguments: dict[str, Any], **context: Any) -> dict[str, Any]:
        args = dict(arguments or {})
        action = str(args.pop("action", None) or "run")
        nested = args.pop("kwargs", None)
        if isinstance(nested, dict):
            args.update(nested)
        args.pop("butler_app", None)
        args.pop("entities", None)

        result = capability_registry.execute(name, action, args)
        if isinstance(result, dict) and result.get("error"):
            return {
                "success": False,
                "error": str(result["error"])[:_MAX_RESULT_CHARS],
                "metadata": {"capability": name, "action": action},
            }
        return {
            "success": True,
            "content": json.dumps(result, ensure_ascii=False, default=str)[:_MAX_RESULT_CHARS],
            "metadata": {"capability": name, "action": action},
        }

    return handler


def register_capability_tools(
    registry: ToolRegistry,
    permission_level: PermissionLevel = PermissionLevel.REQUIRE_CONFIRM,
    max_tools: int | None = None,
) -> dict[str, str]:
    """把核心能力注册进工具表，返回 ``{tool_name: capability_name}``。"""
    mapping: dict[str, str] = {}
    used_names: set[str] = set()

    for spec in capability_registry.all():
        if max_tools is not None and len(mapping) >= max_tools:
            break
        tool_name = spec.name
        if tool_name in used_names or registry.get(tool_name):
            suffix = 2
            while f"{tool_name}_{suffix}" in used_names or registry.get(f"{tool_name}_{suffix}"):
                suffix += 1
            tool_name = f"{tool_name}_{suffix}"
        used_names.add(tool_name)

        registry.register(
            handler=_make_handler(spec.name),
            name=tool_name,
            description=spec.description,
            parameters=spec.tool_schema()["function"]["parameters"],
            permission_level=permission_level,
            is_read_only=spec.risk == "low",
            is_destructive=spec.risk in ("high", "critical"),
        )
        mapping[tool_name] = spec.name

    logger.info("Registered %d capability tools", len(mapping))
    return mapping
