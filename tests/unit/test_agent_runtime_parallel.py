"""并行工具执行测试。

覆盖：
- 多个并发安全工具在同一轮内并行执行
- 非并发安全工具严格串行，并阻断其后的并行批次
- 结果顺序与 LLM 给出的 tool_call 顺序一致
- 单个工具超时不影响同批其他结果
"""

from __future__ import annotations

import json
import threading
import time

from butler.core.agent_runtime.agent_runtime import AgentConfig, AgentRuntime
from butler.core.agent_runtime.context_manager import ContextManager
from butler.core.agent_runtime.event_stream import EventStream
from butler.core.agent_runtime.permission import PermissionSystem
from butler.core.agent_runtime.tool_registry import ToolRegistry
from butler.core.agent_runtime.types import PermissionLevel


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


def _register_sleep_tool(
    registry: ToolRegistry,
    name: str,
    delay: float,
    *,
    safe: bool,
    log: list[tuple[str, str, float]] | None = None,
):
    lock = threading.Lock()

    def handler(arguments: dict, **ctx) -> dict:
        start = time.monotonic()
        if log is not None:
            with lock:
                log.append((name, "start", start))
        time.sleep(delay)
        if log is not None:
            with lock:
                log.append((name, "end", time.monotonic()))
        return {"success": True, "content": f"{name}-done"}

    registry.register(
        handler=handler,
        name=name,
        description=f"sleep {delay}s",
        parameters={"type": "object", "properties": {}},
        permission_level=PermissionLevel.ALWAYS_ALLOW if safe else PermissionLevel.REQUIRE_CONFIRM,
        is_read_only=safe,
        is_concurrency_safe=safe,
    )


def test_concurrency_safe_tools_run_in_parallel_and_keep_order():
    registry = ToolRegistry()
    _register_sleep_tool(registry, "read_a", 0.2, safe=True)
    _register_sleep_tool(registry, "read_b", 0.2, safe=True)
    _register_sleep_tool(registry, "read_c", 0.2, safe=True)

    calls = {"n": 0}

    def handler(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "content": "",
                "stop_reason": "tool_calls",
                "tool_calls": [
                    _tool_call("read_a", {}, "c1"),
                    _tool_call("read_b", {}, "c2"),
                    _tool_call("read_c", {}, "c3"),
                ],
            }
        return {"content": "done", "stop_reason": "end_turn", "tool_calls": []}

    runtime = _runtime(registry, handler, max_parallel_tools=3)

    start = time.monotonic()
    result = runtime.run("read all")
    elapsed = time.monotonic() - start

    assert result["stop_reason"] == "end_turn"
    # 串行至少 0.6s；并行应接近 0.2s，留足余量避免 CI 抖动。
    assert elapsed < 0.5

    tool_events = [e for e in result["events"] if e.type.value == "tool_result"]
    assert [e.data["tool_call_id"] for e in tool_events] == ["c1", "c2", "c3"]


def test_unsafe_tool_blocks_following_parallel_batch():
    registry = ToolRegistry()
    log: list[tuple[str, str, float]] = []
    _register_sleep_tool(registry, "read_one", 0.1, safe=True, log=log)
    _register_sleep_tool(registry, "write_one", 0.1, safe=False, log=log)
    _register_sleep_tool(registry, "read_two", 0.1, safe=True, log=log)

    calls = {"n": 0}

    def handler(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "content": "",
                "stop_reason": "tool_calls",
                "tool_calls": [
                    _tool_call("read_one", {}, "c1"),
                    _tool_call("write_one", {}, "c2"),
                    _tool_call("read_two", {}, "c3"),
                ],
            }
        return {"content": "done", "stop_reason": "end_turn", "tool_calls": []}

    runtime = _runtime(registry, handler, max_parallel_tools=3)
    runtime.run("mixed")

    marks = {(name, phase): ts for name, phase, ts in log}
    # 写操作必须等前面的只读批次全部结束；后面的只读批次必须等写操作结束。
    assert marks[("write_one", "start")] >= marks[("read_one", "end")]
    assert marks[("read_two", "start")] >= marks[("write_one", "end")]


def test_tool_timeout_does_not_block_other_results():
    registry = ToolRegistry()
    _register_sleep_tool(registry, "slow_read", 0.5, safe=True)
    _register_sleep_tool(registry, "fast_read", 0.01, safe=True)

    calls = {"n": 0}

    def handler(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "content": "",
                "stop_reason": "tool_calls",
                "tool_calls": [
                    _tool_call("slow_read", {}, "slow"),
                    _tool_call("fast_read", {}, "fast"),
                ],
            }
        return {"content": "done", "stop_reason": "end_turn", "tool_calls": []}

    runtime = _runtime(
        registry,
        handler,
        max_parallel_tools=2,
        tool_execution_timeout=0.1,
    )
    result = runtime.run("timeout please")

    assert result["stop_reason"] == "end_turn"

    tool_events = {e.data["tool_call_id"]: e for e in result["events"] if e.type.value in ("tool_result", "tool_error")}
    assert tool_events["slow"].data["success"] is False
    assert "timed out" in tool_events["slow"].data["error"]
    assert tool_events["fast"].data["success"] is True
    assert tool_events["fast"].data["content"] == "fast_read-done"
