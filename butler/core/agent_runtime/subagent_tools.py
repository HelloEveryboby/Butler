"""子代理工具 — 让主 Agent 把子任务委派给隔离上下文的专职子代理。

工具名沿用 Claude Code 的 ``task``：LLM 给出任务描述，运行时选择子代理
（explorer / reviewer / worker，或 ``.butler/agents/`` 下的自定义定义），
子代理在独立上下文里执行，只把最终摘要返回给父代理。
"""

from __future__ import annotations

import logging
from typing import Any

from .tool_registry import ToolRegistry
from .types import PermissionLevel

logger = logging.getLogger(__name__)

_MAX_RESULT_CHARS = 12000


def register_subagent_tools(registry: ToolRegistry, runtime: Any, manager: Any) -> None:
    """把 ``task`` 工具注册到已构建的 AgentRuntime 上。"""
    if manager is None:
        return

    def task(arguments: dict[str, Any], **context: Any) -> dict[str, Any]:
        prompt = str((arguments or {}).get("prompt") or "").strip()
        if not prompt:
            return {"success": False, "error": "缺少 prompt 参数"}

        agent_name = str(arguments.get("agent") or "").strip()
        if not agent_name:
            agent_name = manager.match_agent(prompt) or "explorer"

        definition = manager.get_agent(agent_name)
        if definition is None:
            available = ", ".join(d.name for d in manager.list_agents())
            return {"success": False, "error": f"未知子代理 '{agent_name}'。可用: {available}"}

        result = manager.delegate(agent_name, prompt, parent_runtime=runtime)
        response = str(result.get("response") or "").strip()[:_MAX_RESULT_CHARS]
        stop = result.get("stop_reason", "")
        payload = (
            f"[subagent:{agent_name}] stop={stop} turns={result.get('turns', 0)}\n\n"
            f"{response or '(子代理没有返回文本)'}"
        )
        if stop == "error":
            return {"success": False, "error": payload, "metadata": {"subagent": agent_name}}
        return {
            "success": True,
            "content": payload,
            "metadata": {"subagent": agent_name, "turns": result.get("turns", 0)},
        }

    def list_subagents(arguments: dict[str, Any], **context: Any) -> dict[str, Any]:
        lines = [
            f"- {d.name}: {d.description} (tools={d.tools or 'inherit'}, max_turns={d.max_turns})"
            for d in manager.list_agents()
        ]
        return {"success": True, "content": "\n".join(lines) or "没有可用的子代理。"}

    registry.register(
        handler=task,
        name="task",
        description=(
            "把一个有边界的子任务委派给专职子代理，子代理使用隔离上下文执行，只返回摘要。"
            "适合：大范围代码探索（explorer）、代码审查（reviewer）、独立的小改动/跑测试（worker）。"
            "可用子代理见 list_subagents。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "交给子代理的完整任务描述"},
                "agent": {
                    "type": "string",
                    "description": "可选：explorer / reviewer / worker 或自定义子代理名；省略时按描述自动匹配",
                },
            },
            "required": ["prompt"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
    )

    registry.register(
        handler=list_subagents,
        name="list_subagents",
        description="列出当前可用的子代理及其工具权限。",
        parameters={"type": "object", "properties": {}},
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
    )

    logger.info("Registered subagent tools (task, list_subagents)")
