"""断点续跑测试。

覆盖：
- checkpoint 每轮落盘，恢复后不重复执行已完成的工具
- 恢复后的消息与事件历史都保留
- 未指定 session_id 时自动选择最近的 checkpoint
"""

from __future__ import annotations

import json
from pathlib import Path

from butler.core.agent_runtime.agent_runtime import AgentConfig, AgentRuntime
from butler.core.agent_runtime.context_manager import ContextManager
from butler.core.agent_runtime.event_stream import EventStream
from butler.core.agent_runtime.permission import PermissionSystem
from butler.core.agent_runtime.tool_registry import ToolRegistry
from butler.core.agent_runtime.types import EventType, PermissionLevel


def _tool_call(name: str, arguments: dict, call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _build_runtime(checkpoint_dir: str, handler, max_turns: int) -> tuple[AgentRuntime, list[str]]:
    registry = ToolRegistry()
    executed: list[str] = []

    def echo(arguments: dict, **ctx) -> dict:
        executed.append(str(arguments.get("text", "")))
        return {"success": True, "content": f"echo:{arguments.get('text', '')}"}

    registry.register(
        handler=echo,
        name="echo",
        description="echo text",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
        is_concurrency_safe=True,
    )

    runtime = AgentRuntime(
        config=AgentConfig(
            max_turns=max_turns,
            checkpoint_dir=checkpoint_dir,
            llm_call_handler=handler,
            auto_confirm_handler=lambda name, args: True,
        ),
        tool_registry=registry,
        permission_system=PermissionSystem(),
        context_manager=ContextManager(token_limit=100000),
        event_stream=EventStream(),
    )
    return runtime, executed


def test_resume_does_not_rerun_completed_tools(tmp_path):
    sessions = str(tmp_path / "sessions")

    first_calls = {"n": 0}

    def first_handler(messages, tools, **kwargs):
        first_calls["n"] += 1
        return {
            "content": "",
            "stop_reason": "tool_calls",
            "tool_calls": [_tool_call("echo", {"text": "step1"}, "c1")],
        }

    runtime1, executed1 = _build_runtime(sessions, first_handler, max_turns=1)
    result1 = runtime1.run("start", session_id="session_a")

    assert result1["stop_reason"] == "max_turns"
    session_dir = Path(sessions) / "session_a"
    assert (session_dir / "state.json").exists()
    assert (session_dir / "events.json").exists()
    assert executed1 == ["step1"]

    second_calls = {"n": 0}

    def second_handler(messages, tools, **kwargs):
        second_calls["n"] += 1
        return {"content": "finished", "stop_reason": "end_turn", "tool_calls": []}

    runtime2, executed2 = _build_runtime(sessions, second_handler, max_turns=3)
    result2 = runtime2.run("continue", session_id="session_a", resume=True)

    assert result2["stop_reason"] == "end_turn"
    assert result2["response"] == "finished"
    # 已完成的工具不会重新执行
    assert executed2 == []
    assert first_calls["n"] == 1
    assert second_calls["n"] == 1

    restored_messages = runtime2.state.messages
    assert restored_messages[0].role == "user"
    assert restored_messages[0].content == "start"
    assert any(m.role == "tool" and "echo:step1" in m.content for m in restored_messages)
    assert any(m.content == "continue" for m in restored_messages)
    assert restored_messages[-1].content == "finished"

    # 历史事件被恢复，新事件继续追加
    event_types = [e.type for e in result2["events"]]
    assert EventType.TOOL_RESULT in event_types
    assert event_types[-1] == EventType.STOP


def test_resume_picks_latest_session_when_id_omitted(tmp_path):
    sessions = str(tmp_path / "sessions")

    def handler(messages, tools, **kwargs):
        return {"content": "ok", "stop_reason": "end_turn", "tool_calls": []}

    runtime1, _ = _build_runtime(sessions, handler, max_turns=1)
    runtime1.run("hello", session_id="latest")

    runtime2, _ = _build_runtime(sessions, handler, max_turns=1)
    result = runtime2.run("again", resume=True)

    assert result["session_id"] == "latest"
    assert result["stop_reason"] == "end_turn"
    assert any(m.content == "hello" for m in runtime2.state.messages)
