# -*- coding: utf-8 -*-
"""Butler 数字员工（Agent）— 基于 AgentRuntime 的原生工具调用循环。

历史问题
--------
旧实现（v2.0 Alpha）是「假 Agent」：``Planner`` 在没有 API Key 时按关键词返回
硬编码的三步计划，``Executor`` 找不到技能包就返回拟真的假文本，``butler agent run``
因此会在第一步直接失败（``该包被禁用`` + ``no such table: tasks``）。

现在的实现
---------
``Agent.run_task`` 直接驱动 ``butler.core.agent_runtime.AgentRuntime``：

    LLM → tool_calls（内置文件/shell 工具 + Butler 技能）→ 结果回灌 → LLM …
    → end_turn

任务状态持久化在 SQLite ``tasks`` 表（表缺失时自动补建）。
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = """You are Butler, an autonomous agent running locally on the user's machine.

Operate in a loop: inspect the environment with tools, take action, verify the result,
and only then answer. Keep working until the task is actually done.

Rules:
- Prefer tools over guessing. Never claim you did something you did not do.
- `bash` for shell work, `read`/`write`/`edit`/`grep`/`glob` for files,
  and the Butler skill tools for higher-level capabilities.
- If a tool fails, read the error and try a different approach.
- Respect the user's files: do not delete or overwrite without need.
- Final answer: what you did, where the result is, and what is still pending.
"""

# 明显的自毁命令：即使 auto_confirm 打开也拒绝
_DANGEROUS_COMMAND_PATTERNS = (
    r"rm\s+-rf\s+/(\s|$)",
    r"mkfs\.",
    r"dd\s+if=",
    r">\s*/dev/sd",
    r"shutdown\b",
    r"reboot\b",
    r":\(\)\s*\{",
)


def _config_get(key: str, default: Any = None) -> Any:
    """安全读取 config.yaml，不因配置模块缺失而中断。"""
    try:
        from package.core_utils.config_loader import config_loader

        value = config_loader.get(key)
        return default if value is None else value
    except Exception:
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Agent:
    """单个数字员工：一个带工具、记忆和持久化任务记录的 Agent 循环。"""

    def __init__(
        self,
        role: str = "supervisor",
        db_path: str = None,
        use_mock: bool = None,
        llm_call_handler: Optional[Callable[..., Dict[str, Any]]] = None,
        skill_manager: Any = None,
        max_turns: Optional[int] = None,
        workspace_root: Optional[str] = None,
    ):
        self.role = role
        if db_path is None:
            self.db_path = Path(__file__).resolve().parent.parent / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)

        # use_mock 仅为兼容旧签名保留：现在没有假计划可退回，配置缺失时直接报错。
        self.use_mock = bool(use_mock)
        self._llm_call_handler = llm_call_handler
        self.max_turns = max_turns or _as_int(_config_get("agent.max_turns", 25), 25)
        self.workspace_root = str(workspace_root or os.getcwd())
        self.skill_manager = skill_manager if skill_manager is not None else self._load_skill_manager()
        self.skill_tool_map: Dict[str, str] = {}
        self._runtime = None

        self._ensure_schema()

    # ------------------------------------------------------------------ 初始化
    def _load_skill_manager(self):
        """加载 Butler 技能；失败不阻断 Agent（退化为只有内置工具）。"""
        try:
            from butler.core.skill_manager import SkillManager

            manager = SkillManager()
            manager.load_skills()
            return manager
        except Exception as exc:  # pragma: no cover - 环境相关
            logger.warning("Agent: 技能加载失败，仅使用内置工具: %s", exc)
            return None

    def _ensure_schema(self) -> None:
        """补建 tasks 表（冷启动/独立调用时不依赖 CLI 迁移）。"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        agent TEXT,
                        status TEXT NOT NULL,
                        input TEXT,
                        output TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            conn.close()
        except Exception as exc:
            logger.error("初始化 tasks 表失败: %s", exc)

    # ------------------------------------------------------------------ 运行时
    def _build_registry(self):
        from butler.core.agent_runtime.builtin_tools import register_builtin_tools
        from butler.core.agent_runtime.skill_tools import register_skill_tools
        from butler.core.agent_runtime.tool_registry import ToolRegistry

        registry = ToolRegistry()
        register_builtin_tools(registry, workspace_root=self.workspace_root)

        if self.skill_manager is not None:
            max_tools = _as_int(_config_get("agent.max_skill_tools", 40), 40)
            self.skill_tool_map = register_skill_tools(
                registry,
                self.skill_manager,
                max_tools=max_tools if max_tools > 0 else None,
            )
        return registry

    def _build_permission_system(self):
        from butler.core.agent_runtime.permission import PermissionMode, PermissionSystem

        permissions = PermissionSystem()
        mode_name = str(_config_get("agent.permission_mode", "default") or "default").lower()
        try:
            permissions.set_mode(PermissionMode(mode_name))
        except ValueError:
            logger.warning("未知权限模式 '%s'，使用 default", mode_name)
        return permissions

    def _auto_confirm(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """无 UI 场景的权限决策：默认放行，但拦截明显的自毁命令。"""
        command = str(arguments.get("command") or "")
        for pattern in _DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command):
                logger.warning("拒绝高危命令 (%s): %s", tool_name, command[:120])
                return False
        return bool(_config_get("agent.auto_confirm", True))

    def _default_llm_handler(self, messages: List[dict], tools: List[dict], **kwargs) -> Dict[str, Any]:
        from butler.core.llm_providers import chat_completions, resolve_llm_config

        cfg = resolve_llm_config(_config_get)
        if not cfg.is_usable:
            raise RuntimeError(
                "没有可用的 LLM 提供商。请设置 DEEPSEEK_API_KEY（或 OPENAI_API_KEY 等），"
                "或用 AI_PROVIDER=ollama 指向本地模型。"
            )

        content, tool_calls, stop_reason, _tokens = chat_completions(
            cfg,
            messages,
            tools=tools,
            max_tokens=_as_int(_config_get("api.max_tokens", 4096), 4096),
            temperature=float(_config_get("api.temperature", 0.3) or 0.3),
        )
        return {"content": content, "tool_calls": tool_calls, "stop_reason": stop_reason}

    def get_runtime(self):
        """构建（并缓存）AgentRuntime，供 CLI/TUI/测试复用。"""
        if self._runtime is not None:
            return self._runtime

        from butler.core.agent_runtime.agent_runtime import AgentConfig, AgentRuntime
        from butler.core.agent_runtime.context_manager import ContextManager
        from butler.core.agent_runtime.event_stream import EventStream

        handler = self._llm_call_handler or self._default_llm_handler

        self._runtime = AgentRuntime(
            config=AgentConfig(
                max_turns=self.max_turns,
                system_prompt=_DEFAULT_SYSTEM_PROMPT,
                llm_call_handler=handler,
                auto_confirm_handler=self._auto_confirm,
                enable_self_healing=True,
            ),
            tool_registry=self._build_registry(),
            permission_system=self._build_permission_system(),
            context_manager=ContextManager(token_limit=120000, compaction_threshold=0.8),
            event_stream=EventStream(),
        )
        return self._runtime

    # ------------------------------------------------------------------ 任务
    def run_task(self, task_input: str) -> Dict[str, Any]:
        """执行一个任务，返回最终报告；全过程写入 tasks 表。"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        self._update_task_db(task_id, "running", task_input)
        logger.info("[%s] 任务 %s 开始: %s", self.role, task_id, task_input)

        try:
            runtime = self.get_runtime()
        except Exception as exc:
            logger.error("Agent 运行时初始化失败: %s", exc, exc_info=True)
            report = f"Agent 运行时初始化失败: {exc}"
            self._update_task_db(task_id, "failed", task_input, report)
            return self._result(task_id, "failed", [], {}, report, "error", 0)

        try:
            raw = runtime.run(user_input=task_input)
        except Exception as exc:
            logger.error("任务执行异常: %s", exc, exc_info=True)
            report = f"任务执行异常: {exc}"
            self._update_task_db(task_id, "failed", task_input, report)
            return self._result(task_id, "failed", [], {}, report, "error", 0)

        response = (raw.get("response") or "").strip()
        stop_reason = str(raw.get("stop_reason") or "end_turn")
        turns = int(raw.get("turns") or 0)
        plan, results = self._extract_trace(runtime)

        if stop_reason == "end_turn":
            status = "completed"
            report = response or "任务已完成（模型未返回文本总结）。"
        elif stop_reason == "max_turns":
            status = "incomplete"
            report = f"已达到最大轮次 {self.max_turns}，任务尚未收敛。\n\n最近结果:\n{response}"
        elif stop_reason == "permission_denied":
            status = "failed"
            report = "权限被拒绝，任务中止。"
        elif stop_reason == "user_interrupt":
            status = "failed"
            report = "任务被用户中断。"
        elif stop_reason == "error":
            status = "failed"
            detail = self._last_error(raw.get("events") or [])
            report = f"运行失败: {detail}" if detail else (response or "任务失败（LLM 或工具链异常）。")
        else:
            status = "failed"
            report = response or f"任务失败（stop_reason={stop_reason}）。"

        self._update_task_db(task_id, status, task_input, report)
        logger.info("[%s] 任务 %s 结束: %s (%d 轮)", self.role, task_id, status, turns)
        return self._result(task_id, status, plan, results, report, stop_reason, turns)

    def _extract_trace(self, runtime) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """从最终对话状态里提取「计划 = 工具调用序列」和「工具结果」。"""
        plan: List[Dict[str, Any]] = []
        results: Dict[str, Any] = {}
        state = getattr(runtime, "state", None)
        if not state:
            return plan, results

        for message in state.messages:
            for call in getattr(message, "tool_calls", []) or []:
                plan.append({"tool": call.name, "arguments": dict(call.arguments or {})})
            if getattr(message, "role", "") == "tool":
                results[getattr(message, "tool_call_id", "") or f"result_{len(results)}"] = message.content

        return plan, results

    @staticmethod
    def _last_error(events) -> str:
        """从事件流里取出最后一条错误信息，给用户可读的失败原因。"""
        for event in reversed(events):
            kind = getattr(getattr(event, "type", None), "value", getattr(event, "type", ""))
            data = getattr(event, "data", None) or {}
            if kind == "error" and data.get("error"):
                return str(data["error"])
        return ""

    def _result(
        self,
        task_id: str,
        status: str,
        plan: List[Dict[str, Any]],
        results: Dict[str, Any],
        report: str,
        stop_reason: str,
        turns: int,
    ) -> Dict[str, Any]:
        return {
            "task_id": task_id,
            "status": status,
            "plan": plan,
            "results": results,
            "report": report,
            "response": report,
            "stop_reason": stop_reason,
            "turns": turns,
        }

    def _update_task_db(self, task_id: str, status: str, input_str: str, output_str: Optional[str] = None) -> None:
        """写入/更新任务状态；失败只记日志，不影响任务本身。"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO tasks (id, agent, status, input, output) VALUES (?, ?, ?, ?, ?)",
                    (task_id, self.role, status, input_str, output_str),
                )
            conn.close()
        except Exception as exc:
            logger.error("写入 tasks 表失败: %s", exc)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """读取历史任务归档。"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, agent, status, input, output, created_at FROM tasks ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": row[0],
                    "agent": row[1],
                    "status": row[2],
                    "input": row[3],
                    "output": row[4],
                    "created_at": row[5],
                }
                for row in rows
            ]
        except Exception as exc:
            logger.error("读取 tasks 表失败: %s", exc)
            return []
