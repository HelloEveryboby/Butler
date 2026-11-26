"""核心能力注册表测试 — 与技能系统解耦的五项能力。"""

from __future__ import annotations

from butler.core.agent_runtime.capability_tools import register_capability_tools
from butler.core.agent_runtime.tool_registry import ToolRegistry
from butler.core.capabilities import capability_registry


def test_five_capabilities_registered():
    assert set(capability_registry.names()) == {
        "reading", "scanner", "versioning", "commands", "dsh",
        "documents", "audio", "skills_admin",
        "media", "system", "network",
    }


def test_tool_schema_has_action_enum():
    schemas = {item["function"]["name"]: item for item in capability_registry.tool_schemas()}
    reading = schemas["reading"]["function"]["parameters"]
    assert reading["properties"]["action"]["enum"] == [
        "play", "pause", "resume", "stop", "status", "voices", "explain_tokens",
    ]
    assert reading["required"] == ["action"]


def test_execute_commands_lookup():
    result = capability_registry.execute("commands", "lookup", {"query": "扫描"})
    assert result["query"] == "扫描"
    assert isinstance(result["commands"], list)


def test_execute_reading_explain_tokens():
    result = capability_registry.execute(
        "reading", "explain_tokens", {"text": "他说：走吧。"}
    )
    assert result["tts_tokens"] == 0


def test_execute_versioning_snapshot(tmp_path):
    target = tmp_path / "note.txt"
    target.write_text("第一稿", encoding="utf-8")
    record = capability_registry.execute(
        "versioning", "snapshot", {"path": str(target), "message": "初稿"}
    )
    assert record["kind"] == "text"
    assert capability_registry.execute(
        "versioning", "list", {"path": str(target)}
    )["versions"]


def test_unknown_action_returns_error():
    result = capability_registry.execute("reading", "not-an-action", {})
    assert "error" in result


def test_register_capability_tools():
    registry = ToolRegistry()
    mapping = register_capability_tools(registry)
    assert mapping["reading"] == "reading"
    assert registry.get("scanner") is not None


def test_prompt_section_lists_all_capabilities():
    section = capability_registry.prompt_section()
    assert "Butler 核心能力" in section
    for name in capability_registry.names():
        assert name in section
