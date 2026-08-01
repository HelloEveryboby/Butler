"""
Agent Runtime 上下文管理子系统单元测试。

覆盖模块：
    - butler.core.agent_runtime.condenser
    - butler.core.agent_runtime.context_manager
    - butler.core.agent_runtime.subagent_manager
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from butler.core.agent_runtime.condenser import (
    BudgetCondenser,
    Condenser,
    ImportanceScorer,
    _estimate_tokens,
)
from butler.core.agent_runtime.context_manager import (
    CompactionStage,
    ContextManager,
)
from butler.core.agent_runtime.subagent_manager import (
    SubagentDefinition,
    SubagentManager,
)
from butler.core.agent_runtime.types import (
    ConversationState,
    Event,
    EventType,
    Message,
    ToolCall,
)


# ── 辅助函数 ────────────────────────────────────────────────────


def _make_messages(count: int, prefix: str = "msg") -> list[Message]:
    """生成指定数量的 user/assistant 交替消息（短消息）。"""
    msgs: list[Message] = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(Message(role=role, content=f"{prefix}-{i}"))
    return msgs


def _make_big_messages(count: int, size: int = 40) -> list[Message]:
    """生成指定数量的 user/assistant 交替消息（每条 size 字符 ≈ size//4 tokens）。"""
    return [
        Message(role="user" if i % 2 == 0 else "assistant", content="x" * size)
        for i in range(count)
    ]


def _make_tool_handler(content: str = "ok"):
    """生成一个简单的工具 handler。"""
    return lambda arguments, **ctx: {"content": content}


# ── Condenser 基类测试 ──────────────────────────────────────────


class TestCondenserBase:
    """Condenser 基类测试。"""

    def test_base_condense_raises_not_implemented(self):
        """基类的 condense 方法应抛出 NotImplementedError。"""
        condenser = Condenser()
        with pytest.raises(NotImplementedError):
            condenser.condense([])


# ── ImportanceScorer 测试 ───────────────────────────────────────


class TestImportanceScorer:
    """ImportanceScorer 重要性打分测试。"""

    def test_score_in_valid_range(self):
        """分数应在 [0, 100] 范围内。"""
        scorer = ImportanceScorer()
        msg = Message(role="user", content="hello")
        score = scorer.score(msg, 0, 1)
        assert 0 <= score <= 100

    def test_newer_message_scores_higher(self):
        """越新的消息（index 越大）分数应越高（recency 衰减）。"""
        scorer = ImportanceScorer()
        msg = Message(role="user", content="plain text here")
        old_score = scorer.score(msg, 0, 10)  # 最旧
        new_score = scorer.score(msg, 9, 10)  # 最新
        assert new_score > old_score

    def test_error_signal_boosts_score(self):
        """含 error/failed 信号的消息分数应高于普通消息。"""
        scorer = ImportanceScorer()
        plain = Message(role="assistant", content="just some normal response text")
        with_error = Message(
            role="assistant", content="error: something failed in the code"
        )
        assert scorer.score(with_error, 0, 5) > scorer.score(plain, 0, 5)

    def test_write_tool_scores_higher_than_read(self):
        """写操作（edit）的 tool_impact 应高于读操作（read）。"""
        scorer = ImportanceScorer()
        write_msg = Message(
            role="assistant",
            content="m",
            tool_calls=[ToolCall(id="1", name="edit", arguments={"path": "x.py"})],
        )
        read_msg = Message(
            role="assistant",
            content="m",
            tool_calls=[ToolCall(id="2", name="read", arguments={"path": "x.py"})],
        )
        assert scorer.score(write_msg, 0, 5) > scorer.score(read_msg, 0, 5)

    def test_user_role_scores_higher_than_tool(self):
        """user 消息（意图）分数应高于 tool 消息（结果）。"""
        scorer = ImportanceScorer()
        user_msg = Message(role="user", content="some content here")
        tool_msg = Message(role="tool", content="some content here")
        assert scorer.score(user_msg, 0, 5) > scorer.score(tool_msg, 0, 5)


# ── BudgetCondenser 测试 ────────────────────────────────────────


class TestBudgetCondenser:
    """BudgetCondenser 预算驱动压缩测试。"""

    def test_empty_messages_returns_empty(self):
        """空消息列表应返回空。"""
        condenser = BudgetCondenser(target_tokens=100)
        assert condenser.condense([]) == []

    def test_under_budget_returns_as_is(self):
        """未超预算时原样返回。"""
        condenser = BudgetCondenser(target_tokens=10000)
        messages = _make_messages(5)
        result = condenser.condense(messages)
        assert result == messages

    def test_over_budget_reduces_tokens(self):
        """超预算时应减少 token 总量与消息数。"""
        condenser = BudgetCondenser(target_tokens=30, keep_recent=2)
        # 10 条 × 40 字符 = 400 字符 ≈ 100 tokens > 30
        messages = _make_big_messages(10, 40)
        result = condenser.condense(messages)
        assert _estimate_tokens(result) < _estimate_tokens(messages)
        assert len(result) < len(messages)

    def test_system_messages_always_preserved(self):
        """系统消息应始终保留。"""
        condenser = BudgetCondenser(target_tokens=10, keep_recent=2)
        messages = [Message(role="system", content="important system prompt")]
        messages.extend(_make_big_messages(10, 40))
        result = condenser.condense(messages)
        system_msgs = [m for m in result if m.role == "system"]
        assert any(m.content == "important system prompt" for m in system_msgs)

    def test_recent_messages_always_preserved(self):
        """最近 keep_recent 条消息应始终保留。"""
        condenser = BudgetCondenser(target_tokens=10, keep_recent=3)
        messages = _make_big_messages(10, 40)
        result = condenser.condense(messages)
        non_system = [m for m in result if m.role != "system"]
        # 最后 3 条原始消息应在结果中
        assert messages[-1] in non_system
        assert messages[-3] in non_system

    def test_context_card_generated_with_key_facts(self):
        """被丢弃消息应生成 Context Card，含文件路径与工具名等关键事实。"""
        condenser = BudgetCondenser(target_tokens=5, keep_recent=2)
        tool_call = ToolCall(
            id="tc1", name="edit", arguments={"file_path": "/src/app/main.py"}
        )
        messages = [
            Message(role="user", content="please fix the error in main.py"),
            Message(role="assistant", content="editing", tool_calls=[tool_call]),
            Message(role="assistant", content="done"),
            Message(role="user", content="x" * 40),
            Message(role="user", content="y" * 40),  # recent
            Message(role="assistant", content="z" * 40),  # recent
        ]
        result = condenser.condense(messages)
        cards = [
            m for m in result if m.role == "system" and "Context Card" in m.content
        ]
        assert len(cards) == 1
        # 文件路径与工具名应被抽取进 card
        assert "main.py" in cards[0].content or "edit" in cards[0].content

    def test_high_importance_message_retained(self):
        """token 紧张时，含 error/路径的高分消息应保留，低分消息进 Context Card。"""
        condenser = BudgetCondenser(target_tokens=15, keep_recent=2)
        messages = [
            Message(role="user", content="error: something failed in /app/server.py"),
            Message(role="user", content="hello world"),
            Message(role="user", content="nice weather"),
            Message(role="user", content="recent a"),
            Message(role="assistant", content="recent b"),
        ]
        result = condenser.condense(messages)
        # 高分消息（含 error + 路径）保留为独立 user 消息
        assert any(
            "error: something failed" in m.content and m.role == "user"
            for m in result
        )
        # 有消息被压缩 → 存在 Context Card
        assert any(
            m.role == "system" and "Context Card" in m.content for m in result
        )

    def test_max_messages_triggers_compression(self):
        """max_messages 上限触发压缩（即使 token 未超）。"""
        condenser = BudgetCondenser(
            target_tokens=100000, max_messages=5, keep_recent=2
        )
        messages = _make_messages(10)  # 总 token 极少，但条数 > 5
        result = condenser.condense(messages)
        assert len(result) < len(messages)


class TestBudgetCondenserLLM:
    """BudgetCondenser LLM 摘要测试。"""

    def test_llm_summary_used_when_available(self):
        """有 LLM handler 且丢弃消息 >= 3 时，Context Card 用 LLM 摘要。"""
        calls: list[str] = []

        def summarize(text: str) -> str:
            calls.append(text)
            return "llm summary of dropped messages"

        condenser = BudgetCondenser(
            target_tokens=10, keep_recent=2, llm_summarize_handler=summarize
        )
        messages = [Message(role="system", content="sys")]
        messages.extend(_make_big_messages(10, 40))
        result = condenser.condense(messages)

        assert len(calls) == 1  # LLM 调用一次
        # 摘要应在结果中
        assert any("llm summary of dropped messages" in m.content for m in result)

    def test_llm_failure_falls_back_to_structural_card(self):
        """LLM 异常时回退到结构化 Context Card。"""
        def failing_summarize(text: str) -> str:
            raise RuntimeError("LLM unavailable")

        condenser = BudgetCondenser(
            target_tokens=10, keep_recent=2, llm_summarize_handler=failing_summarize
        )
        messages = [Message(role="system", content="sys")]
        messages.extend(_make_big_messages(10, 40))
        result = condenser.condense(messages)

        # 回退到结构化 card
        assert any("Context Card" in m.content for m in result)


# ── ContextManager 测试 ─────────────────────────────────────────


class TestContextManagerShouldCompact:
    """ContextManager.should_compact 测试。"""

    def test_below_threshold_returns_false(self):
        """token 数低于阈值时返回 False。"""
        manager = ContextManager(token_limit=10000, compaction_threshold=0.8)
        state = ConversationState()
        state.append(Message(role="user", content="x" * 1000))
        assert manager.should_compact(state) is False

    def test_above_threshold_returns_true(self):
        """token 数高于阈值时返回 True。"""
        manager = ContextManager(token_limit=1000, compaction_threshold=0.8)
        state = ConversationState()
        state.append(Message(role="user", content="x" * 4000))
        assert manager.should_compact(state) is True

    def test_exactly_at_threshold_returns_false(self):
        """token 数正好等于阈值时返回 False（使用 > 而非 >=）。"""
        manager = ContextManager(token_limit=1000, compaction_threshold=0.8)
        state = ConversationState()
        state.append(Message(role="user", content="x" * 3200))
        assert manager.should_compact(state) is False


class TestContextManagerCompact:
    """ContextManager.compact 各阶段测试。"""

    def test_compact_auto_reduces_tokens(self):
        """AUTO 阶段应减少 token 总量。"""
        # token_limit=200 → AUTO 预算 = 160
        manager = ContextManager(token_limit=200, compaction_threshold=0.8)
        messages = [Message(role="system", content="sys")]
        messages.extend(_make_big_messages(20, 40))  # ≈ 200 tokens > 160

        state = ConversationState(messages=messages)
        original_tokens = state.estimate_tokens()

        result = manager.compact(state, CompactionStage.AUTO)

        assert result["stage"] == "autocompaction"
        assert result["original_tokens"] == original_tokens
        assert result["new_tokens"] < original_tokens

    def test_compact_micro_removes_empty_messages(self):
        """MICRO 阶段应移除空消息。"""
        manager = ContextManager()

        messages: list[Message] = [
            Message(role="system", content="sys prompt"),
            Message(role="user", content=""),  # 空消息
            Message(role="assistant", content="hello"),
            Message(role="user", content=""),  # 空消息
            Message(role="assistant", content="world"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.MICRO)

        assert len(state.messages) == 3
        contents = [m.content for m in state.messages]
        assert "sys prompt" in contents
        assert "hello" in contents
        assert "world" in contents

    def test_compact_micro_truncates_long_tool_output(self):
        """MICRO 阶段应截断过长的工具输出。"""
        manager = ContextManager()

        long_content = "x" * 3000  # > 2000 字符
        messages: list[Message] = [
            Message(role="tool", content=long_content, tool_call_id="tc1"),
            Message(role="user", content="short"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.MICRO)

        tool_msg = next(m for m in state.messages if m.role == "tool")
        assert len(tool_msg.content) < 3000
        assert "[truncated]" in tool_msg.content
        assert tool_msg.metadata.get("truncated") is True

    def test_compact_micro_removes_duplicate_system_messages(self):
        """MICRO 阶段应移除重复的系统消息。"""
        manager = ContextManager()

        messages: list[Message] = [
            Message(role="system", content="same system"),
            Message(role="system", content="same system"),  # 重复
            Message(role="user", content="hello"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.MICRO)

        system_msgs = [m for m in state.messages if m.role == "system"]
        assert len(system_msgs) == 1

    def test_compact_reactive_more_aggressive_than_auto(self):
        """REACTIVE 阶段（50% 预算）应比 AUTO（80% 预算）保留更少消息。"""
        manager = ContextManager(token_limit=200, compaction_threshold=0.8)

        messages = [Message(role="system", content="sys")]
        messages.extend(_make_big_messages(20, 40))  # ≈ 200 tokens

        state_auto = ConversationState(messages=messages)
        manager.compact(state_auto, CompactionStage.AUTO)

        state_reactive = ConversationState(messages=messages)
        manager.compact(state_reactive, CompactionStage.REACTIVE)

        # REACTIVE 预算更低 → 压缩更激进 → 消息更少
        assert len(state_reactive.messages) <= len(state_auto.messages)

    def test_compact_reactive_with_llm_summarize(self):
        """REACTIVE 阶段有 LLM 时，被丢弃消息生成 LLM 摘要。"""
        def mock_summarize(text: str) -> str:
            return "reactive summary"

        manager = ContextManager(
            llm_summarize_handler=mock_summarize,
            token_limit=200,
            compaction_threshold=0.8,
        )

        messages = [Message(role="system", content="sys")]
        messages.extend(_make_big_messages(20, 40))

        state = ConversationState(messages=messages)
        result = manager.compact(state, CompactionStage.REACTIVE)

        assert result["stage"] == "reactive_compact"
        assert any("reactive summary" in m.content for m in state.messages)

    def test_compact_collapse_keeps_system_and_last_user(self):
        """COLLAPSE 阶段只保留系统消息 + Context Card + 最后一条用户消息。"""
        manager = ContextManager()

        messages: list[Message] = [
            Message(role="system", content="sys prompt"),
            Message(role="user", content="first user"),
            Message(role="assistant", content="first response"),
            Message(role="user", content="second user"),
            Message(role="assistant", content="second response"),
            Message(role="user", content="last user message"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.COLLAPSE)

        # 应只剩少量消息（system + card + last user）
        assert len(state.messages) <= 4

        # 第一个系统消息应保留
        system_msgs = [m for m in state.messages if m.role == "system"]
        assert any(m.content == "sys prompt" for m in system_msgs)

        # 最后一条用户消息应保留（且是唯一的 user 消息）
        user_msgs = [m for m in state.messages if m.role == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "last user message"

    def test_compact_collapse_with_llm_summary(self):
        """COLLAPSE 阶段有 LLM 时生成整体摘要。"""
        def mock_summarize(text: str) -> str:
            return "full conversation summary"

        manager = ContextManager(llm_summarize_handler=mock_summarize)

        messages: list[Message] = [
            Message(role="system", content="sys"),
            Message(role="user", content="do something"),
            Message(role="assistant", content="done"),
            Message(role="user", content="do more"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.COLLAPSE)

        summary_msgs = [
            m for m in state.messages
            if m.role == "system" and "[Conversation Summary" in m.content
        ]
        assert len(summary_msgs) == 1
        assert "full conversation summary" in summary_msgs[0].content

    def test_compact_collapse_empty_messages(self):
        """COLLAPSE 阶段处理空消息列表。"""
        manager = ContextManager()
        state = ConversationState(messages=[])
        result = manager.compact(state, CompactionStage.COLLAPSE)
        assert len(state.messages) == 0
        assert result["new_messages"] == 0

    def test_compact_collapse_llm_fallback_on_error(self):
        """COLLAPSE 阶段 LLM 异常时回退到结构化 Context Card。"""
        def failing_handler(text: str) -> str:
            raise RuntimeError("LLM error")

        manager = ContextManager(llm_summarize_handler=failing_handler)

        messages: list[Message] = [
            Message(role="system", content="sys"),
            Message(role="user", content="do something"),
            Message(role="assistant", content="done"),
            Message(role="user", content="more"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.COLLAPSE)

        # 应回退到结构化 Context Card
        assert any("[Context Card" in m.content for m in state.messages)

    def test_compact_records_history(self):
        """compact 应记录压缩历史。"""
        manager = ContextManager(token_limit=200000)

        messages: list[Message] = [Message(role="system", content="sys")]
        messages.extend(_make_messages(30))

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.AUTO)

        history = manager.compaction_history
        assert len(history) == 1
        assert history[0]["stage"] == "autocompaction"
        assert "original_messages" in history[0]
        assert "new_messages" in history[0]
        assert "reduction_pct" in history[0]

    def test_compact_multiple_stages_history(self):
        """多次不同阶段压缩应记录完整历史。"""
        manager = ContextManager()

        messages: list[Message] = [
            Message(role="system", content="sys"),
            Message(role="user", content="hello"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.MICRO)

        messages2 = [Message(role="system", content="sys")]
        messages2.extend(_make_messages(30))
        state2 = ConversationState(messages=messages2)
        manager.compact(state2, CompactionStage.AUTO)

        history = manager.compaction_history
        assert len(history) == 2
        assert history[0]["stage"] == "microcompaction"
        assert history[1]["stage"] == "autocompaction"

    def test_compaction_history_is_copy(self):
        """compaction_history 属性应返回副本，修改不影响内部状态。"""
        manager = ContextManager()
        messages = [Message(role="user", content="hello")]
        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.MICRO)

        history = manager.compaction_history
        history.clear()
        assert len(manager.compaction_history) == 1


class TestContextManagerForceCompact:
    """ContextManager.force_compact 测试。"""

    def test_force_compact_triggers_compaction(self):
        """force_compact 应强制执行压缩（忽略阈值检查），并实际减少 token。"""
        # token_limit=200 → AUTO 预算 160，消息 ≈ 200 tokens > 160 → 实际压缩
        manager = ContextManager(token_limit=200, compaction_threshold=0.8)

        messages: list[Message] = [Message(role="system", content="sys")]
        messages.extend(_make_big_messages(20, 40))

        state = ConversationState(messages=messages)
        original_tokens = state.estimate_tokens()

        result = manager.force_compact(state, CompactionStage.AUTO)

        assert result["stage"] == "autocompaction"
        assert state.estimate_tokens() < original_tokens

    def test_force_compact_with_collapse(self):
        """force_compact 可用 COLLAPSE 阶段。"""
        manager = ContextManager()

        messages: list[Message] = [
            Message(role="system", content="sys"),
            Message(role="user", content="task"),
            Message(role="assistant", content="response"),
        ]

        state = ConversationState(messages=messages)
        result = manager.force_compact(state, CompactionStage.COLLAPSE)

        assert result["stage"] == "context_collapse"
        assert len(state.messages) <= 3


class TestContextManagerCustomCondenser:
    """ContextManager 自定义 condenser 测试。"""

    def test_custom_condenser_used_in_auto(self):
        """AUTO 阶段应使用自定义 condenser。"""
        call_log: list[int] = []

        class CustomCondenser(Condenser):
            def condense(self, messages: list[Message]) -> list[Message]:
                call_log.append(len(messages))
                # 只保留最后 2 条
                return list(messages[-2:])

        manager = ContextManager(condenser=CustomCondenser())

        messages: list[Message] = [
            Message(role="system", content="sys"),
            Message(role="user", content="u1"),
            Message(role="assistant", content="a1"),
            Message(role="user", content="u2"),
            Message(role="assistant", content="a2"),
        ]

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.AUTO)

        assert len(call_log) == 1
        assert call_log[0] == 5
        assert len(state.messages) == 2

    def test_custom_condenser_in_auto_with_llm_handler(self):
        """ContextManager 可同时配置自定义 condenser 和 llm_summarize_handler。"""
        class CountingCondenser(Condenser):
            def __init__(self):
                self.call_count = 0

            def condense(self, messages: list[Message]) -> list[Message]:
                self.call_count += 1
                return [messages[0]] if messages else []

        condenser = CountingCondenser()
        manager = ContextManager(
            condenser=condenser,
            llm_summarize_handler=lambda t: "summary",
        )

        messages = [Message(role="system", content="sys")]
        messages.extend(_make_messages(10))

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.AUTO)

        assert condenser.call_count == 1


class TestContextManagerLLMSummarize:
    """ContextManager llm_summarize_handler 测试。"""

    def test_llm_summarize_in_reactive(self):
        """REACTIVE 阶段使用 llm_summarize_handler 对被丢弃消息生成摘要。"""
        summary_calls: list[str] = []

        def handler(text: str) -> str:
            summary_calls.append(text)
            return "reactive summary"

        manager = ContextManager(
            llm_summarize_handler=handler,
            token_limit=200,
            compaction_threshold=0.8,
        )

        messages: list[Message] = [Message(role="system", content="sys")]
        messages.extend(_make_big_messages(20, 40))

        state = ConversationState(messages=messages)
        manager.compact(state, CompactionStage.REACTIVE)

        assert len(summary_calls) == 1
        assert any("reactive summary" in m.content for m in state.messages)

    def test_llm_summarize_handler_inherited_attribute(self):
        """_llm_summarize_handler 属性应可被外部访问（subagent_manager 依赖）。"""
        handler = lambda t: "summary"  # noqa: E731
        manager = ContextManager(llm_summarize_handler=handler)
        assert manager._llm_summarize_handler is handler


# ── SubagentDefinition 测试 ─────────────────────────────────────


class TestSubagentDefinitionFromMarkdown:
    """SubagentDefinition.from_markdown 测试。"""

    def test_parse_with_frontmatter_and_system_prompt(self):
        """解析带 YAML frontmatter 和系统提示的 markdown。"""
        content = """---
name: code-reviewer
description: Reviews code for bugs and suggests improvements
tools: [read, grep, glob, ls]
model: inherit
max_turns: 20
---
You are a code reviewer. Analyze code for bugs, security issues,
and suggest improvements. Be concise and specific."""

        defn = SubagentDefinition.from_markdown(content)

        assert defn.name == "code-reviewer"
        assert defn.description == "Reviews code for bugs and suggests improvements"
        assert defn.tools == ["read", "grep", "glob", "ls"]
        assert defn.model == "inherit"
        assert defn.max_turns == 20
        assert "You are a code reviewer" in defn.system_prompt

    def test_parse_with_disallowed_tools(self):
        """解析带 disallowed_tools 的 frontmatter。"""
        content = """---
name: safe-agent
description: A safe agent
tools: [read, grep]
disallowed_tools: [write, delete]
---
Be safe."""

        defn = SubagentDefinition.from_markdown(content)

        assert defn.name == "safe-agent"
        assert defn.tools == ["read", "grep"]
        assert defn.disallowed_tools == ["write", "delete"]

    def test_parse_without_frontmatter(self):
        """无 frontmatter 时整个内容作为 description。"""
        content = "This is just a plain description with no frontmatter."

        defn = SubagentDefinition.from_markdown(content)

        assert defn.name == ""
        assert defn.description == "This is just a plain description with no frontmatter."
        assert defn.system_prompt == ""

    def test_parse_with_permission_mode(self):
        """解析 permission_mode 字段。"""
        content = """---
name: test-agent
description: test
permission_mode: plan
---
System prompt."""

        defn = SubagentDefinition.from_markdown(content)

        assert defn.permission_mode == "plan"

    def test_parse_defaults(self):
        """未指定的字段使用默认值。"""
        content = """---
name: minimal
description: minimal agent
---
Prompt."""

        defn = SubagentDefinition.from_markdown(content)

        assert defn.model == "inherit"
        assert defn.max_turns == 30
        assert defn.permission_mode == "inherit"
        assert defn.tools == []
        assert defn.disallowed_tools == []


class TestSubagentDefinitionToMarkdown:
    """SubagentDefinition.to_markdown 测试。"""

    def test_roundtrip(self):
        """to_markdown → from_markdown 往返应保持一致。"""
        original = SubagentDefinition(
            name="roundtrip-agent",
            description="A test agent for roundtrip",
            system_prompt="You are a test agent. Do your best.",
            tools=["read", "grep"],
            disallowed_tools=["delete"],
            model="sonnet",
            max_turns=15,
            permission_mode="default",
        )

        md = original.to_markdown()
        restored = SubagentDefinition.from_markdown(md)

        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.system_prompt == original.system_prompt
        assert restored.tools == original.tools
        assert restored.disallowed_tools == original.disallowed_tools
        assert restored.model == original.model
        assert restored.max_turns == original.max_turns
        assert restored.permission_mode == original.permission_mode

    def test_roundtrip_empty_fields(self):
        """空字段的往返也应正确。"""
        original = SubagentDefinition(
            name="empty",
            description="empty fields",
            system_prompt="",
            tools=[],
            disallowed_tools=[],
        )

        md = original.to_markdown()
        restored = SubagentDefinition.from_markdown(md)

        assert restored.name == "empty"
        assert restored.description == "empty fields"
        assert restored.system_prompt == ""
        assert restored.tools == []
        assert restored.disallowed_tools == []

    def test_to_markdown_starts_with_frontmatter(self):
        """to_markdown 输出应以 --- 开头。"""
        defn = SubagentDefinition(name="test", description="test desc")
        md = defn.to_markdown()
        assert md.startswith("---")


class TestSubagentDefinitionFromFile:
    """SubagentDefinition.from_file 测试。"""

    def test_load_from_md_file(self, tmp_path: Path):
        """从 .md 文件加载定义。"""
        content = """---
name: file-agent
description: Loaded from file
tools: [read]
---
You are a file-loaded agent."""

        file_path = tmp_path / "file-agent.md"
        file_path.write_text(content, encoding="utf-8")

        defn = SubagentDefinition.from_file(file_path)

        assert defn.name == "file-agent"
        assert defn.description == "Loaded from file"
        assert defn.tools == ["read"]
        assert "file-loaded agent" in defn.system_prompt

    def test_load_without_name_uses_stem(self, tmp_path: Path):
        """无 name 字段时使用文件名（stem）作为名称。"""
        content = """---
description: No name field
---
System prompt."""

        file_path = tmp_path / "stem-agent.md"
        file_path.write_text(content, encoding="utf-8")

        defn = SubagentDefinition.from_file(file_path)

        assert defn.name == "stem-agent"

    def test_load_plain_markdown_file(self, tmp_path: Path):
        """加载无 frontmatter 的纯 markdown 文件。"""
        content = "Just a plain description."

        file_path = tmp_path / "plain.md"
        file_path.write_text(content, encoding="utf-8")

        defn = SubagentDefinition.from_file(file_path)

        assert defn.name == "plain"  # 使用 stem
        assert defn.description == "Just a plain description."


# ── SubagentManager 测试 ────────────────────────────────────────


class TestSubagentManagerRegistration:
    """SubagentManager 注册和查询测试。"""

    def test_register_and_list_agents(self):
        """register 后 list_agents 应包含该定义。"""
        manager = SubagentManager()
        defn = SubagentDefinition(
            name="test-agent",
            description="A test agent",
        )
        manager.register(defn)

        agents = manager.list_agents()
        assert len(agents) == 1
        assert agents[0].name == "test-agent"

    def test_register_multiple(self):
        """注册多个 subagent。"""
        manager = SubagentManager()
        manager.register(SubagentDefinition(name="a", description="agent a"))
        manager.register(SubagentDefinition(name="b", description="agent b"))
        manager.register(SubagentDefinition(name="c", description="agent c"))

        agents = manager.list_agents()
        assert len(agents) == 3
        names = {a.name for a in agents}
        assert names == {"a", "b", "c"}

    def test_get_agent_existing(self):
        """get_agent 返回已注册的定义。"""
        manager = SubagentManager()
        defn = SubagentDefinition(name="findable", description="can find me")
        manager.register(defn)

        result = manager.get_agent("findable")
        assert result is not None
        assert result.name == "findable"

    def test_get_agent_nonexistent_returns_none(self):
        """get_agent 查找不存在的 agent 返回 None。"""
        manager = SubagentManager()
        assert manager.get_agent("nonexistent") is None

    def test_get_agent_returns_none_for_empty_manager(self):
        """空管理器 get_agent 返回 None。"""
        manager = SubagentManager()
        assert manager.get_agent("anything") is None


class TestSubagentManagerLoadFromDirectory:
    """SubagentManager.load_from_directory 测试。"""

    def test_load_multiple_md_files(self, tmp_path: Path):
        """从目录加载多个 .md 文件。"""
        (tmp_path / "agent1.md").write_text(
            "---\nname: agent-one\ndescription: first agent\n---\nPrompt 1.",
            encoding="utf-8",
        )
        (tmp_path / "agent2.md").write_text(
            "---\nname: agent-two\ndescription: second agent\n---\nPrompt 2.",
            encoding="utf-8",
        )
        (tmp_path / "agent3.md").write_text(
            "---\nname: agent-three\ndescription: third agent\n---\nPrompt 3.",
            encoding="utf-8",
        )

        manager = SubagentManager()
        count = manager.load_from_directory(tmp_path)

        assert count == 3
        assert len(manager.list_agents()) == 3
        assert manager.get_agent("agent-one") is not None
        assert manager.get_agent("agent-two") is not None
        assert manager.get_agent("agent-three") is not None

    def test_load_from_nonexistent_directory(self, tmp_path: Path):
        """从不存在的目录加载返回 0。"""
        manager = SubagentManager()
        count = manager.load_from_directory(tmp_path / "nonexistent")
        assert count == 0

    def test_load_from_empty_directory(self, tmp_path: Path):
        """从空目录加载返回 0。"""
        manager = SubagentManager()
        count = manager.load_from_directory(tmp_path)
        assert count == 0

    def test_load_skips_non_md_files(self, tmp_path: Path):
        """非 .md 文件应被跳过。"""
        (tmp_path / "agent.md").write_text(
            "---\nname: md-agent\ndescription: md\n---\nPrompt.",
            encoding="utf-8",
        )
        (tmp_path / "readme.txt").write_text("not a markdown", encoding="utf-8")
        (tmp_path / "config.yaml").write_text("key: value", encoding="utf-8")

        manager = SubagentManager()
        count = manager.load_from_directory(tmp_path)

        assert count == 1
        assert manager.get_agent("md-agent") is not None


class TestSubagentManagerMatchAgent:
    """SubagentManager.match_agent 测试。"""

    def test_keyword_matching(self):
        """根据关键词匹配 subagent。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="code-reviewer",
                description="Reviews code for bugs and security issues",
            )
        )
        manager.register(
            SubagentDefinition(
                name="file-organizer",
                description="Organizes files and directories",
            )
        )

        # 任务描述包含 code/reviews 相关词
        match = manager.match_agent("review code for security bugs")
        assert match == "code-reviewer"

    def test_match_returns_none_when_no_overlap(self):
        """无关键词重叠时返回 None。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="code-reviewer",
                description="Reviews code for bugs",
            )
        )

        match = manager.match_agent("cook dinner")
        assert match is None

    def test_match_returns_none_for_empty_manager(self):
        """空管理器匹配返回 None。"""
        manager = SubagentManager()
        assert manager.match_agent("anything") is None

    def test_match_picks_best_score(self):
        """选择关键词重叠最多的 agent。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="weak-match",
                description="code helper",
            )
        )
        manager.register(
            SubagentDefinition(
                name="strong-match",
                description="code review security bugs fix",
            )
        )

        match = manager.match_agent("review code for security bugs")
        assert match == "strong-match"


class TestSubagentManagerCreateIsolatedTools:
    """SubagentManager._create_isolated_tools 测试。"""

    def _make_parent_tools(self) -> "ToolRegistry":
        """创建包含多个工具的父注册表。"""
        from butler.core.agent_runtime.tool_registry import ToolRegistry

        registry = ToolRegistry()
        for name in ["read", "write", "delete", "grep", "glob"]:
            registry.register(
                handler=_make_tool_handler(),
                name=name,
                description=f"Tool {name}",
                parameters={"type": "object", "properties": {}, "required": []},
            )
        return registry

    def test_filter_by_tools_allow_list(self):
        """tools 允许列表应过滤工具。"""
        manager = SubagentManager()
        parent_tools = self._make_parent_tools()

        defn = SubagentDefinition(
            name="limited",
            description="limited agent",
            tools=["read", "grep"],
        )

        child_tools = manager._create_isolated_tools(parent_tools, defn)

        assert set(child_tools.list_names()) == {"read", "grep"}

    def test_filter_by_disallowed_tools(self):
        """disallowed_tools 拒绝列表应移除工具。"""
        manager = SubagentManager()
        parent_tools = self._make_parent_tools()

        defn = SubagentDefinition(
            name="safe",
            description="safe agent",
            disallowed_tools=["delete", "write"],
        )

        child_tools = manager._create_isolated_tools(parent_tools, defn)

        assert set(child_tools.list_names()) == {"read", "grep", "glob"}

    def test_disallowed_takes_precedence_over_allowed(self):
        """disallowed_tools 先评估，优先于 tools 允许列表。"""
        manager = SubagentManager()
        parent_tools = self._make_parent_tools()

        defn = SubagentDefinition(
            name="test",
            description="test",
            tools=["read", "write", "delete"],
            disallowed_tools=["write", "delete"],
        )

        child_tools = manager._create_isolated_tools(parent_tools, defn)

        # disallowed 先过滤，write 和 delete 被移除
        assert set(child_tools.list_names()) == {"read"}

    def test_empty_tools_inherits_all(self):
        """tools 为空列表时继承所有工具（减去 disallowed）。"""
        manager = SubagentManager()
        parent_tools = self._make_parent_tools()

        defn = SubagentDefinition(
            name="inherited",
            description="inherits all",
            tools=[],
        )

        child_tools = manager._create_isolated_tools(parent_tools, defn)

        assert set(child_tools.list_names()) == {"read", "write", "delete", "grep", "glob"}

    def test_empty_tools_and_empty_disallowed_inherits_all(self):
        """tools 和 disallowed 都为空时继承所有工具。"""
        manager = SubagentManager()
        parent_tools = self._make_parent_tools()

        defn = SubagentDefinition(
            name="all",
            description="all tools",
        )

        child_tools = manager._create_isolated_tools(parent_tools, defn)

        assert len(child_tools.list_names()) == 5


# ── SubagentManager delegate 测试 ───────────────────────────────


def _make_llm_handler(response: str = "done"):
    """生成一个返回指定响应的 LLM handler。"""
    def handler(**kwargs):
        return {
            "content": response,
            "tool_calls": [],
            "stop_reason": "end_turn",
        }
    return handler


def _make_parent_runtime(llm_handler=None):
    """创建一个 mock parent runtime，包含真实组件。"""
    from butler.core.agent_runtime.agent_runtime import AgentConfig
    from butler.core.agent_runtime.context_manager import ContextManager
    from butler.core.agent_runtime.event_stream import EventStream
    from butler.core.agent_runtime.permission import PermissionSystem
    from butler.core.agent_runtime.tool_registry import ToolRegistry

    if llm_handler is None:
        llm_handler = _make_llm_handler()

    config = AgentConfig(
        llm_call_handler=llm_handler,
        system_prompt="",
        max_turns=5,
    )

    tools = ToolRegistry()
    for name in ["read", "write", "grep"]:
        tools.register(
            handler=_make_tool_handler(),
            name=name,
            description=f"Tool {name}",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    permissions = PermissionSystem()
    context = ContextManager()
    events = EventStream()

    parent = MagicMock()
    parent.config = config
    parent.tools = tools
    parent.permissions = permissions
    parent.context = context
    parent.events = events

    return parent


class TestSubagentManagerDelegate:
    """SubagentManager.delegate 测试。"""

    def test_delegate_returns_result(self):
        """delegate 应返回子代理的执行结果。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="worker",
                description="a worker agent",
                system_prompt="You are a worker.",
                tools=["read"],
                max_turns=3,
            )
        )

        parent_runtime = _make_parent_runtime()
        result = manager.delegate(
            agent_name="worker",
            task="do something",
            parent_runtime=parent_runtime,
        )

        assert "response" in result
        assert result["response"] == "done"
        assert result["stop_reason"] == "end_turn"
        assert result["turns"] >= 1

    def test_delegate_emits_spawn_and_return_events(self):
        """delegate 应发出 SUBAGENT_SPAWN 和 SUBAGENT_RETURN 事件。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="worker",
                description="a worker agent",
                system_prompt="You are a worker.",
            )
        )

        parent_runtime = _make_parent_runtime()
        manager.delegate(
            agent_name="worker",
            task="do something",
            parent_runtime=parent_runtime,
        )

        spawn_events = parent_runtime.events.get_events_by_type(
            EventType.SUBAGENT_SPAWN
        )
        return_events = parent_runtime.events.get_events_by_type(
            EventType.SUBAGENT_RETURN
        )

        assert len(spawn_events) == 1
        assert spawn_events[0].data["agent_name"] == "worker"
        assert spawn_events[0].data["task"] == "do something"
        assert spawn_events[0].data["depth"] == 1

        assert len(return_events) == 1
        assert return_events[0].data["agent_name"] == "worker"
        assert return_events[0].data["response"] == "done"

    def test_delegate_tracks_depth(self):
        """delegate 应正确跟踪嵌套深度。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="worker",
                description="a worker agent",
                system_prompt="You are a worker.",
            )
        )

        captured_depths: list[int] = []

        def depth_tracking_handler(**kwargs):
            captured_depths.append(manager.depth)
            return {
                "content": "done",
                "tool_calls": [],
                "stop_reason": "end_turn",
            }

        parent_runtime = _make_parent_runtime(llm_handler=depth_tracking_handler)

        # 执行前深度为 0
        assert manager.depth == 0

        manager.delegate(
            agent_name="worker",
            task="do something",
            parent_runtime=parent_runtime,
        )

        # 执行中深度应为 1
        assert len(captured_depths) >= 1
        assert captured_depths[0] == 1

        # 执行后深度恢复为 0
        assert manager.depth == 0

    def test_delegate_unregistered_agent_raises_keyerror(self):
        """委托未注册的 agent 应抛出 KeyError。"""
        manager = SubagentManager()
        parent_runtime = _make_parent_runtime()

        with pytest.raises(KeyError, match="not registered"):
            manager.delegate(
                agent_name="nonexistent",
                task="do something",
                parent_runtime=parent_runtime,
            )

    def test_delegate_max_nesting_depth_raises_runtime_error(self):
        """超过最大嵌套深度应抛出 RuntimeError。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="worker",
                description="a worker agent",
                system_prompt="You are a worker.",
            )
        )

        # 设置深度为最大值
        manager._depth = 5

        parent_runtime = _make_parent_runtime()

        with pytest.raises(RuntimeError, match="Maximum nesting depth"):
            manager.delegate(
                agent_name="worker",
                task="do something",
                parent_runtime=parent_runtime,
            )

        # 深度应未改变（因为检查在增加深度之前）
        assert manager._depth == 5

    def test_delegate_depth_restored_on_error(self):
        """delegate 出错后深度应恢复（子代理内部捕获错误时，深度仍应恢复）。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="worker",
                description="a worker agent",
                system_prompt="You are a worker.",
            )
        )

        def failing_handler(**kwargs):
            raise RuntimeError("LLM failed")

        parent_runtime = _make_parent_runtime(llm_handler=failing_handler)

        # 即使子代理运行出错，深度也应恢复
        # 注意：AgentRuntime.run 内部捕获 LLM 异常，返回 stop_reason=error
        result = manager.delegate(
            agent_name="worker",
            task="do something",
            parent_runtime=parent_runtime,
        )

        # 子代理因错误终止
        assert result["stop_reason"] == "error"
        # 深度应恢复为 0（finally 块确保恢复）
        assert manager.depth == 0

        # 应有 SUBAGENT_RETURN 事件（即使子代理出错，delegate 仍会发出返回事件）
        return_events = parent_runtime.events.get_events_by_type(
            EventType.SUBAGENT_RETURN
        )
        assert len(return_events) == 1
        assert return_events[0].data["stop_reason"] == "error"

    def test_delegate_creates_isolated_tools(self):
        """delegate 应为子代理创建隔离的工具集。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="limited-worker",
                description="a limited worker",
                system_prompt="You are a worker.",
                tools=["read"],  # 只允许 read
                disallowed_tools=["write"],
            )
        )

        parent_runtime = _make_parent_runtime()
        result = manager.delegate(
            agent_name="limited-worker",
            task="do something",
            parent_runtime=parent_runtime,
        )

        # 子代理应成功执行（即使只有 read 工具）
        assert result["stop_reason"] == "end_turn"

    def test_delegate_spawns_with_correct_depth(self):
        """delegate 发出的 spawn 事件应包含正确的深度。"""
        manager = SubagentManager()
        manager.register(
            SubagentDefinition(
                name="worker",
                description="a worker",
                system_prompt="You are a worker.",
            )
        )

        # 模拟已经在深度 2
        manager._depth = 2

        parent_runtime = _make_parent_runtime()
        manager.delegate(
            agent_name="worker",
            task="nested task",
            parent_runtime=parent_runtime,
        )

        spawn_events = parent_runtime.events.get_events_by_type(
            EventType.SUBAGENT_SPAWN
        )
        assert len(spawn_events) == 1
        # 深度应为当前深度 + 1 = 3
        assert spawn_events[0].data["depth"] == 3

        # 深度应恢复
        assert manager.depth == 2
