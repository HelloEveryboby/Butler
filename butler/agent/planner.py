# -*- coding: utf-8 -*-
"""任务规划器 — 用真实 LLM 把目标拆成可执行的工具步骤。

注意：``Agent.run_task`` 现在直接驱动 ``AgentRuntime`` 的 tool calling 循环，
本模块保留给需要「先出计划再执行」的场景，以及旧调用方兼容。
没有可用 LLM 时不会再编造假的执行结果，只返回一个明确的单步计划。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Planner:
    """把任务目标转换为有序步骤（action 为真实工具名）。"""

    def __init__(self, use_mock: bool = None, llm_call_handler=None):
        # use_mock 仅表示「不调用 LLM」，不再生成假的业务输出
        self.use_mock = bool(use_mock)
        self._llm_call_handler = llm_call_handler

    def create_plan(self, task_input: str, tools: Optional[List[dict]] = None) -> List[Dict[str, Any]]:
        """生成步骤清单。"""
        if self.use_mock:
            return self._single_step(task_input, reason="已禁用 LLM 规划")

        try:
            return self._create_llm_plan(task_input, tools or [])
        except Exception as exc:
            logger.warning("LLM 规划失败，退化为单步计划: %s", exc)
            return self._single_step(task_input, reason=str(exc))

    @staticmethod
    def _single_step(task_input: str, reason: str) -> List[Dict[str, Any]]:
        """诚实的兜底：一步，交给 Agent 循环自主决定用哪个工具。"""
        return [
            {
                "id": "1",
                "action": "agent_loop",
                "description": f"交由 Agent 循环自主完成（{reason}）",
                "input": {"goal": task_input},
            }
        ]

    def _create_llm_plan(self, task_input: str, tools: List[dict]) -> List[Dict[str, Any]]:
        """调用 LLM 生成 JSON 步骤列表，并校验 action 是否真实存在。"""
        from butler.core.llm_providers import chat_completions, resolve_llm_config

        cfg = resolve_llm_config(self._config_get)
        if not cfg.is_usable:
            raise RuntimeError("没有可用的 LLM 提供商")

        tool_names = sorted(
            {t.get("function", {}).get("name") for t in tools if t.get("function", {}).get("name")}
        )
        allowed = f"\nAvailable tools: {', '.join(tool_names)}" if tool_names else ""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a task planner. Decompose the goal into at most 6 ordered steps. "
                    "Return ONLY a JSON array; each item is "
                    '{"id": "1", "action": "<tool name>", "description": "...", "input": {...}}.'
                    + allowed
                ),
            },
            {"role": "user", "content": task_input},
        ]

        content, _tool_calls, _stop, _tokens = chat_completions(
            cfg, messages, max_tokens=1024, temperature=0.2
        )
        match = re.search(r"\[.*\]", content or "", re.DOTALL)
        if not match:
            raise ValueError("LLM 未返回 JSON 计划")

        steps = json.loads(match.group(0))
        if not isinstance(steps, list) or not steps:
            raise ValueError("LLM 返回的计划为空")

        if tool_names:
            steps = [s for s in steps if str(s.get("action")) in tool_names] or steps
        return steps

    @staticmethod
    def _config_get(key: str, default: Any = None) -> Any:
        try:
            from package.core_utils.config_loader import config_loader

            value = config_loader.get(key)
            return default if value is None else value
        except Exception:
            return default
