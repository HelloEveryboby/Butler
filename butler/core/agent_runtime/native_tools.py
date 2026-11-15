"""原生工具 — 让 Agent 直接调用 C / C++ / Go / Rust 模块。

Agent 拿到两个工具：
* ``native_call``   调用一个 BHL 方法（自动路由到实现它的语言模块）
* ``native_status`` 查看各语言模块是否已构建、是否在运行

这样「混合编程」不是 README 里的标语：LLM 可以真的把任务分派给本地原生代码。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .tool_registry import ToolRegistry
from .types import PermissionLevel

logger = logging.getLogger(__name__)

_MAX_RESULT_CHARS = 12000


def register_native_tools(registry: ToolRegistry, hub: Any = None) -> None:
    """把 BHL 原生调用能力注册为工具。"""
    if hub is None:
        from butler.core.hybrid_hub import get_hub

        hub = get_hub()

    def native_call(arguments: dict[str, Any], **context: Any) -> dict[str, Any]:
        method = str((arguments or {}).get("method") or "").strip()
        if not method:
            return {"success": False, "error": "缺少 method 参数"}

        params = arguments.get("params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError as exc:
                return {"success": False, "error": f"params 不是合法 JSON: {exc}"}
        if not isinstance(params, dict):
            return {"success": False, "error": "params 必须是对象"}

        envelope = hub.call(
            method,
            params,
            module=arguments.get("module") or None,
            timeout=float(arguments.get("timeout") or 0) or None,
        )
        content = json.dumps(envelope, ensure_ascii=False, default=str)[:_MAX_RESULT_CHARS]
        if envelope.get("ok"):
            return {
                "success": True,
                "content": content,
                "metadata": {"via": envelope.get("via"), "module": envelope.get("module")},
            }
        return {"success": False, "error": content}

    def native_status(arguments: dict[str, Any], **context: Any) -> dict[str, Any]:
        modules = hub.status()
        summary = {
            "modules": modules,
            "languages": sorted({row["language"] for row in modules}),
            "running": [row["name"] for row in modules if row["running"]],
            "built": [row["name"] for row in modules if row["built"]],
        }
        return {
            "success": True,
            "content": json.dumps(summary, ensure_ascii=False)[:_MAX_RESULT_CHARS],
        }

    registry.register(
        handler=native_call,
        name="native_call",
        description=(
            "调用本机混合语言（BHL）模块中的方法，例如 C 的系统信息、C++ 的数学计算、"
            "Go 的并发网络/审计、Rust 的哈希与加密。可用方法与模块用 native_status 查询；"
            "返回 via 字段表明本次是 native:<语言> 还是 python 回退。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "BHL 方法名，如 get_system_info / factorize / hash_sha256",
                },
                "params": {"type": "object", "description": "传给模块的参数对象"},
                "module": {
                    "type": "string",
                    "description": "可选，显式指定模块（同名方法冲突时用）",
                },
                "timeout": {"type": "number", "description": "可选，超时秒数"},
            },
            "required": ["method"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
    )

    registry.register(
        handler=native_status,
        name="native_status",
        description="查看 BHL 各语言模块的构建/运行状态与支持的方法。",
        parameters={"type": "object", "properties": {}},
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
    )

    logger.info("Registered BHL native tools (native_call, native_status)")
