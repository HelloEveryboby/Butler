# -*- coding: utf-8 -*-
"""原生 Agent 循环的回归测试。

覆盖：
- 技能 → 工具适配（含参数透传与不可执行技能过滤）
- Agent.run_task 走真实 tool calling 循环并写 tasks 表
- 工具失败后 Agent 能继续收敛
- Planner/Executor 不再输出伪造结果
- JarvisAgentBridge 端到端（技能工具 + 权限 + 事件流）
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from butler.agent.agent import Agent
from butler.agent.executor import Executor
from butler.agent.planner import Planner
from butler.core.agent_runtime.jarvis_adapter import JarvisAgentBridge
from butler.core.agent_runtime.skill_tools import register_skill_tools
from butler.core.agent_runtime.tool_registry import ToolRegistry


class FakeSkillManager:
    """只暴露一个可执行技能和一个纯指令技能的假 SkillManager。"""

    def __init__(self):
        self.manifests = {
            "demo_skill": {"has_python": True, "description": "Demo skill"},
            "prompt_only": {"description": "Instruction-only skill"},
        }
        self.loaded_skills = {}
        self.calls = []

    def export_openai_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "demo_skill",
                    "description": "Echo text back",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prompt_only",
                    "description": "Instruction only",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    def execute(self, skill_id, action, **kwargs):
        self.calls.append((skill_id, action, kwargs))
        text = (kwargs.get("entities") or {}).get("text", "")
        return {"status": "success", "content": f"echo:{text}"}


def _tool_call(name, arguments, call_id="call_1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def test_skill_tools_register_and_execute():
    manager = FakeSkillManager()
    registry = ToolRegistry()

    mapping = register_skill_tools(registry, manager)

    assert mapping == {"demo_skill": "demo_skill"}
    assert "prompt_only" not in registry.list_names()

    result = registry.execute("demo_skill", {"action": "run", "text": "hi"})

    assert result.success is True
    assert result.content == "echo:hi"
    skill_id, action, kwargs = manager.calls[0]
    assert (skill_id, action) == ("demo_skill", "run")
    assert kwargs["entities"]["text"] == "hi"


def test_agent_runs_tool_calling_loop_and_persists_task(tmp_path):
    calls = {"n": 0}

    def fake_llm(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "content": "",
                "stop_reason": "tool_calls",
                "tool_calls": [_tool_call("bash", {"command": "echo butler-native-agent"})],
            }
        return {"content": "已执行 echo", "stop_reason": "end_turn", "tool_calls": []}

    db_path = tmp_path / "tasks.db"
    agent = Agent(
        db_path=str(db_path),
        llm_call_handler=fake_llm,
        skill_manager=None,
        workspace_root=str(tmp_path),
        max_turns=5,
    )

    result = agent.run_task("用 shell 打印一句话")

    assert result["status"] == "completed"
    assert result["turns"] == 2
    assert result["report"] == "已执行 echo"
    assert result["plan"][0]["tool"] == "bash"

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT status, agent, output FROM tasks WHERE id = ?", (result["task_id"],)).fetchone()
    conn.close()
    assert row[0] == "completed"
    assert row[1] == "supervisor"
    assert "已执行 echo" in row[2]

    assert [t["id"] for t in agent.list_tasks()] == [result["task_id"]]


def test_agent_recovers_from_unknown_tool(tmp_path):
    calls = {"n": 0}

    def fake_llm(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "content": "",
                "stop_reason": "tool_calls",
                "tool_calls": [_tool_call("no_such_tool", {}, "call_bad")],
            }
        return {"content": "改用其他方式完成", "stop_reason": "end_turn", "tool_calls": []}

    agent = Agent(
        db_path=str(tmp_path / "tasks.db"),
        llm_call_handler=fake_llm,
        skill_manager=None,
        workspace_root=str(tmp_path),
    )

    result = agent.run_task("做点什么")

    assert result["status"] == "completed"
    assert result["turns"] == 2
    assert result["report"] == "改用其他方式完成"


def test_planner_fallback_is_honest_not_fake():
    steps = Planner(use_mock=True).create_plan("整理本周销售报告")

    assert len(steps) == 1
    assert steps[0]["action"] == "agent_loop"
    assert "整理本周销售报告" in steps[0]["input"]["goal"]


def test_executor_rejects_unknown_tool():
    result = Executor(registry=ToolRegistry()).execute_step({"action": "not_a_tool"}, {})

    assert result["status"] == "failed"
    assert "未知工具" in result["error"]


class StubSkillManager(FakeSkillManager):
    pass


class StubJarvis:
    """够用的 Jarvis 替身：只实现 bridge 真正会碰到的接口。"""

    def __init__(self, skill_manager):
        self.root = None
        self.container = None
        self.config = {"agent": {"runtime": True, "auto_confirm": True, "max_turns": 5}}
        self.skill_manager = skill_manager
        self.long_memory = self
        self.printed = []

    def get_recent_history(self, limit=10):
        return []

    def ui_print(self, message, tag="ai_response", **kwargs):
        self.printed.append((tag, message))

    def _get_runner_env_prompt_extension(self):
        return ""


def test_jarvis_bridge_end_to_end_with_skill_tool(monkeypatch):
    manager = StubSkillManager()
    jarvis = StubJarvis(manager)

    responses = [
        (_tool_call("demo_skill", {"action": "run", "text": "butler"}), "tool_calls"),
        ({}, "end_turn"),
    ]

    def fake_chat(cfg, messages, tools=None, **kwargs):
        tool_call, stop_reason = responses.pop(0)
        content = "工具执行完毕，任务完成" if stop_reason == "end_turn" else ""
        return content, [tool_call] if tool_call else [], stop_reason, 42

    class FakeConfig:
        is_usable = True

    monkeypatch.setattr(
        "butler.core.agent_runtime.jarvis_adapter.resolve_llm_config",
        lambda *a, **k: FakeConfig(),
    )
    monkeypatch.setattr("butler.core.agent_runtime.jarvis_adapter.chat_completions", fake_chat)

    bridge = JarvisAgentBridge(jarvis, enabled=True, echo_assistant=False)
    result = bridge.run("用 demo 技能回显 butler")

    assert result["stop_reason"] == "end_turn"
    assert result["response"] == "工具执行完毕，任务完成"
    assert manager.calls and manager.calls[0][0] == "demo_skill"
    assert bridge.skill_tool_map == {"demo_skill": "demo_skill"}

    tool_events = [e for e in result["events"] if getattr(e.type, "value", e.type) == "tool_result"]
    assert tool_events and "echo:butler" in str(tool_events[0].data)
    # echo_assistant=False，中间 assistant 文本不打到 UI（由宿主自己汇报）
    assert all(tag != "ai_response" for tag, _ in jarvis.printed)


def test_bridge_blocks_dangerous_command(monkeypatch):
    class FakeConfig:
        is_usable = True

    monkeypatch.setattr(
        "butler.core.agent_runtime.jarvis_adapter.resolve_llm_config",
        lambda *a, **k: FakeConfig(),
    )
    jarvis = StubJarvis(StubSkillManager())
    bridge = JarvisAgentBridge(jarvis, enabled=True)
    bridge.create_runtime()

    handler = bridge.runtime.config.auto_confirm_handler

    assert handler("bash", {"command": "echo safe"}) is True
    assert handler("bash", {"command": "rm -rf / --no-preserve-root"}) is False
