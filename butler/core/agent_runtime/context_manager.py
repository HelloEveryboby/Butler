"""
上下文管理器 — Token 预算驱动的四阶段压缩管道。

设计目标：省 token、保质量。
    压缩不再按"消息条数"触发，而是按 token 预算：每个阶段对应一个更紧的预算，
    越靠后的阶段越激进。被丢弃消息的关键事实由 BudgetCondenser 浓缩进
    Context Card，避免上下文语义丢失。

四阶段（对应真实失败模式）：
    1. Microcompaction（微压缩）: Pre-API 预处理，移除冗余格式（不依赖预算）
    2. Autocompaction（自动压缩）: 上下文接近 token 限制时触发，目标 = threshold × limit
    3. Reactive compact（反应式压缩）: prompt-too-long 错误时触发，目标 = 50% × limit
    4. Context collapse（上下文折叠）: max output tokens 错误时的紧急地板

压缩保留的关键信息（参考 Claude Code）：
    - 修改了哪些文件及如何修改
    - 当前任务是什么
    - 已尝试什么、什么有效/失败
    - 重要的代码片段或决策
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable

from .condenser import BudgetCondenser, Condenser
from .types import ConversationState, Message

logger = logging.getLogger(__name__)

# 工具输出在微压缩阶段的截断阈值（字符数）
_TOOL_OUTPUT_TRUNCATE = 2000


class CompactionStage(str, Enum):
    """压缩阶段。"""

    MICRO = "microcompaction"
    AUTO = "autocompaction"
    REACTIVE = "reactive_compact"
    COLLAPSE = "context_collapse"


class ContextManager:
    """
    上下文管理器。

    管理对话上下文的生命周期，包括：
        - Token 估算和监控
        - 四阶段预算驱动压缩管道
        - 可插拔压缩策略（Condenser）
        - 压缩后关键信息保留（Context Card）

    使用方式::

        manager = ContextManager(
            token_limit=120000,
            condenser=BudgetCondenser(target_tokens=96000),
        )

        # 在 Agent 循环中检查是否需要压缩
        if manager.should_compact(state):
            manager.compact(state)

        # prompt-too-long 错误时强制更激进的压缩
        manager.force_compact(state, CompactionStage.REACTIVE)
    """

    def __init__(
        self,
        token_limit: int = 120000,
        compaction_threshold: float = 0.8,
        condenser: Condenser | None = None,
        llm_summarize_handler: Callable[[str], str] | None = None,
    ):
        self.token_limit = token_limit
        self.compaction_threshold = compaction_threshold
        # 保留原始 handler 引用，供子代理隔离上下文时继承（subagent_manager 依赖）
        self._llm_summarize_handler = llm_summarize_handler
        # 默认 AUTO 策略：预算 = threshold × limit
        self._condenser = condenser or BudgetCondenser(
            target_tokens=int(token_limit * compaction_threshold),
            llm_summarize_handler=llm_summarize_handler,
        )
        self._compaction_history: list[dict[str, Any]] = []

    @property
    def compaction_history(self) -> list[dict[str, Any]]:
        """压缩历史记录（返回副本）。"""
        return list(self._compaction_history)

    def should_compact(self, state: ConversationState) -> bool:
        """检查是否需要自动压缩（估算 token 超过阈值）。"""
        estimated = state.estimate_tokens()
        threshold = int(self.token_limit * self.compaction_threshold)
        return estimated > threshold

    def compact(
        self,
        state: ConversationState,
        stage: CompactionStage = CompactionStage.AUTO,
    ) -> dict[str, Any]:
        """
        执行上下文压缩。

        参数:
            state: 对话状态
            stage: 压缩阶段

        返回:
            压缩结果摘要（含 stage/前后消息数/前后 token 数/压缩率）
        """
        original_count = len(state.messages)
        original_tokens = state.estimate_tokens()

        logger.info(
            f"Starting compaction (stage={stage.value}): "
            f"{original_count} messages, ~{original_tokens} tokens"
        )

        if stage == CompactionStage.MICRO:
            new_messages = self._microcompact(state.messages)
        elif stage == CompactionStage.AUTO:
            new_messages = self._autocompact(state.messages)
        elif stage == CompactionStage.REACTIVE:
            new_messages = self._reactive_compact(state.messages)
        elif stage == CompactionStage.COLLAPSE:
            new_messages = self._context_collapse(state.messages)
        else:
            new_messages = self._autocompact(state.messages)

        state.replace_messages(new_messages)

        new_count = len(state.messages)
        new_tokens = state.estimate_tokens()

        result = {
            "stage": stage.value,
            "original_messages": original_count,
            "new_messages": new_count,
            "original_tokens": original_tokens,
            "new_tokens": new_tokens,
            "reduction_pct": (
                round((1 - new_tokens / original_tokens) * 100, 1)
                if original_tokens > 0
                else 0
            ),
        }

        self._compaction_history.append(result)
        logger.info(f"Compaction complete: {result}")
        return result

    def force_compact(
        self, state: ConversationState, stage: CompactionStage
    ) -> dict[str, Any]:
        """强制执行压缩（忽略阈值检查）。"""
        return self.compact(state, stage)

    # ── 阶段实现 ────────────────────────────────────────────────────

    def _microcompact(self, messages: list[Message]) -> list[Message]:
        """
        微压缩：Pre-API 预处理（不依赖预算）。

        - 移除空消息
        - 截断过长的工具输出
        - 移除重复的系统消息
        """
        result: list[Message] = []
        seen_system: set[str] = set()

        for msg in messages:
            # 跳过空消息
            if not msg.content and not msg.tool_calls:
                continue

            # 去重系统消息
            if msg.role == "system":
                if msg.content in seen_system:
                    continue
                seen_system.add(msg.content)

            # 截断过长的工具输出
            if msg.role == "tool" and len(msg.content) > _TOOL_OUTPUT_TRUNCATE:
                truncated = msg.content[:_TOOL_OUTPUT_TRUNCATE] + "\n... [truncated]"
                result.append(
                    Message(
                        role=msg.role,
                        content=truncated,
                        tool_call_id=msg.tool_call_id,
                        metadata={**msg.metadata, "truncated": True},
                    )
                )
            else:
                result.append(msg)

        return result

    def _autocompact(self, messages: list[Message]) -> list[Message]:
        """
        自动压缩：上下文接近 token 限制时触发。

        使用 self._condenser（默认 BudgetCondenser，预算 = threshold × limit；
        或用户传入的自定义 Condenser）。
        """
        return self._condenser.condense(messages)

    def _reactive_compact(self, messages: list[Message]) -> list[Message]:
        """
        反应式压缩：prompt-too-long 错误时触发。

        更激进的预算 = 50% × token_limit，保留更少的最近消息。
        """
        budget = int(self.token_limit * 0.5)
        condenser = BudgetCondenser(
            target_tokens=budget,
            keep_recent=4,
            llm_summarize_handler=self._llm_summarize_handler,
        )
        return condenser.condense(messages)

    def _context_collapse(self, messages: list[Message]) -> list[Message]:
        """
        上下文折叠：max output tokens 错误时的紧急地板。

        最激进的降级：
            - 只保留第一条系统消息
            - 所有历史浓缩为一条 Context Card（结构化摘要 / LLM 摘要）
            - 保留最后一条用户消息（当前任务）
        """
        if not messages:
            return []

        result: list[Message] = []

        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # 只保留第一条系统消息
        if system_msgs:
            result.append(system_msgs[0])

        # 对所有非系统消息生成 Context Card
        if non_system:
            condenser = BudgetCondenser(
                llm_summarize_handler=self._llm_summarize_handler
            )
            card = condenser._build_context_card(non_system)
            if card is not None:
                result.append(card)

            # 保留最后一条用户消息
            for m in reversed(non_system):
                if m.role == "user":
                    result.append(m)
                    break

        return result
