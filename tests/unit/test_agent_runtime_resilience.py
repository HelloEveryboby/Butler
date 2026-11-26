"""Agent 循环健壮性测试。

覆盖：
- finish_reason="stop" 但带 tool_calls 时仍然执行工具
- 上下文超限错误触发压缩并重试
- 取消请求返回 user_interrupt
- 自愈提示追加在整轮 tool 消息之后（消息序列合法）
- token 估算计入工具调用参数
"""

from __future__ import annotations

import json

from butler.core.agent_runtime.agent_runtime import AgentConfig, AgentRuntime
from butler.core.agent_runtime.context_manager import ContextManager
from butler.core.agent_runtime.event_stream import EventStream
from butler.core.agent_runtime.permission import PermissionSystem
from butler.core.agent_runtime.tool_registry import ToolRegistry
from butler.core.agent_runtime.types import (
    ConversationState,
    EventType,
    Message,
    PermissionLevel,
    StopReason,
    ToolCall,
)


def _tool_call(name: str, arguments: dict, call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _runtime(registry: ToolRegistry, handler, **config_kwargs) -> AgentRuntime:
    return AgentRuntime(
        config=AgentConfig(
            max_turns=config_kwargs.pop("max_turns", 5),
            llm_call_handler=handler,
            auto_confirm_handler=lambda name, args: True,
            **config_kwargs,
        ),
        tool_registry=registry,
        permission_system=PermissionSystem(),
        context_manager=ContextManager(token_limit=100000),
        event_stream=EventStream(),
    )


def _register_echo(registry: ToolRegistry, name: str = "echo", *, raises: bool = False):
    def handler(arguments: dict, **ctx) -> dict:
        if raises:
            raise RuntimeError("boom")
        return {"success": True, "content": f"echo:{arguments.get('text', '')}"}

    registry.register(
        handler=handler,
        name=name,
        description="echo",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
        is_concurrency_safe=True,
    )


def test_tool_calls_are_executed_even_when_finish_reason_is_stop():
    registry = ToolRegistry()
    _register_echo(registry)
    calls = {"n": 0}

    def handler(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # 部分 OpenAI 兼容服务会这样返回
            return {
                "content": "",
                "stop_reason": "stop",
                "tool_calls": [_tool_call("echo", {"text": "hi"}, "c1")],
            }
        return {"content": "done", "stop_reason": "stop", "tool_calls": []}

    runtime = _runtime(registry, handler)
    result = runtime.run("go")

    assert result["turns"] == 2
    assert result["stop_reason"] == "end_turn"
    assert any(
        e.type == EventType.TOOL_RESULT and "echo:hi" in e.data.get("content", "")
        for e in result["events"]
    )


def test_context_error_triggers_compaction_and_retry():
    registry = ToolRegistry()

    def handler(messages, tools, **kwargs):
        handler.calls += 1
        if handler.calls == 1:
            raise RuntimeError("This model's maximum context length is 8192 tokens")
        return {"content": "recovered", "stop_reason": "end_turn", "tool_calls": []}

    handler.calls = 0

    runtime = _runtime(registry, handler, max_context_retries=1)
    result = runtime.run("long task")

    assert handler.calls == 2
    assert result["stop_reason"] == "end_turn"
    assert result["response"] == "recovered"
    assert any(e.type == EventType.COMPACTION for e in result["events"])


def test_cancel_returns_user_interrupt():
    registry = ToolRegistry()
    _register_echo(registry)
    holder: dict[str, AgentRuntime] = {}

    def handler(messages, tools, **kwargs):
        holder["runtime"].request_cancel()
        return {
            "content": "",
            "stop_reason": "tool_calls",
            "tool_calls": [_tool_call("echo", {"text": "hi"}, "c1")],
        }

    runtime = _runtime(registry, handler)
    holder["runtime"] = runtime
    result = runtime.run("cancel me")

    assert result["stop_reason"] == StopReason.USER_INTERRUPT.value
    assert result["turns"] == 1


def test_self_healing_message_appended_after_all_tool_results():
    registry = ToolRegistry()
    _register_echo(registry, "good", raises=False)
    _register_echo(registry, "bad", raises=True)
    calls = {"n": 0}

    def handler(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "content": "",
                "stop_reason": "tool_calls",
                "tool_calls": [
                    _tool_call("bad", {"text": "x"}, "c_bad"),
                    _tool_call("good", {"text": "y"}, "c_good"),
                ],
            }
        # 校验失败提示必须位于所有 tool 消息之后
        assert messages[-1]["role"] == "user"
        assert messages[-2]["role"] == "tool"
        assert messages[-3]["role"] == "tool"
        return {"content": "done", "stop_reason": "end_turn", "tool_calls": []}

    runtime = _runtime(registry, handler)
    result = runtime.run("mixed")

    roles = [m.role for m in runtime.state.messages]
    assert roles == ["user", "assistant", "tool", "tool", "user", "assistant"]
    assert result["stop_reason"] == "end_turn"


def test_token_estimate_includes_tool_call_arguments():
    state = ConversationState()
    state.append(
        Message(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="c1", name="write", arguments={"content": "x" * 400}),
            ],
        )
    )

    # 400+ 字符的工具参数必须计入，否则长任务会低估上下文
    assert state.estimate_tokens() > 50
