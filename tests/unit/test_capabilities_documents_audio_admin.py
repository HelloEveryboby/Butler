"""documents / audio / skills_admin 三项核心能力测试。"""

from __future__ import annotations

from butler.core.capabilities import capability_registry


def _schema(name: str) -> dict:
    schemas = {item["function"]["name"]: item for item in capability_registry.tool_schemas()}
    return schemas[name]["function"]["parameters"]


def test_capabilities_registered():
    assert {"documents", "audio", "skills_admin"} <= set(capability_registry.names())


def test_documents_schema_actions():
    enum = _schema("documents")["properties"]["action"]["enum"]
    for action in (
        "convert",
        "extract_text",
        "extract_tables",
        "merge",
        "split",
        "create",
        "metadata",
        "rotate",
        "docx_read",
        "docx_create",
        "docx_edit",
        "markdown",
        "xlsx_recalc",
        "translate",
    ):
        assert action in enum
    assert _schema("documents")["required"] == ["action"]


def test_documents_translate_requires_text():
    result = capability_registry.execute("documents", "translate", {})

    assert "error" in result
    assert "text" in result["error"]


def test_audio_schema_actions():
    enum = _schema("audio")["properties"]["action"]["enum"]
    assert {"run", "open", "push_subtitle", "status"} <= set(enum)


def test_skills_admin_schema_actions():
    enum = _schema("skills_admin")["properties"]["action"]["enum"]
    assert {"find", "create", "sync"} <= set(enum)


def test_documents_convert(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# 标题\n\n这是 **正文**。", encoding="utf-8")
    output = tmp_path / "note.html"

    result = capability_registry.execute(
        "documents",
        "convert",
        {"input": str(source), "from": "MD", "to": "HTML", "save_to": str(output)},
    )

    assert "error" not in result
    assert output.exists()
    assert "<strong>正文</strong>" in output.read_text(encoding="utf-8")


def test_documents_markdown(tmp_path):
    source = tmp_path / "note.txt"
    source.write_text("hello butler", encoding="utf-8")

    result = capability_registry.execute("documents", "markdown", {"path": str(source)})

    assert "error" not in result
    assert "hello butler" in result["result"]


def test_skills_admin_find():
    result = capability_registry.execute("skills_admin", "find", {"query": ""})

    assert result["query"] == ""
    assert result["count"] >= 1
    assert isinstance(result["skills"], list)
