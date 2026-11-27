"""主动代理 — 按固定间隔自动执行 Agent 任务。

与 ProactiveAgent（系统健康巡检）互补：这里执行的是用户用自然语言定义的
周期性任务，例如「每小时检查一次下载目录并整理」「每天早上汇总待办」。

任务持久化在 SQLite，daemon 线程按 next_run 轮询执行；每次执行都会记录
状态与结果，便于 `butler agent schedule list` 查看。
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "system_data" / "long_memory.db"


def parse_interval(text: str) -> int:
    """把 '30s' / '10m' / '2h' / '1d' 解析为秒。"""
    text = str(text or "").strip().lower()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if text.isdigit():
        return int(text)
    if len(text) > 1 and text[-1] in units and text[:-1].isdigit():
        return int(text[:-1]) * units[text[-1]]
    raise ValueError(f"无法解析间隔: {text}（示例: 30s / 10m / 2h / 1d）")


class AgentScheduler:
    """周期性 Agent 任务调度器。"""

    def __init__(self, db_path: str | None = None, agent_factory: Callable[[], Any] | None = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.agent_factory = agent_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ensure_schema()

    # ------------------------------------------------------------------ 存储
    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self.db_path))

    def _ensure_schema(self) -> None:
        try:
            conn = self._connect()
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_jobs (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        prompt TEXT NOT NULL,
                        interval_seconds INTEGER NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        next_run REAL NOT NULL,
                        last_run REAL,
                        last_status TEXT,
                        last_output TEXT
                    )
                    """
                )
            conn.close()
        except Exception as exc:
            logger.error("初始化 agent_jobs 表失败: %s", exc)

    def add(self, prompt: str, interval: str | int, name: str | None = None) -> dict[str, Any]:
        """新增一个周期任务。"""
        seconds = parse_interval(str(interval)) if not isinstance(interval, int) else interval
        if seconds < 10:
            raise ValueError("间隔不能小于 10 秒")
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        now = time.time()
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT INTO agent_jobs (id, name, prompt, interval_seconds, enabled, next_run) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (job_id, name or prompt[:40], prompt, seconds, now + seconds),
            )
        conn.close()
        return {
            "id": job_id,
            "name": name or prompt[:40],
            "prompt": prompt,
            "interval_seconds": seconds,
            "next_run": now + seconds,
        }

    def list_jobs(self) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, name, prompt, interval_seconds, enabled, next_run, last_run, last_status, last_output "
            "FROM agent_jobs ORDER BY next_run"
        ).fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "name": row[1],
                "prompt": row[2],
                "interval_seconds": row[3],
                "enabled": bool(row[4]),
                "next_run": row[5],
                "last_run": row[6],
                "last_status": row[7],
                "last_output": row[8],
            }
            for row in rows
        ]

    def remove(self, job_id: str) -> bool:
        conn = self._connect()
        with conn:
            cursor = conn.execute("DELETE FROM agent_jobs WHERE id = ?", (job_id,))
        conn.close()
        return cursor.rowcount > 0

    def set_enabled(self, job_id: str, enabled: bool) -> bool:
        conn = self._connect()
        with conn:
            cursor = conn.execute(
                "UPDATE agent_jobs SET enabled = ? WHERE id = ?", (1 if enabled else 0, job_id)
            )
        conn.close()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------ 执行
    def due_jobs(self, now: float | None = None) -> list[dict[str, Any]]:
        now = now or time.time()
        return [job for job in self.list_jobs() if job["enabled"] and job["next_run"] <= now]

    def _agent(self) -> Any:
        if self.agent_factory is not None:
            return self.agent_factory()
        from butler.agent.agent import Agent

        return Agent(role="scheduler")

    def run_job(self, job: dict[str, Any], agent: Any = None) -> dict[str, Any]:
        """执行单个任务，记录结果并推进 next_run。"""
        started = time.time()
        status, output = "failed", ""
        try:
            runner = agent or self._agent()
            result = runner.run_task(job["prompt"])
            status = result.get("status", "failed")
            output = (result.get("report") or "")[:2000]
        except Exception as exc:
            logger.error("定时任务 %s 执行失败: %s", job["id"], exc, exc_info=True)
            output = f"执行异常: {exc}"

        next_run = started + int(job["interval_seconds"])
        conn = self._connect()
        with conn:
            conn.execute(
                "UPDATE agent_jobs SET last_run = ?, last_status = ?, last_output = ?, next_run = ? WHERE id = ?",
                (started, status, output, next_run, job["id"]),
            )
        conn.close()
        logger.info("定时任务 %s 完成: %s", job["id"], status)
        return {"id": job["id"], "status": status, "output": output, "next_run": next_run}

    def run_due(self, now: float | None = None, agent: Any = None) -> list[dict[str, Any]]:
        """执行所有到期任务。"""
        results = []
        for job in self.due_jobs(now):
            results.append(self.run_job(job, agent=agent))
        return results

    # ------------------------------------------------------------------ 守护
    def start(self, poll_seconds: float = 30.0) -> None:
        """启动后台轮询线程（幂等）。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def loop():
            logger.info("主动代理调度器已启动（每 %.0f 秒轮询）", poll_seconds)
            while not self._stop.is_set():
                try:
                    self.run_due()
                except Exception as exc:
                    logger.error("调度轮询异常: %s", exc)
                self._stop.wait(poll_seconds)

        self._thread = threading.Thread(target=loop, name="butler-agent-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


_default_scheduler: AgentScheduler | None = None
_default_lock = threading.Lock()


def get_scheduler() -> AgentScheduler:
    global _default_scheduler
    with _default_lock:
        if _default_scheduler is None:
            _default_scheduler = AgentScheduler()
        return _default_scheduler
