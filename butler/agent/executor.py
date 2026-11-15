# -*- coding: utf-8 -*-
"""步骤执行器 — 按工具名执行真实工具，绝不返回伪造结果。

旧实现会在找不到技能包时返回「拟真周报」之类假数据，让 Agent 看起来成功、
实际什么都没做。现在未知工具一律返回失败，并列出真实可用的工具名。

``Agent.run_task`` 已改为直接驱动 ``AgentRuntime``，本模块用于「先规划再执行」
的独立场景和旧调用方兼容。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Executor:
    """执行 Planner 产出的步骤。"""

    def __init__(self, registry=None, package_loader=None, skill_manager=None):
        # package_loader 仅为旧签名兼容保留，不再使用
        self._registry = registry
        self._package_loader = package_loader
        self._skill_manager = skill_manager

    def _get_registry(self):
        if self._registry is not None:
            return self._registry
        from butler.core.tool_bridge import get_registry

        self._registry = get_registry()
        return self._registry

    def execute_step(self, step: Dict[str, Any], previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个步骤，返回 ``{"status", "result"|"error"}``。"""
        action = str(step.get("action") or "")
        if not action:
            return {"status": "failed", "error": "步骤缺少 action 字段"}

        if action == "agent_loop":
            return {
                "status": "failed",
                "error": "agent_loop 是交给 AgentRuntime 的标记，不能直接执行；请使用 Agent.run_task()。",
            }

        resolved_input = self._resolve_dependencies(step.get("input") or {}, previous_results)

        if self._skill_manager is not None and action in getattr(self._skill_manager, "manifests", {}):
            try:
                result = self._skill_manager.execute(
                    action,
                    str(resolved_input.pop("action", "run")),
                    entities=resolved_input,
                    **resolved_input,
                )
            except Exception as exc:
                logger.error("技能 %s 执行失败: %s", action, exc, exc_info=True)
                return {"status": "failed", "error": str(exc)}
            return {"status": "success", "result": result}

        registry = self._get_registry()
        executor = registry.get(action)
        if executor is None:
            available = ", ".join(sorted(registry.list_names()))
            return {"status": "failed", "error": f"未知工具 '{action}'。可用工具: {available}"}

        try:
            tool_result = executor.execute(arguments=resolved_input)
        except Exception as exc:
            logger.error("工具 %s 执行失败: %s", action, exc, exc_info=True)
            return {"status": "failed", "error": str(exc)}

        if not tool_result.success:
            return {"status": "failed", "error": tool_result.error or "工具执行失败"}
        return {"status": "success", "result": tool_result.content}

    @staticmethod
    def _resolve_dependencies(step_input: Dict[str, Any], previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """把 ``{"source_step": "1"}`` 替换为上游步骤的真实结果。"""
        resolved: Dict[str, Any] = {}
        for key, value in step_input.items():
            if isinstance(value, dict) and "source_step" in value:
                prev = previous_results.get(str(value["source_step"]), {})
                resolved[key] = prev.get("result") if isinstance(prev, dict) else prev
            elif key == "source_step":
                prev = previous_results.get(str(value), {})
                resolved["dependent_data"] = prev.get("result") if isinstance(prev, dict) else prev
            else:
                resolved[key] = value
        return resolved
