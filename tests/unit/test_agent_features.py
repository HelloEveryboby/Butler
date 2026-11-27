"""新 Agent 能力测试：子代理、长期记忆、主动调度、MCP 接入。"""

import json
import sys

import pytest

from butler.agent.agent import Agent
from butler.core.agent_memory import AgentMemory
from butler.core.agent_runtime import mcp_stdio
from butler.core.agent_runtime.mcp_stdio import register_mcp_tools
from butler.core.agent_runtime.tool_registry import ToolRegistry
from butler.core.agent_scheduler import AgentScheduler, parse_interval

MCP_SERVER = """#!/usr/bin/env python3
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    req = json.loads(line)
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "echo", "description": "Echo text", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}]}
    elif method == "tools/call":
        text = (req.get("params") or {}).get("arguments", {}).get("text", "")
        result = {"content": [{"type": "text", "text": "echo:" + text}]}
    elif method and method.startswith("notifications/"):
        continue
    else:
        result = {}

    if req_id is not None:
        print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}), flush=True)
"""


def test_memory_remember_recall_and_markdown(tmp_path):
    memory = AgentMemory(
        db_path=str(tmp_path / "mem.db"), markdown_path=str(tmp_path / "MEMORY.md")
    )

    memory.remember(
        "解析 BHL 模块的构建流程", "用 hybrid_hub 统一构建 C/C++/Go/Rust", "completed", ["bash"]
    )
    memory.remember("整理下载目录", "按日期归档到 Documents", "completed", ["bash"])

    rows = memory.recall("BHL 构建流程")
    assert rows
    assert "BHL" in rows[0]["task"]

    assert memory.stats()["count"] == 2
    markdown = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "hybrid_hub" in markdown


def test_agent_recalls_experience_next_run(tmp_path):
    memory = AgentMemory(
        db_path=str(tmp_path / "mem.db"), markdown_path=str(tmp_path / "MEMORY.md")
    )
    seen = []

    def fake_llm(messages, tools, **kwargs):
        seen.append(messages)
        return {
            "content": "BHL 用 hybrid_hub 统一构建",
            "stop_reason": "end_turn",
            "tool_calls": [],
        }

    agent = Agent(
        db_path=str(tmp_path / "tasks.db"),
        llm_call_handler=fake_llm,
        skill_manager=None,
        workspace_root=str(tmp_path),
        memory=memory,
    )

    agent.run_task("解析 BHL 模块的构建流程")
    agent.run_task("BHL 构建流程是什么")

    system_blocks = [m["content"] for m in seen[-1] if m["role"] == "system"]
    assert any("历史任务经验" in block for block in system_blocks)


def test_subagent_task_delegation(tmp_path):
    memory = AgentMemory(
        db_path=str(tmp_path / "mem.db"), markdown_path=str(tmp_path / "MEMORY.md")
    )
    calls = {"parent": 0, "child": 0}

    def fake_llm(messages, tools, **kwargs):
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        if "codebase explorer" in system:
            calls["child"] += 1
            return {
                "content": "found: butler/core/hybrid_hub.py",
                "stop_reason": "end_turn",
                "tool_calls": [],
            }

        calls["parent"] += 1
        if calls["parent"] == 1:
            return {
                "content": "",
                "stop_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "t1",
                        "type": "function",
                        "function": {
                            "name": "task",
                            "arguments": json.dumps(
                                {"prompt": "find the BHL hub file", "agent": "explorer"}
                            ),
                        },
                    }
                ],
            }
        return {"content": "done", "stop_reason": "end_turn", "tool_calls": []}

    agent = Agent(
        db_path=str(tmp_path / "tasks.db"),
        llm_call_handler=fake_llm,
        skill_manager=None,
        workspace_root=str(tmp_path),
        memory=memory,
    )

    result = agent.run_task("找一下 BHL hub")

    assert result["status"] == "completed"
    assert calls["child"] == 1
    assert result["plan"][0]["tool"] == "task"


class StubAgent:
    def __init__(self, status="completed", report="done"):
        self.status = status
        self.report = report
        self.tasks = []

    def run_task(self, prompt):
        self.tasks.append(prompt)
        return {"status": self.status, "report": self.report}


def test_scheduler_runs_job_and_persists(tmp_path):
    scheduler = AgentScheduler(db_path=str(tmp_path / "jobs.db"))
    job = scheduler.add("检查下载目录", "10m", name="下载检查")
    stub = StubAgent()

    result = scheduler.run_job(job, agent=stub)

    assert result["status"] == "completed"
    assert stub.tasks == ["检查下载目录"]

    stored = scheduler.list_jobs()[0]
    assert stored["last_status"] == "completed"
    assert stored["last_output"] == "done"
    assert stored["next_run"] > stored["last_run"]


def test_scheduler_interval_parsing(tmp_path):
    assert parse_interval("30s") == 30
    assert parse_interval("10m") == 600
    assert parse_interval("2h") == 7200
    assert parse_interval("1d") == 86400

    with pytest.raises(ValueError):
        parse_interval("soon")


def test_mcp_stdio_registers_and_calls_tool(tmp_path):
    server = tmp_path / "fake_mcp.py"
    server.write_text(MCP_SERVER, encoding="utf-8")
    server.chmod(0o755)

    registry = ToolRegistry()
    try:
        connected = register_mcp_tools(
            registry,
            servers=[{"name": "fake", "command": sys.executable, "args": [str(server)]}],
            start_timeout=10,
        )
        assert connected == ["fake"]
        assert "mcp_fake_echo" in registry.list_names()

        result = registry.execute("mcp_fake_echo", {"text": "hi"})
        assert result.success is True
        assert result.content == "echo:hi"
    finally:
        mcp_stdio._stop_all()
