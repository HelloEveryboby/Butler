# -*- coding: utf-8 -*-
"""
AI Memory Service Unit & Integration Tests
测试 Markdown FrontMatter 解析、SQLite FTS5 索引与降级、RRF 混合搜索、交接与 MCP 服务。
"""

import os
import shutil
import tempfile
import json
import pytest

from skills.ai_memory.data_model import MemoryDocument
from skills.ai_memory.memory_service import MemoryService
from skills.ai_memory.mcp_server import MCPMemoryServer
from skills.ai_memory import handle_request


@pytest.fixture
def temp_memory_dir():
    temp_dir = tempfile.mkdtemp(prefix="test_ai_memory_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_memory_document_serialization():
    doc = MemoryDocument(
        title="Test Design",
        project="Butler",
        session_summary="Completed memory architecture",
        decisions=["Use Markdown as source of truth", "Use SQLite FTS5 + Zvec"],
        open_questions=["What about vector dimensions?"],
        tags=["architecture", "ai-memory"],
        content="## Detailed Context\nThis is a test content string."
    )

    markdown_text = doc.to_frontmatter_markdown()
    assert "---" in markdown_text
    assert "Test Design" in markdown_text
    assert "Use Markdown as source of truth" in markdown_text

    parsed_doc = MemoryDocument.from_markdown(markdown_text)
    assert parsed_doc.title == "Test Design"
    assert parsed_doc.project == "Butler"
    assert parsed_doc.session_summary == "Completed memory architecture"
    assert "Use Markdown as source of truth" in parsed_doc.decisions
    assert "What about vector dimensions?" in parsed_doc.open_questions
    assert "architecture" in parsed_doc.tags
    assert "This is a test content string." in parsed_doc.content


def test_memory_service_crud_and_fts_search(temp_memory_dir):
    service = MemoryService(project_root=temp_memory_dir)

    doc = MemoryDocument(
        title="SQLite FTS5 Strategy",
        project="TestProject",
        session_summary="Testing SQLite FTS5 search",
        decisions=["Use BM25 ranking"],
        open_questions=[],
        tags=["sqlite", "search"],
        content="SQLite FTS5 provides high-performance full-text search capabilities."
    )

    saved_path = service.save_memory(doc)
    assert os.path.exists(saved_path)
    assert saved_path.startswith(temp_memory_dir)

    # Test FTS Search
    results = service.fts_search("capabilities")
    assert len(results) >= 1
    assert results[0]["title"] == "SQLite FTS5 Strategy"

    # Test Hybrid Search with Fallback
    hybrid_res = service.hybrid_search("FTS5 capabilities", limit=5)
    assert len(hybrid_res) >= 1
    assert "SQLite FTS5 Strategy" in [r["title"] for r in hybrid_res]


def test_handoff_and_session_lifecycle(temp_memory_dir):
    service = MemoryService(project_root=temp_memory_dir)

    handoff_doc = service.create_handoff(
        project_name="ProjectButler",
        session_summary="Built MCP server and FTS5 layer",
        decisions=["Implemented MCP JSON-RPC protocol"],
        open_questions=["Add web UI visualization"],
        title="Handoff Step 1"
    )

    assert os.path.exists(handoff_doc.file_path)

    latest = service.get_latest_handoff(project_name="ProjectButler")
    assert latest is not None
    assert latest["session_summary"] == "Built MCP server and FTS5 layer"
    assert "Implemented MCP JSON-RPC protocol" in latest["decisions"]


def test_mcp_server_json_rpc(temp_memory_dir):
    server = MCPMemoryServer(project_root=temp_memory_dir)

    # 1. Initialize
    init_resp = server.handle_rpc_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize"
    })
    assert init_resp["result"]["serverInfo"]["name"] == "butler-ai-memory"

    # 2. List tools
    tools_resp = server.handle_rpc_message({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list"
    })
    tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
    assert "search_memory" in tool_names
    assert "save_memory" in tool_names
    assert "create_handoff" in tool_names

    # 3. Call save_memory
    save_tool_resp = server.handle_rpc_message({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "save_memory",
            "arguments": {
                "title": "MCP Test Memory",
                "content": "Content saved via MCP tool call",
                "session_summary": "MCP summary",
                "project": "TestMCP"
            }
        }
    })
    res_text = save_tool_resp["result"]["content"][0]["text"]
    res_json = json.loads(res_text)
    assert res_json["status"] == "success"

    # 4. Call search_memory
    search_tool_resp = server.handle_rpc_message({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "search_memory",
            "arguments": {
                "query": "MCP tool call"
            }
        }
    })
    search_json = json.loads(search_tool_resp["result"]["content"][0]["text"])
    assert len(search_json) >= 1
    assert search_json[0]["title"] == "MCP Test Memory"


def test_skill_handle_request_lifecycle(temp_memory_dir):
    start_res = handle_request("session_start", project_root=temp_memory_dir, project_name="TestProj")
    assert start_res["status"] == "no_previous_handoff"

    save_res = handle_request(
        "save",
        project_root=temp_memory_dir,
        title="Skill Request Test",
        content="Testing skill entrypoint",
        session_summary="Summary test"
    )
    assert save_res["status"] == "success"

    end_res = handle_request(
        "session_end",
        project_root=temp_memory_dir,
        project_name="TestProj",
        session_summary="Finished iteration",
        decisions=["Tested skill handlers"]
    )
    assert end_res["status"] == "handoff_saved"

    restore_res = handle_request("session_start", project_root=temp_memory_dir, project_name="TestProj")
    assert restore_res["status"] == "handoff_restored"
    assert restore_res["summary"] == "Finished iteration"
