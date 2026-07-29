"""
Condenser — 可插拔压缩策略。

参考架构：OpenHands V1 的 Condenser 组件。

可插拔策略：
    - SummaryCondenser: 摘要旧消息（需要 LLM）
    - RecentNCondenser: 保留最近 N 轮对话
    - TaskFocusedCondenser: 保留任务相关消息

所有 Condenser 实现统一接口：
    condense(messages: list[Message]) -> list[Message]
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .types import Message

logger = logging.getLogger(__name__)


class Condenser:
    """
    压缩策略基类。

    所有具体策略继承此类并实现 condense 方法。
    """

    def condense(self, messages: list[Message]) -> list[Message]:
        """压缩消息列表。"""
        raise NotImplementedError


class RecentNCondenser(Condenser):
    """
    保留最近 N 轮对话的压缩策略。

    策略：
        1. 保留所有系统消息
        2. 保留最近 N 条非系统消息
        3. 中间消息用占位符替代

    适用于：快速压缩、不需要 LLM 的场景。
    """

    def __init__(self, keep_recent: int = 20):
        self.keep_recent = keep_recent

    def condense(self, messages: list[Message]) -> list[Message]:
        if len(messages) <= self.keep_recent + 5:
            return list(messages)

        # 分离系统消息和非系统消息
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # 保留最近 N 条非系统消息
        recent = non_system[-self.keep_recent :] if len(non_system) > self.keep_recent else non_system
        older = non_system[: -self.keep_recent] if len(non_system) > self.keep_recent else []

        result: list[Message] = list(system_msgs)

        if older:
            result.append(
                Message(
                    role="system",
                    content=(
                        f"[{len(older)} earlier messages condensed. "
                        f"Use /rewind or search history if needed.]"
                    ),
                )
            )

        result.extend(recent)
        return result


class SummaryCondenser(Condenser):
    """
    摘要旧消息的压缩策略。

    策略：
        1. 保留所有系统消息
        2. 保留最近 N 轮对话
        3. 旧消息用 LLM 生成摘要替代

    适用于：需要保留上下文语义的场景。
    需要 LLM summarize 回调。
    """

    def __init__(
        self,
        llm_summarize_handler: Callable[[str], str] | None = None,
        keep_recent: int = 10,
    ):
        self._llm_summarize = llm_summarize_handler
        self.keep_recent = keep_recent

    def condense(self, messages: list[Message]) -> list[Message]:
        if len(messages) <= self.keep_recent + 5:
            return list(messages)

        # 分离
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        if len(non_system) <= self.keep_recent:
            return list(messages)

        recent = non_system[-self.keep_recent :]
        older = non_system[: -self.keep_recent]

        result: list[Message] = list(system_msgs)

        # 生成摘要
        if self._llm_summarize:
            history_text = "\n".join(
                f"[{m.role}]: {m.content[:500]}" for m in older
            )
            try:
                summary = self._llm_summarize(history_text)
                result.append(
                    Message(
                        role="system",
                        content=f"[Earlier conversation summary]: {summary}",
                    )
                )
            except Exception as e:
                logger.warning(f"LLM summarize failed: {e}, falling back to manual")
                result.append(
                    Message(
                        role="system",
                        content=self._manual_summary(older),
                    )
                )
        else:
            result.append(
                Message(
                    role="system",
                    content=self._manual_summary(older),
                )
            )

        result.extend(recent)
        return result

    def _manual_summary(self, messages: list[Message]) -> str:
        """手动摘要（无 LLM 时的降级）。"""
        tools_used: set[str] = set()
        user_msgs: list[str] = []
        assistant_msgs: list[str] = []

        for msg in messages:
            if msg.role == "user" and msg.content:
                user_msgs.append(msg.content[:150])
            elif msg.role == "assistant":
                if msg.content:
                    assistant_msgs.append(msg.content[:150])
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tools_used.add(tc.name)

        parts = [f"[Summary of {len(messages)} earlier messages]"]

        if user_msgs:
            parts.append(f"Key user requests: {' | '.join(user_msgs[-3:])}")

        if tools_used:
            parts.append(f"Tools used: {', '.join(tools_used)}")

        if assistant_msgs:
            parts.append(f"Key responses: {' | '.join(assistant_msgs[-2:])}")

        return "\n".join(parts)


class TaskFocusedCondenser(Condenser):
    """
    任务聚焦压缩策略。

    策略：
        1. 保留所有系统消息
        2. 保留最后一条用户消息（当前任务）
        3. 保留包含特定关键词的消息（文件路径、错误信息、决策点）
        4. 保留最近 N 轮对话
        5. 其他消息丢弃

    适用于：编码任务场景，保留关键上下文。
    """

    # 关键词：这些词出现的消息应该保留
    KEYWORDS = {
        "error", "Error", "failed", "失败",
        "created", "modified", "updated", "deleted",
        "file", "path", "目录", "文件",
        "decision", "decided", "决定",
        "important", "重要",
        "todo", "TODO",
        "fix", "fixed", "修复",
    }

    def __init__(self, keep_recent: int = 15, max_messages: int = 50):
        self.keep_recent = keep_recent
        self.max_messages = max_messages

    def condense(self, messages: list[Message]) -> list[Message]:
        if len(messages) <= self.max_messages:
            return list(messages)

        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # 保留最近 N 条
        recent = non_system[-self.keep_recent :] if len(non_system) > self.keep_recent else non_system
        older = non_system[: -self.keep_recent] if len(non_system) > self.keep_recent else []

        # 从旧消息中筛选包含关键词的
        kept_older: list[Message] = []
        for msg in older:
            if self._contains_keywords(msg):
                kept_older.append(msg)

        result: list[Message] = list(system_msgs)

        if len(kept_older) < len(older):
            dropped = len(older) - len(kept_older)
            result.append(
                Message(
                    role="system",
                    content=f"[{dropped} messages condensed (non-task-relevant)]",
                )
            )

        result.extend(kept_older)
        result.extend(recent)
        return result

    def _contains_keywords(self, msg: Message) -> bool:
        """检查消息是否包含关键词。"""
        text = msg.content
        if not text:
            return False

        for keyword in self.KEYWORDS:
            if keyword in text:
                return True

        # 检查工具调用中的参数
        for tc in msg.tool_calls:
            for v in tc.arguments.values():
                if isinstance(v, str):
                    for keyword in self.KEYWORDS:
                        if keyword in v:
                            return True

        return False
