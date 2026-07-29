"""
Agent Runtime 端到端集成测试。

验证完整的 Agent 循环：用户输入 → LLM → 工具调用 → 权限检查 → 执行 → 结果反馈 → 最终回复。
使用 mock LLM handler 模拟真实的工具调用流程。
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from butler.core.agent_runtime import (
    AgentConfig,
    AgentRuntime,
    CompactionStage,
    ContextManager,
    EventStream,
    EventType,
    Message,
    PermissionLevel,
    PermissionSystem,
    StopReason,
    SubagentDefinition,
    SubagentManager,
    ToolCall,
    ToolRegistry,
)
from butler.core.agent_runtime.builtin_tools import (
    PersistentShell,
    register_builtin_tools,
)
from butler.core.agent_runtime.permission import (
    PermissionDecision,
    PermissionMode,
)


# ── 辅助函数 ──────────────────────────────────────────────────

def make_tool_call_dict(call_id: str, name: str, arguments: dict) -> dict:
    """构造 OpenAI 格式的 tool_call 字典。"""
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        },
    }


def create_mock_llm(responses: list[dict]):
    """
    创建 mock LLM handler，按顺序返回预设响应。

    每个 response 是一个 dict:
        {"content": "...", "tool_calls": [...], "stop_reason": "..."}
    """
    call_count = [0]

    def handler(messages, tools, **kwargs):
        idx = call_count[0]
        if idx >= len(responses):
            # 超出预设响应后返回空回复终止循环
            return {"content": "Done.", "tool_calls": [], "stop_reason": "end_turn"}
        resp = responses[idx]
        call_count[0] += 1
        return resp

    return handler


# ── 端到端测试 ──────────────────────────────────────────────────


class TestSimpleConversation:
    """测试简单对话流程（无工具调用）。"""

    def test_simple_text_response(self, tmp_path):
        """LLM 直接返回文本回复，无工具调用。"""
        llm = create_mock_llm([
            {"content": "Hello! How can I help you?", "tool_calls": [], "stop_reason": "end_turn"},
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(
                system_prompt="You are a helpful assistant.",
                llm_call_handler=llm,
                max_turns=5,
            ),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Hi there")

        assert result["response"] == "Hello! How can I help you?"
        assert result["stop_reason"] == StopReason.END_TURN.value
        assert result["turns"] == 1

        # 验证事件流
        events = result["events"]
        message_events = [e for e in events if e.type == EventType.MESSAGE]
        assert len(message_events) >= 2  # user + assistant

    def test_empty_llm_response(self, tmp_path):
        """LLM 返回空内容时仍正常终止。"""
        llm = create_mock_llm([
            {"content": "", "tool_calls": [], "stop_reason": "end_turn"},
        ])

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=3),
            tool_registry=ToolRegistry(),
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("test")
        assert result["stop_reason"] == StopReason.END_TURN.value
        assert result["turns"] == 1


class TestToolCallFlow:
    """测试工具调用完整流程。"""

    def test_single_tool_call_then_respond(self, tmp_path):
        """LLM 调用一个工具，然后给出最终回复。"""
        llm = create_mock_llm([
            # 第一轮：调用 write 工具
            {
                "content": "I'll create the file for you.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "write", {
                        "path": "hello.py",
                        "content": "print('Hello, World!')",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            # 第二轮：给出最终回复
            {
                "content": "I've created hello.py with a print statement.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        # 使用 auto_confirm 避免权限阻塞
        perm = PermissionSystem()
        perm.set_mode(PermissionMode.BYPASS_PERMISSIONS)

        runtime = AgentRuntime(
            config=AgentConfig(
                system_prompt="You are a coding assistant.",
                llm_call_handler=llm,
                max_turns=10,
            ),
            tool_registry=registry,
            permission_system=perm,
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Create a file called hello.py")

        assert result["stop_reason"] == StopReason.END_TURN.value
        assert result["turns"] == 2
        assert "hello.py" in result["response"]

        # 验证文件确实被创建
        created_file = tmp_path / "hello.py"
        assert created_file.exists()
        assert "Hello, World!" in created_file.read_text()

        # 验证事件流包含工具调用和结果
        events = result["events"]
        tool_call_events = [e for e in events if e.type == EventType.TOOL_CALL]
        tool_result_events = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(tool_call_events) == 1
        assert tool_call_events[0].data["tool_name"] == "write"
        assert len(tool_result_events) == 1
        assert tool_result_events[0].data["success"] is True

    def test_multiple_tool_calls_in_one_turn(self, tmp_path):
        """LLM 在一轮中调用多个工具。"""
        # 先创建两个文件供读取
        (tmp_path / "a.txt").write_text("content A")
        (tmp_path / "b.txt").write_text("content B")

        llm = create_mock_llm([
            {
                "content": "Let me read both files.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "read", {"path": "a.txt"}),
                    make_tool_call_dict("tc2", "read", {"path": "b.txt"}),
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": "I read both files. A contains 'content A' and B contains 'content B'.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=10),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Read both files")

        assert result["stop_reason"] == StopReason.END_TURN.value
        assert result["turns"] == 2

        events = result["events"]
        tool_results = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(tool_results) == 2
        assert tool_results[0].data["success"] is True
        assert tool_results[1].data["success"] is True

    def test_tool_not_found(self, tmp_path):
        """LLM 调用不存在的工具。"""
        llm = create_mock_llm([
            {
                "content": "Let me use a non-existent tool.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "nonexistent_tool", {"arg": "value"}),
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": "The tool doesn't exist. Let me try something else.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=10),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Use nonexistent tool")

        assert result["stop_reason"] == StopReason.END_TURN.value

        events = result["events"]
        error_events = [e for e in events if e.type == EventType.TOOL_ERROR]
        assert len(error_events) == 1
        assert "not found" in error_events[0].data.get("error", "").lower()

    def test_self_healing_on_tool_failure(self, tmp_path):
        """工具失败时自愈逻辑触发，将错误信息加入对话。"""
        llm = create_mock_llm([
            # 第一轮：尝试读取不存在的文件
            {
                "content": "Let me read that file.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "read", {"path": "nonexistent.py"}),
                ],
                "stop_reason": "tool_use",
            },
            # 第二轮：LLM 看到错误后给出最终回复
            {
                "content": "The file doesn't exist. Would you like me to create it?",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(
                llm_call_handler=llm,
                max_turns=10,
                enable_self_healing=True,
            ),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Read nonexistent.py")

        assert result["stop_reason"] == StopReason.END_TURN.value
        assert result["turns"] == 2

        # 自愈消息应被加入对话
        events = result["events"]
        tool_errors = [e for e in events if e.type == EventType.TOOL_ERROR]
        assert len(tool_errors) == 1
        assert "not found" in tool_errors[0].data["error"].lower() or "File not found" in tool_errors[0].data["error"]


class TestPermissionFlow:
    """测试权限系统在 Agent 循环中的行为。"""

    def test_permission_denied_blocks_tool(self, tmp_path):
        """权限被拒绝时工具不执行。"""
        llm = create_mock_llm([
            {
                "content": "I'll write to the file.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "write", {
                        "path": "test.py",
                        "content": "test",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": "Permission was denied.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        # DONT_ASK 模式：静默拒绝非允许操作
        perm = PermissionSystem()
        perm.set_mode(PermissionMode.DONT_ASK)

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=10),
            tool_registry=registry,
            permission_system=perm,
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Write test.py")

        # 文件不应被创建
        assert not (tmp_path / "test.py").exists()

        events = result["events"]
        perm_responses = [e for e in events if e.type == EventType.PERMISSION_RESPONSE]
        assert any(r.data.get("decision") == "deny" for r in perm_responses)

    def test_auto_confirm_approves_tool(self, tmp_path):
        """auto_confirm_handler 返回 True 时工具被批准执行。"""
        llm = create_mock_llm([
            {
                "content": "I'll create the file.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "write", {
                        "path": "approved.py",
                        "content": "print('approved')",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": "File created successfully.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(
                llm_call_handler=llm,
                max_turns=10,
                auto_confirm_handler=lambda name, args: True,
            ),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Create approved.py")

        assert (tmp_path / "approved.py").exists()

        events = result["events"]
        perm_requests = [e for e in events if e.type == EventType.PERMISSION_REQUEST]
        perm_responses = [e for e in events if e.type == EventType.PERMISSION_RESPONSE]
        assert len(perm_requests) == 1
        assert any(r.data.get("decision") == "user_approved" for r in perm_responses)

    def test_auto_confirm_denies_tool(self, tmp_path):
        """auto_confirm_handler 返回 False 时工具被拒绝。"""
        llm = create_mock_llm([
            {
                "content": "I'll try to write.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "write", {
                        "path": "denied.py",
                        "content": "test",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": "Permission denied by user.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(
                llm_call_handler=llm,
                max_turns=10,
                auto_confirm_handler=lambda name, args: False,
            ),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Write denied.py")

        assert not (tmp_path / "denied.py").exists()

        events = result["events"]
        perm_responses = [e for e in events if e.type == EventType.PERMISSION_RESPONSE]
        assert any(r.data.get("decision") == "user_denied" for r in perm_responses)


class TestContextCompactionInLoop:
    """测试 Agent 循环中的上下文压缩。"""

    def test_compaction_triggered_during_loop(self, tmp_path):
        """当 token 数超过阈值时自动触发压缩。"""
        # 构造大量对话内容以触发压缩
        long_content = "A" * 1000  # 每条消息 250 tokens (1000/4)

        responses = []
        # 第一轮：工具调用
        responses.append({
            "content": long_content,
            "tool_calls": [
                make_tool_call_dict("tc1", "read", {"path": "."}),
            ],
            "stop_reason": "tool_use",
        })
        # 第二轮：最终回复
        responses.append({
            "content": "Done.",
            "tool_calls": [],
            "stop_reason": "end_turn",
        })

        llm = create_mock_llm(responses)

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        # 设置极低的 token 限制以触发压缩
        ctx_manager = ContextManager(
            token_limit=100,  # 极低限制
            compaction_threshold=0.5,
        )

        runtime = AgentRuntime(
            config=AgentConfig(
                llm_call_handler=llm,
                max_turns=10,
                context_token_limit=100,
                compaction_threshold=0.5,
            ),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ctx_manager,
            event_stream=EventStream(),
        )

        result = runtime.run(long_content)

        # 应该有压缩事件
        events = result["events"]
        compaction_events = [e for e in events if e.type == EventType.COMPACTION]
        assert len(compaction_events) >= 1


class TestBuiltinToolsIntegration:
    """测试内置工具在 Agent 循环中的集成。"""

    def test_read_write_edit_flow(self, tmp_path):
        """完整的文件操作流程：写入 → 读取 → 编辑。"""
        llm = create_mock_llm([
            # 1. 写入文件
            {
                "content": "Creating the file.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "write", {
                        "path": "target.py",
                        "content": "def hello():\n    pass\n",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            # 2. 读取文件
            {
                "content": "Reading the file.",
                "tool_calls": [
                    make_tool_call_dict("tc2", "read", {"path": "target.py"}),
                ],
                "stop_reason": "tool_use",
            },
            # 3. 编辑文件
            {
                "content": "Editing the file.",
                "tool_calls": [
                    make_tool_call_dict("tc3", "edit", {
                        "path": "target.py",
                        "old_string": "    pass",
                        "new_string": "    return 'hello'",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            # 4. 最终回复
            {
                "content": "File created, read, and edited successfully.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        perm = PermissionSystem()
        perm.set_mode(PermissionMode.BYPASS_PERMISSIONS)

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=10),
            tool_registry=registry,
            permission_system=perm,
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Create, read, and edit target.py")

        assert result["stop_reason"] == StopReason.END_TURN.value
        assert result["turns"] == 4

        # 验证文件内容
        final_content = (tmp_path / "target.py").read_text()
        assert "return 'hello'" in final_content
        assert "pass" not in final_content

    def test_bash_tool_execution(self, tmp_path):
        """Bash 工具执行命令。"""
        llm = create_mock_llm([
            {
                "content": "Running a command.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "bash", {
                        "command": "echo 'hello from bash'",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": "Command executed successfully.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        perm = PermissionSystem()
        perm.set_mode(PermissionMode.BYPASS_PERMISSIONS)

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=10),
            tool_registry=registry,
            permission_system=perm,
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Run echo command")

        assert result["stop_reason"] == StopReason.END_TURN.value

        events = result["events"]
        tool_results = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(tool_results) == 1
        assert "hello from bash" in tool_results[0].data["content"]

    def test_glob_and_grep_tools(self, tmp_path):
        """Glob 和 Grep 工具搜索文件。"""
        # 创建测试文件
        (tmp_path / "module.py").write_text("def foo():\n    pass\n")
        (tmp_path / "other.txt").write_text("not python")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "helper.py").write_text("def bar():\n    return 42\n")

        llm = create_mock_llm([
            # Glob 查找所有 .py 文件
            {
                "content": "Finding Python files.",
                "tool_calls": [
                    make_tool_call_dict("tc1", "glob", {"pattern": "*.py"}),
                ],
                "stop_reason": "tool_use",
            },
            # Grep 搜索函数定义
            {
                "content": "Searching for function definitions.",
                "tool_calls": [
                    make_tool_call_dict("tc2", "grep", {
                        "pattern": "def \\w+",
                        "include": "*.py",
                    }),
                ],
                "stop_reason": "tool_use",
            },
            # 最终回复
            {
                "content": "Found Python files and function definitions.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=10),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Find Python files and search for functions")

        assert result["stop_reason"] == StopReason.END_TURN.value
        assert result["turns"] == 3

        events = result["events"]
        tool_results = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(tool_results) == 2
        # Glob 结果包含 .py 文件
        assert "module.py" in tool_results[0].data["content"]
        # Grep 结果包含函数定义
        assert "def foo" in tool_results[1].data["content"] or "def bar" in tool_results[1].data["content"]


class TestSubagentDelegation:
    """测试子代理委托在完整循环中的行为。"""

    def test_subagent_delegation_flow(self, tmp_path):
        """Agent 委托任务给子代理。"""
        # 子代理的 LLM handler
        subagent_llm = create_mock_llm([
            {"content": "Subagent review complete. No issues found.", "tool_calls": [], "stop_reason": "end_turn"},
        ])

        # 主代理的 LLM handler
        main_llm = create_mock_llm([
            # 主代理决定委托给子代理
            {
                "content": "I'll delegate this to the code reviewer.",
                "tool_calls": [],  # 实际委托通过 SubagentManager.delegate()
                "stop_reason": "end_turn",
            },
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=main_llm, max_turns=5),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        # 手动执行委托
        sub_manager = SubagentManager()
        sub_manager.register(SubagentDefinition(
            name="code-reviewer",
            description="Reviews code for bugs",
            system_prompt="You are a code reviewer.",
            tools=["read", "grep", "glob"],
            max_turns=5,
        ))

        # 覆盖子代理的 LLM handler
        runtime.config.llm_call_handler = subagent_llm

        result = sub_manager.delegate(
            agent_name="code-reviewer",
            task="Review the code",
            parent_runtime=runtime,
        )

        assert result["stop_reason"] == StopReason.END_TURN.value
        assert "No issues found" in result["response"]

        # 验证事件流包含 spawn 和 return 事件
        events = runtime.events.events
        spawn_events = [e for e in events if e.type == EventType.SUBAGENT_SPAWN]
        return_events = [e for e in events if e.type == EventType.SUBAGENT_RETURN]
        assert len(spawn_events) == 1
        assert spawn_events[0].data["agent_name"] == "code-reviewer"
        assert len(return_events) == 1
        assert return_events[0].data["agent_name"] == "code-reviewer"


class TestStatePersistence:
    """测试对话状态持久化和恢复。"""

    def test_save_and_load_state(self, tmp_path):
        """保存和恢复对话状态。"""
        llm = create_mock_llm([
            {"content": "Hello!", "tool_calls": [], "stop_reason": "end_turn"},
        ])

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(
                llm_call_handler=llm,
                max_turns=5,
                system_prompt="You are a test assistant.",
            ),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        runtime.run("Test message")

        # 保存状态
        state_file = tmp_path / "state.json"
        runtime.save_state(str(state_file))
        assert state_file.exists()

        # 加载状态
        runtime2 = AgentRuntime(
            config=AgentConfig(llm_call_handler=llm, max_turns=5),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )
        runtime2.load_state(str(state_file))

        assert runtime2.state is not None
        assert len(runtime2.state.messages) > 0
        # 第一条消息应该是 system 提示
        assert runtime2.state.messages[0].role == "system"
        # 包含 user 消息
        user_msgs = [m for m in runtime2.state.messages if m.role == "user"]
        assert len(user_msgs) >= 1

    def test_event_stream_persistence(self, tmp_path):
        """事件流持久化到文件。"""
        from butler.core.agent_runtime.types import Event

        stream = EventStream()
        stream.emit(Event.create(EventType.MESSAGE, role="user", content="hello"))

        events_file = tmp_path / "events.json"
        stream.save_to_file(str(events_file))
        assert events_file.exists()

        # 加载
        loaded = EventStream.load_from_file(str(events_file))
        assert len(loaded) == len(stream)
        loaded_events = loaded.events
        assert loaded_events[0].type == EventType.MESSAGE


class TestMaxTurnsLimit:
    """测试最大轮次限制。"""

    def test_max_turns_reached(self, tmp_path):
        """LLM 持续调用工具直到达到最大轮次。"""
        # LLM 每轮都调用工具，永不终止
        def looping_llm(messages, tools, **kwargs):
            return {
                "content": "Continuing...",
                "tool_calls": [
                    make_tool_call_dict("tc1", "ls", {"path": "."}),
                ],
                "stop_reason": "tool_use",
            }

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=str(tmp_path))

        runtime = AgentRuntime(
            config=AgentConfig(
                llm_call_handler=looping_llm,
                max_turns=3,
            ),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("Keep going")

        assert result["stop_reason"] == StopReason.MAX_TURNS.value
        assert result["turns"] == 3

    def test_llm_error_stops_loop(self, tmp_path):
        """LLM 调用异常时循环终止。"""
        def error_llm(messages, tools, **kwargs):
            raise RuntimeError("LLM service unavailable")

        registry = ToolRegistry()

        runtime = AgentRuntime(
            config=AgentConfig(llm_call_handler=error_llm, max_turns=5),
            tool_registry=registry,
            permission_system=PermissionSystem(),
            context_manager=ContextManager(),
            event_stream=EventStream(),
        )

        result = runtime.run("test")

        assert result["stop_reason"] == StopReason.ERROR.value

        events = result["events"]
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) >= 1
        assert "LLM service unavailable" in error_events[0].data.get("error", "")


class TestPersistentShell:
    """测试持久 Shell 会话。"""

    def test_shell_cwd_persistence(self, tmp_path):
        """Shell 的 cd 命令在调用间持久。"""
        shell = PersistentShell(cwd=str(tmp_path))

        # 执行 cd 到子目录
        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()
        shell.execute(f"cd {sub_dir}")

        # 验证 cwd 已更新
        assert shell.cwd == str(sub_dir.resolve())

        # 后续命令在新的 cwd 下执行
        result = shell.execute("pwd")
        assert str(sub_dir.resolve()) in result["stdout"]

    def test_shell_env_persistence(self, tmp_path):
        """Shell 环境变量在同一命令内有效。"""
        shell = PersistentShell(cwd=str(tmp_path))

        # export + echo 在同一命令中执行
        result = shell.execute("export MY_VAR=test_value && echo $MY_VAR")

        assert "test_value" in result["stdout"]

    def test_shell_history(self, tmp_path):
        """Shell 命令历史记录。"""
        shell = PersistentShell(cwd=str(tmp_path))

        shell.execute("echo first")
        shell.execute("echo second")

        history = shell.history
        assert len(history) == 2
        assert "echo first" in history[0]["command"]
        assert "echo second" in history[1]["command"]

    def test_shell_timeout(self, tmp_path):
        """Shell 命令超时处理。"""
        shell = PersistentShell(cwd=str(tmp_path), timeout=1)

        result = shell.execute("sleep 5")

        assert result["returncode"] == -1
        assert "timed out" in result["stderr"].lower()
