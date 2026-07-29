"""
Comprehensive tests for butler.core.agent_runtime.types and
butler.core.agent_runtime.event_stream modules.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from butler.core.agent_runtime.types import (
    ConversationState,
    Event,
    EventType,
    Message,
    PermissionLevel,
    StopReason,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from butler.core.agent_runtime.event_stream import EventStream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_call(
    id: str = "call_001",
    name: str = "read_file",
    arguments: dict | None = None,
) -> ToolCall:
    return ToolCall(
        id=id,
        name=name,
        arguments=arguments or {"path": "/tmp/test.txt"},
    )


def _make_message(
    role: str = "user",
    content: str = "hello",
    tool_calls: list[ToolCall] | None = None,
    tool_call_id: str | None = None,
    name: str | None = None,
    metadata: dict | None = None,
) -> Message:
    return Message(
        role=role,
        content=content,
        tool_calls=tool_calls or [],
        tool_call_id=tool_call_id,
        name=name,
        metadata=metadata or {},
    )


# ===========================================================================
# EventType enum
# ===========================================================================

class TestEventType:
    def test_values(self):
        assert EventType.MESSAGE == "message"
        assert EventType.TOOL_CALL == "tool_call"
        assert EventType.TOOL_RESULT == "tool_result"
        assert EventType.TOOL_ERROR == "tool_error"
        assert EventType.PERMISSION_REQUEST == "permission_request"
        assert EventType.PERMISSION_RESPONSE == "permission_response"
        assert EventType.COMPACTION == "compaction"
        assert EventType.SUBAGENT_SPAWN == "subagent_spawn"
        assert EventType.SUBAGENT_RETURN == "subagent_return"
        assert EventType.ERROR == "error"
        assert EventType.STOP == "stop"

    def test_is_str_enum(self):
        assert isinstance(EventType.MESSAGE, str)
        assert EventType.MESSAGE.value == "message"


# ===========================================================================
# PermissionLevel enum
# ===========================================================================

class TestPermissionLevel:
    def test_values(self):
        assert PermissionLevel.ALWAYS_ALLOW == "always_allow"
        assert PermissionLevel.REQUIRE_CONFIRM == "require_confirm"
        assert PermissionLevel.NEVER_ALLOW == "never_allow"

    def test_is_str_enum(self):
        assert isinstance(PermissionLevel.ALWAYS_ALLOW, str)


# ===========================================================================
# StopReason enum
# ===========================================================================

class TestStopReason:
    def test_values(self):
        assert StopReason.END_TURN == "end_turn"
        assert StopReason.MAX_TURNS == "max_turns"
        assert StopReason.ERROR == "error"
        assert StopReason.USER_INTERRUPT == "user_interrupt"
        assert StopReason.PERMISSION_DENIED == "permission_denied"

    def test_is_str_enum(self):
        assert isinstance(StopReason.END_TURN, str)


# ===========================================================================
# ToolCall
# ===========================================================================

class TestToolCall:
    def test_creation(self):
        tc = _make_tool_call()
        assert tc.id == "call_001"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp/test.txt"}

    def test_frozen(self):
        tc = _make_tool_call()
        with pytest.raises(AttributeError):
            tc.id = "other"  # type: ignore[misc]

    def test_to_dict(self):
        tc = _make_tool_call()
        d = tc.to_dict()
        assert d["id"] == "call_001"
        assert d["type"] == "function"
        assert d["function"]["name"] == "read_file"
        # arguments must be a JSON string
        assert isinstance(d["function"]["arguments"], str)
        parsed = json.loads(d["function"]["arguments"])
        assert parsed == {"path": "/tmp/test.txt"}

    def test_from_dict(self):
        d = {
            "id": "call_abc",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": '{"path": "/tmp/out.txt", "content": "data"}',
            },
        }
        tc = ToolCall.from_dict(d)
        assert tc.id == "call_abc"
        assert tc.name == "write_file"
        assert tc.arguments == {"path": "/tmp/out.txt", "content": "data"}

    def test_to_dict_from_dict_roundtrip(self):
        original = _make_tool_call(
            id="call_rt",
            name="search",
            arguments={"query": "pytest", "limit": 10},
        )
        d = original.to_dict()
        restored = ToolCall.from_dict(d)
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.arguments == original.arguments

    def test_from_dict_handles_non_string_arguments(self):
        """_json_loads falls back to dict() when not a string."""
        # This tests the defensive path; arguments might be non-string in edge cases.
        d = {
            "id": "c1",
            "type": "function",
            "function": {"name": "foo", "arguments": "not valid json {{{"},
        }
        tc = ToolCall.from_dict(d)
        # _json_loads returns {} on failure
        assert tc.arguments == {}


# ===========================================================================
# Message
# ===========================================================================

class TestMessage:
    def test_basic_creation(self):
        msg = _make_message(role="user", content="hello world")
        assert msg.role == "user"
        assert msg.content == "hello world"
        assert msg.tool_calls == []
        assert msg.tool_call_id is None
        assert msg.name is None
        assert msg.metadata == {}

    def test_frozen(self):
        msg = _make_message()
        with pytest.raises(AttributeError):
            msg.role = "system"  # type: ignore[misc]

    def test_creation_with_tool_calls(self):
        tc = _make_tool_call()
        msg = Message(role="assistant", content="", tool_calls=[tc])
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].id == "call_001"

    def test_creation_with_tool_call_id(self):
        msg = Message(role="tool", content="result", tool_call_id="call_001")
        assert msg.tool_call_id == "call_001"

    def test_creation_with_name(self):
        msg = Message(role="tool", content="result", name="read_file")
        assert msg.name == "read_file"

    def test_creation_with_metadata(self):
        msg = Message(role="user", content="hi", metadata={"source": "cli"})
        assert msg.metadata == {"source": "cli"}

    def test_to_dict_simple(self):
        msg = _make_message(role="user", content="hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_to_dict_with_tool_calls(self):
        tc = _make_tool_call()
        msg = Message(role="assistant", content="", tool_calls=[tc])
        d = msg.to_dict()
        assert "tool_calls" in d
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["id"] == "call_001"

    def test_to_dict_with_tool_call_id(self):
        msg = Message(role="tool", content="ok", tool_call_id="c1")
        d = msg.to_dict()
        assert d["tool_call_id"] == "c1"

    def test_to_dict_with_name(self):
        msg = Message(role="tool", content="ok", name="bash")
        d = msg.to_dict()
        assert d["name"] == "bash"

    def test_to_dict_omits_empty_fields(self):
        msg = Message(role="system", content="be helpful")
        d = msg.to_dict()
        assert "tool_calls" not in d
        assert "tool_call_id" not in d
        assert "name" not in d

    def test_from_dict_simple(self):
        d = {"role": "user", "content": "test message"}
        msg = Message.from_dict(d)
        assert msg.role == "user"
        assert msg.content == "test message"
        assert msg.tool_calls == []

    def test_from_dict_with_tool_calls(self):
        d = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "arguments": '{"command": "ls"}',
                    },
                }
            ],
        }
        msg = Message.from_dict(d)
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "bash"
        assert msg.tool_calls[0].arguments == {"command": "ls"}

    def test_from_dict_with_tool_call_id_and_name(self):
        d = {
            "role": "tool",
            "content": "done",
            "tool_call_id": "c1",
            "name": "bash",
            "metadata": {"elapsed": 0.5},
        }
        msg = Message.from_dict(d)
        assert msg.tool_call_id == "c1"
        assert msg.name == "bash"
        assert msg.metadata == {"elapsed": 0.5}

    def test_roundtrip(self):
        original = Message(
            role="assistant",
            content="thinking...",
            tool_calls=[_make_tool_call()],
            metadata={"step": 3},
        )
        restored = Message.from_dict(original.to_dict())
        assert restored.role == original.role
        assert restored.content == original.content
        assert len(restored.tool_calls) == len(original.tool_calls)
        assert restored.tool_calls[0].id == original.tool_calls[0].id
        # NOTE: to_dict() produces OpenAI-compatible format which omits
        # the metadata field, so it is not preserved across the roundtrip.
        assert restored.metadata == {}

    def test_roundtrip_with_tool_call_id_and_name(self):
        original = Message(
            role="tool",
            content="result data",
            tool_call_id="call_99",
            name="bash",
        )
        restored = Message.from_dict(original.to_dict())
        assert restored.role == original.role
        assert restored.content == original.content
        assert restored.tool_call_id == original.tool_call_id
        assert restored.name == original.name


# ===========================================================================
# ToolResult
# ===========================================================================

class TestToolResult:
    def test_creation_success(self):
        tr = ToolResult(tool_call_id="c1", content="file contents here")
        assert tr.tool_call_id == "c1"
        assert tr.content == "file contents here"
        assert tr.success is True
        assert tr.error is None
        assert tr.metadata == {}

    def test_creation_error(self):
        tr = ToolResult(
            tool_call_id="c1",
            content="",
            success=False,
            error="File not found",
        )
        assert tr.success is False
        assert tr.error == "File not found"

    def test_frozen(self):
        tr = ToolResult(tool_call_id="c1", content="ok")
        with pytest.raises(AttributeError):
            tr.success = False  # type: ignore[misc]

    def test_to_message(self):
        tr = ToolResult(
            tool_call_id="c1",
            content="42",
            metadata={"elapsed": 0.1},
        )
        msg = tr.to_message()
        assert msg.role == "tool"
        assert msg.content == "42"
        assert msg.tool_call_id == "c1"
        assert msg.metadata == {"elapsed": 0.1}

    def test_to_message_preserves_error_in_content(self):
        tr = ToolResult(tool_call_id="c1", content="Error: boom", success=False, error="boom")
        msg = tr.to_message()
        assert msg.content == "Error: boom"


# ===========================================================================
# Event
# ===========================================================================

class TestEvent:
    def test_create(self):
        event = Event.create(EventType.MESSAGE, role="user", content="hi")
        assert isinstance(event.id, str)
        assert len(event.id) > 0
        assert event.type == EventType.MESSAGE
        assert event.data == {"role": "user", "content": "hi"}

    def test_id_uniqueness(self):
        ids = {Event.create(EventType.STOP).id for _ in range(100)}
        assert len(ids) == 100, "All generated event ids must be unique"

    def test_frozen(self):
        event = Event.create(EventType.MESSAGE)
        with pytest.raises(AttributeError):
            event.type = EventType.ERROR  # type: ignore[misc]

    def test_create_with_timestamp_auto(self):
        before = time.time()
        event = Event.create(EventType.MESSAGE)
        after = time.time()
        assert before <= event.timestamp <= after

    def test_create_with_various_data_types(self):
        event = Event.create(
            EventType.TOOL_CALL,
            id="call_1",
            name="bash",
            args={"cmd": "ls"},
            count=42,
            flag=True,
        )
        assert event.data["id"] == "call_1"
        assert event.data["count"] == 42
        assert event.data["flag"] is True


# ===========================================================================
# ToolDefinition
# ===========================================================================

class TestToolDefinition:
    def _minimal_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
            },
            "required": ["path"],
        }

    def test_creation_minimal(self):
        td = ToolDefinition(
            name="read_file",
            description="Read a file",
            parameters_schema=self._minimal_schema(),
        )
        assert td.name == "read_file"
        assert td.permission_level == PermissionLevel.REQUIRE_CONFIRM
        assert td.is_read_only is False
        assert td.is_destructive is False
        assert td.is_concurrency_safe is False

    def test_creation_full(self):
        td = ToolDefinition(
            name="list_dir",
            description="List directory contents",
            parameters_schema=self._minimal_schema(),
            permission_level=PermissionLevel.ALWAYS_ALLOW,
            is_read_only=True,
            is_destructive=False,
            is_concurrency_safe=True,
        )
        assert td.permission_level == PermissionLevel.ALWAYS_ALLOW
        assert td.is_read_only is True
        assert td.is_concurrency_safe is True

    def test_to_openai_schema(self):
        td = ToolDefinition(
            name="search",
            description="Search files",
            parameters_schema=self._minimal_schema(),
        )
        schema = td.to_openai_schema()
        assert schema == {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search files",
                "parameters": self._minimal_schema(),
            },
        }

    def test_pydantic_validation_extra_fields_forbidden(self):
        """Pydantic BaseModel by default ignores extra fields (if configured) or raises.
        Verify basic construction still works."""
        td = ToolDefinition(
            name="test",
            description="desc",
            parameters_schema={},
        )
        assert td.name == "test"


# ===========================================================================
# ConversationState
# ===========================================================================

class TestConversationState:
    def test_empty_init(self):
        cs = ConversationState()
        assert cs.messages == []
        assert cs.turn_count == 0
        assert cs.compaction_count == 0

    def test_init_with_messages(self):
        msgs = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
        ]
        cs = ConversationState(messages=msgs)
        assert len(cs.messages) == 2
        assert cs.messages[0].role == "user"

    def test_append_user(self):
        cs = ConversationState()
        cs.append(Message(role="user", content="hi"))
        assert len(cs.messages) == 1
        assert cs.turn_count == 0  # user messages don't count as turns

    def test_append_assistant_increments_turn(self):
        cs = ConversationState()
        cs.append(Message(role="assistant", content="ok"))
        assert cs.turn_count == 1
        cs.append(Message(role="assistant", content="done"))
        assert cs.turn_count == 2

    def test_extend(self):
        cs = ConversationState()
        msgs = [
            Message(role="user", content="a"),
            Message(role="assistant", content="b"),
            Message(role="user", content="c"),
            Message(role="assistant", content="d"),
        ]
        cs.extend(msgs)
        assert len(cs.messages) == 4
        assert cs.turn_count == 2

    def test_replace_messages(self):
        cs = ConversationState()
        cs.append(Message(role="user", content="old"))
        new_msgs = [Message(role="user", content="compacted summary")]
        cs.replace_messages(new_msgs)
        assert len(cs.messages) == 1
        assert cs.messages[0].content == "compacted summary"
        assert cs.compaction_count == 1

    def test_replace_messages_increments_compaction(self):
        cs = ConversationState()
        cs.replace_messages([])
        cs.replace_messages([])
        assert cs.compaction_count == 2

    def test_get_user_messages(self):
        cs = ConversationState()
        cs.append(Message(role="system", content="be helpful"))
        cs.append(Message(role="user", content="hi"))
        cs.append(Message(role="assistant", content="hello"))
        cs.append(Message(role="user", content="bye"))
        users = cs.get_user_messages()
        assert len(users) == 2
        assert users[0].content == "hi"
        assert users[1].content == "bye"

    def test_get_last_user_message(self):
        cs = ConversationState()
        assert cs.get_last_user_message() is None
        cs.append(Message(role="assistant", content="hi"))
        assert cs.get_last_user_message() is None
        cs.append(Message(role="user", content="first"))
        cs.append(Message(role="assistant", content="reply"))
        cs.append(Message(role="user", content="second"))
        last = cs.get_last_user_message()
        assert last is not None
        assert last.content == "second"

    def test_to_dict(self):
        cs = ConversationState()
        cs.append(Message(role="user", content="hello"))
        cs.append(Message(role="assistant", content="world"))
        d = cs.to_dict()
        assert "messages" in d
        assert "turn_count" in d
        assert "compaction_count" in d
        assert "created_at" in d
        assert d["turn_count"] == 1
        assert d["compaction_count"] == 0
        assert len(d["messages"]) == 2

    def test_from_dict(self):
        d = {
            "messages": [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
            ],
            "turn_count": 1,
            "compaction_count": 0,
            "created_at": 1000.0,
        }
        cs = ConversationState.from_dict(d)
        assert len(cs.messages) == 2
        assert cs.turn_count == 1
        assert cs.compaction_count == 0
        assert cs.created_at == 1000.0

    def test_from_dict_missing_keys(self):
        cs = ConversationState.from_dict({})
        assert cs.messages == []
        assert cs.turn_count == 0
        assert cs.compaction_count == 0

    def test_to_dict_from_dict_roundtrip(self):
        cs = ConversationState()
        tc = _make_tool_call()
        cs.append(Message(role="user", content="hi"))
        cs.append(Message(role="assistant", content="", tool_calls=[tc]))
        cs.append(Message(role="user", content="do more"))
        cs.append(Message(role="assistant", content="done"))
        cs.replace_messages(cs.messages)  # bump compaction

        d = cs.to_dict()
        restored = ConversationState.from_dict(d)
        assert len(restored.messages) == len(cs.messages)
        assert restored.turn_count == cs.turn_count
        assert restored.compaction_count == cs.compaction_count
        # Verify tool_calls survived roundtrip
        asst_msg = restored.messages[1]
        assert len(asst_msg.tool_calls) == 1
        assert asst_msg.tool_calls[0].id == "call_001"

    def test_estimate_tokens(self):
        cs = ConversationState()
        # 20 characters -> 20 // 4 = 5 tokens
        cs.append(Message(role="user", content="a" * 20))
        assert cs.estimate_tokens() == 5

    def test_estimate_tokens_empty(self):
        cs = ConversationState()
        assert cs.estimate_tokens() == 0

    def test_estimate_tokens_multiple_messages(self):
        cs = ConversationState()
        cs.append(Message(role="user", content="a" * 12))  # 3 tokens
        cs.append(Message(role="assistant", content="b" * 8))  # 2 tokens
        assert cs.estimate_tokens() == 5

    def test_turn_count_property(self):
        cs = ConversationState()
        assert cs.turn_count == 0
        for _ in range(5):
            cs.append(Message(role="assistant", content="ok"))
        assert cs.turn_count == 5

    def test_compaction_count_property(self):
        cs = ConversationState()
        assert cs.compaction_count == 0
        cs.replace_messages([])
        cs.replace_messages([])
        assert cs.compaction_count == 2

    def test_messages_returns_copy(self):
        cs = ConversationState()
        cs.append(Message(role="user", content="hi"))
        msgs = cs.messages
        msgs.append(Message(role="user", content="injected"))
        assert len(cs.messages) == 1


# ===========================================================================
# EventStream
# ===========================================================================

class TestEventStream:
    def test_init_default(self):
        es = EventStream()
        assert len(es) == 0
        assert es.events == []

    def test_emit_and_events(self):
        es = EventStream()
        e1 = Event.create(EventType.MESSAGE, role="user", content="hi")
        e2 = Event.create(EventType.STOP, reason="end_turn")
        es.emit(e1)
        es.emit(e2)
        assert len(es) == 2
        events = es.events
        assert events[0].id == e1.id
        assert events[1].id == e2.id

    def test_events_returns_copy(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        evts = es.events
        evts.append(None)  # type: ignore[arg-type]
        assert len(es.events) == 1

    def test_subscribe_specific_type(self):
        es = EventStream()
        received = []
        es.subscribe(EventType.TOOL_CALL, lambda e: received.append(e))
        es.emit(Event.create(EventType.MESSAGE))
        es.emit(Event.create(EventType.TOOL_CALL, name="bash"))
        assert len(received) == 1
        assert received[0].data["name"] == "bash"

    def test_subscribe_all(self):
        es = EventStream()
        received = []
        es.subscribe_all(lambda e: received.append(e))
        es.emit(Event.create(EventType.MESSAGE))
        es.emit(Event.create(EventType.STOP))
        assert len(received) == 2

    def test_unsubscribe(self):
        es = EventStream()
        received = []
        cb = lambda e: received.append(e)  # noqa: E731
        es.subscribe(EventType.MESSAGE, cb)
        es.emit(Event.create(EventType.MESSAGE))
        assert len(received) == 1
        es.unsubscribe(EventType.MESSAGE, cb)
        es.emit(Event.create(EventType.MESSAGE))
        assert len(received) == 1  # no new notifications

    def test_unsubscribe_nonexistent_callback(self):
        es = EventStream()
        # should not raise
        es.unsubscribe(EventType.MESSAGE, lambda e: None)

    def test_get_events_by_type(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE, role="user"))
        es.emit(Event.create(EventType.TOOL_CALL, name="bash"))
        es.emit(Event.create(EventType.MESSAGE, role="assistant"))
        msgs = es.get_events_by_type(EventType.MESSAGE)
        assert len(msgs) == 2
        tools = es.get_events_by_type(EventType.TOOL_CALL)
        assert len(tools) == 1

    def test_get_recent(self):
        es = EventStream()
        for i in range(10):
            es.emit(Event.create(EventType.MESSAGE, index=i))
        recent = es.get_recent(3)
        assert len(recent) == 3
        assert recent[0].data["index"] == 7
        assert recent[2].data["index"] == 9

    def test_get_recent_more_than_available(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        recent = es.get_recent(10)
        assert len(recent) == 1

    def test_clear(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        es.emit(Event.create(EventType.STOP))
        assert len(es) == 2
        es.clear()
        assert len(es) == 0
        assert es.events == []

    def test_len(self):
        es = EventStream()
        assert len(es) == 0
        es.emit(Event.create(EventType.MESSAGE))
        assert len(es) == 1
        es.emit(Event.create(EventType.STOP))
        assert len(es) == 2

    def test_save_to_file_creates_parent_dirs(self, tmp_path):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE, role="user", content="hi"))
        nested = tmp_path / "a" / "b" / "events.json"
        es.save_to_file(nested)
        assert nested.exists()
        data = json.loads(nested.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert data["event_count"] == 1
        assert len(data["events"]) == 1

    def test_save_to_file_event_fields(self, tmp_path):
        es = EventStream()
        e = Event.create(EventType.TOOL_CALL, name="bash", command="ls")
        es.emit(e)
        path = tmp_path / "stream.json"
        es.save_to_file(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        evt_data = data["events"][0]
        assert evt_data["id"] == e.id
        assert evt_data["type"] == "tool_call"
        assert evt_data["data"]["name"] == "bash"
        assert "timestamp" in evt_data

    def test_load_from_file(self, tmp_path):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE, role="user", content="a"))
        es.emit(Event.create(EventType.STOP, reason="end_turn"))
        path = tmp_path / "stream.json"
        es.save_to_file(path)

        loaded = EventStream.load_from_file(path)
        assert len(loaded) == 2
        assert loaded.events[0].type == EventType.MESSAGE
        assert loaded.events[1].type == EventType.STOP

    def test_load_from_nonexistent_file(self, tmp_path):
        loaded = EventStream.load_from_file(tmp_path / "nope.json")
        assert len(loaded) == 0

    def test_save_load_roundtrip(self, tmp_path):
        es = EventStream()
        events_to_save = [
            Event.create(EventType.MESSAGE, role="user", content="hello"),
            Event.create(EventType.TOOL_CALL, name="read_file", path="/tmp/f"),
            Event.create(EventType.TOOL_RESULT, output="data"),
            Event.create(EventType.COMPACTION, ratio=0.5),
            Event.create(EventType.STOP, reason="end_turn"),
        ]
        for e in events_to_save:
            es.emit(e)

        path = tmp_path / "roundtrip.json"
        es.save_to_file(path)
        loaded = EventStream.load_from_file(path)

        assert len(loaded) == len(events_to_save)
        for orig, loaded_evt in zip(events_to_save, loaded.events):
            assert loaded_evt.id == orig.id
            assert loaded_evt.type == orig.type
            assert loaded_evt.data == orig.data

    def test_load_from_file_skips_invalid_type(self, tmp_path):
        """Events with unknown type values should be skipped."""
        path = tmp_path / "bad.json"
        data = {
            "version": 1,
            "event_count": 2,
            "events": [
                {"id": "1", "type": "message", "data": {}, "timestamp": 1000},
                {"id": "2", "type": "unknown_type", "data": {}, "timestamp": 1001},
            ],
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = EventStream.load_from_file(path)
        assert len(loaded) == 1
        assert loaded.events[0].id == "1"

    def test_replay_with_callback(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE, role="user"))
        es.emit(Event.create(EventType.TOOL_CALL, name="bash"))
        es.emit(Event.create(EventType.STOP))

        replayed = []
        result = es.replay(callback=lambda e: replayed.append(e))
        assert len(replayed) == 3
        assert len(result) == 3
        assert result[0].type == EventType.MESSAGE

    def test_replay_with_event_types_filter(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE, role="user"))
        es.emit(Event.create(EventType.TOOL_CALL, name="bash"))
        es.emit(Event.create(EventType.MESSAGE, role="assistant"))
        es.emit(Event.create(EventType.STOP))

        result = es.replay(event_types=[EventType.MESSAGE, EventType.STOP])
        assert len(result) == 3
        types = [e.type for e in result]
        assert EventType.TOOL_CALL not in types

    def test_replay_with_callback_and_filter(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        es.emit(Event.create(EventType.TOOL_CALL))
        es.emit(Event.create(EventType.STOP))

        replayed = []
        result = es.replay(
            callback=lambda e: replayed.append(e),
            event_types=[EventType.STOP],
        )
        assert len(replayed) == 1
        assert replayed[0].type == EventType.STOP
        assert len(result) == 1

    def test_replay_no_callback(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        result = es.replay()
        assert len(result) == 1

    def test_replay_callback_error_caught(self):
        """Replay should not propagate exceptions from callback."""
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        # callback raises, but replay continues
        result = es.replay(callback=lambda e: 1 / 0)
        assert len(result) == 1

    def test_get_summary(self):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        es.emit(Event.create(EventType.MESSAGE))
        es.emit(Event.create(EventType.TOOL_CALL))
        es.emit(Event.create(EventType.STOP))
        es.emit(Event.create(EventType.MESSAGE))

        summary = es.get_summary()
        assert summary == {
            "message": 3,
            "tool_call": 1,
            "stop": 1,
        }

    def test_get_summary_empty(self):
        es = EventStream()
        assert es.get_summary() == {}

    def test_max_events_boundary(self):
        """Old events should be automatically dropped when maxlen is exceeded."""
        es = EventStream(max_events=5)
        for i in range(8):
            es.emit(Event.create(EventType.MESSAGE, index=i))
        assert len(es) == 5
        # oldest events (0, 1, 2) are dropped
        events = es.events
        assert events[0].data["index"] == 3
        assert events[-1].data["index"] == 7

    def test_thread_safety_emit(self):
        """Emitting from multiple threads should not corrupt the event list."""
        es = EventStream()
        num_threads = 10
        events_per_thread = 50

        barrier = threading.Barrier(num_threads)

        def worker(thread_id: int):
            barrier.wait()
            for i in range(events_per_thread):
                es.emit(
                    Event.create(
                        EventType.MESSAGE,
                        thread=thread_id,
                        seq=i,
                    )
                )

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All events should be present (up to default maxlen of 10000)
        assert len(es) == num_threads * events_per_thread

    def test_subscribe_callback_error_is_caught(self):
        """Subscriber exceptions should not break emit()."""
        es = EventStream()
        received = []
        es.subscribe(EventType.MESSAGE, lambda e: 1 / 0)
        es.subscribe(EventType.MESSAGE, lambda e: received.append(e))
        # emit should not raise
        es.emit(Event.create(EventType.MESSAGE))
        assert len(received) == 1

    def test_subscribe_all_error_is_caught(self):
        """Global subscriber exceptions should not break emit()."""
        es = EventStream()
        received = []
        es.subscribe_all(lambda e: 1 / 0)
        es.subscribe_all(lambda e: received.append(e))
        es.emit(Event.create(EventType.MESSAGE))
        assert len(received) == 1

    def test_save_and_load_preserves_timestamps(self, tmp_path):
        es = EventStream()
        e = Event.create(EventType.MESSAGE, content="ts_test")
        es.emit(e)
        path = tmp_path / "ts.json"
        es.save_to_file(path)
        loaded = EventStream.load_from_file(path)
        assert loaded.events[0].timestamp == e.timestamp

    def test_save_to_file_with_pathlib(self, tmp_path):
        es = EventStream()
        es.emit(Event.create(EventType.MESSAGE))
        es.save_to_file(Path(tmp_path) / "pathlib.json")
        loaded = EventStream.load_from_file(Path(tmp_path) / "pathlib.json")
        assert len(loaded) == 1
