"""
上下文管理器 — 四阶段压缩管道。

参考架构：Claude Code 的四阶段上下文压缩管道。

四阶段压缩：
    1. Microcompaction（微压缩）: Pre-API 预处理阶段，移除冗余格式
    2. Autocompaction（自动压缩）: 上下文接近 token 限制时自动触发
    3. Reactive compact（反应式压缩）: prompt-too-long 错误时触发
    4. Context collapse（上下文折叠）: max output tokens 错误时的降级策略

压缩保留的关键信息（参考 Claude Code）：
    - 修改了哪些文件及如何修改
    - 当前任务是什么
    - 已尝试什么、什么有效/失败
    - 重要的代码片段或决策
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from .condenser import Condenser, RecentNCondenser, SummaryCondenser
from .types import ConversationState, Message

logger = logging.getLogger(__name__)


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
        - 四阶段压缩管道
        - 可插拔压缩策略（Condenser）
        - 压缩后关键信息保留

    使用方式::

        manager = ContextManager(
            token_limit=120000,
            condenser=SummaryCondenser(llm_summarize_handler=my_summarize),
        )

        # 在 Agent 循环中检查是否需要压缩
        manager.compact(conversation_state)

        # 手动触发压缩
        manager.force_compact(conversation_state, CompactionStage.REACTIVE)
    """

    def __init__(
        self,
        token_limit: int = 120000,
        compaction_threshold: float = 0.8,
        condenser: Condenser | None = None,
        llm_summarize_handler: Any = None,
    ):
        self.token_limit = token_limit
        self.compaction_threshold = compaction_threshold
        self._condenser = condenser or RecentNCondenser(keep_recent=20)
        self._llm_summarize = llm_summarize_handler
        self._compaction_history: list[dict[str, Any]] = []

    @property
    def compaction_history(self) -> list[dict[str, Any]]:
        """压缩历史记录。"""
        return list(self._compaction_history)

    def should_compact(self, state: ConversationState) -> bool:
        """检查是否需要自动压缩。"""
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
            压缩结果摘要
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

    def _microcompact(self, messages: list[Message]) -> list[Message]:
        """
        微压缩：Pre-API 预处理。

        - 移除空消息
        - 截断过长的工具输出
        - 移除冗余的系统消息
        """
        result: list[Message] = []
        seen_system = set()

        for msg in messages:
            # 跳过空消息
            if not msg.content and not msg.tool_calls:
                continue

            # 去重系统消息
            if msg.role == "system":
                if msg.content in seen_system:
                    continue
                seen_system.add(msg.content)

            # 截断过长的工具输出（保留前 2000 字符）
            if msg.role == "tool" and len(msg.content) > 2000:
                truncated = msg.content[:2000] + "\n... [truncated]"
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

        使用 Condenser 策略压缩历史消息，保留：
            - 系统提示
            - 最近 N 轮对话
            - 关键决策点
        """
        return self._condenser.condense(messages)

    def _reactive_compact(self, messages: list[Message]) -> list[Message]:
        """
        反应式压缩：prompt-too-long 错误时触发。

        更激进的压缩策略：
            - 只保留系统提示 + 最近 5 轮对话
            - 中间消息用摘要替代
        """
        # 如果有 LLM 摘要能力，使用摘要压缩
        if self._llm_summarize:
            summary_condenser = SummaryCondenser(
                llm_summarize_handler=self._llm_summarize,
                keep_recent=5,
            )
            return summary_condenser.condense(messages)

        # 降级：保留最近 5 轮
        reactive_condenser = RecentNCondenser(keep_recent=10)
        return reactive_condenser.condense(messages)

    def _context_collapse(self, messages: list[Message]) -> list[Message]:
        """
        上下文折叠：max output tokens 错误时的降级策略。

        最激进的压缩：
            - 只保留系统提示 + 最后一条用户消息
            - 所有历史合并为一条摘要
        """
        if not messages:
            return []

        result: list[Message] = []

        # 保留系统消息
        system_msgs = [m for m in messages if m.role == "system"]
        result.extend(system_msgs[:1])  # 只保留第一个系统消息

        # 如果有 LLM 摘要能力，生成整体摘要
        if self._llm_summarize:
            history_text = "\n".join(
                f"[{m.role}]: {m.content[:500]}"
                for m in messages
                if m.role != "system"
            )
            try:
                summary = self._llm_summarize(history_text)
                result.append(
                    Message(
                        role="system",
                        content=f"[Previous conversation summary]: {summary}",
                    )
                )
            except Exception as e:
                logger.warning(f"LLM summarize failed in context collapse: {e}")
                # 降级：手动摘要
                result.append(
                    Message(
                        role="system",
                        content=self._manual_summary(messages),
                    )
                )
        else:
            result.append(
                Message(
                    role="system",
                    content=self._manual_summary(messages),
                )
            )

        # 保留最后一条用户消息
        for msg in reversed(messages):
            if msg.role == "user":
                result.append(msg)
                break

        return result

    def _manual_summary(self, messages: list[Message]) -> str:
        """
        手动生成对话摘要（无 LLM 时的降级方案）。

        保留关键信息：
            - 修改了哪些文件
            - 当前任务
            - 已尝试的方案
        """
        files_mentioned: set[str] = set()
        tools_used: list[str] = []
        user_requests: list[str] = []

        for msg in messages:
            if msg.role == "user" and msg.content:
                user_requests.append(msg.content[:200])

            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_used.append(tc.name)
                    # 提取文件路径
                    for v in tc.arguments.values():
                        if isinstance(v, str) and (
                            "/" in v or "\\" in v or v.endswith(".py")
                        ):
                            files_mentioned.add(v)

        parts = ["[Conversation Summary]"]

        if user_requests:
            parts.append(f"User requests: {user_requests[-3:]}")

        if tools_used:
            parts.append(f"Tools used: {', '.join(set(tools_used))}")

        if files_mentioned:
            parts.append(f"Files mentioned: {', '.join(list(files_mentioned)[:10])}")

        return "\n".join(parts)
