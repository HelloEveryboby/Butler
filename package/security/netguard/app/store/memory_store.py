"""内存状态存储 — 开发/测试用，重启丢失"""

import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from app.store.base import StateStore


class MemoryStore(StateStore):
    def __init__(self):
        self._blocked: dict[str, float] = {}  # ip -> expire_ts
        self._counters: dict[str, list[float]] = defaultdict(list)
        self._rules: dict[str, int] = {}
        self._blacklist: dict[str, set[str]] = defaultdict(set)  # source -> {ips}
        self._tasks: dict[str, dict] = {}

    # ── IP 阻断 ──

    async def is_ip_blocked(self, ip: str) -> bool:
        exp = self._blocked.get(ip)
        if exp and time.time() < exp:
            return True
        self._blocked.pop(ip, None)
        return False

    async def block_ip(self, ip: str, ttl_seconds: int = 3600):
        self._blocked[ip] = time.time() + ttl_seconds

    async def unblock_ip(self, ip: str):
        self._blocked.pop(ip, None)

    async def get_blocked_ips(self) -> list[str]:
        now = time.time()
        return [ip for ip, exp in self._blocked.items() if exp > now]

    # ── 请求计数 ──

    async def increment_counter(self, key: str, window_seconds: int) -> int:
        now = time.time()
        log = self._counters[key]
        log[:] = [t for t in log if now - t < window_seconds]
        log.append(now)
        return len(log)

    async def get_counter(self, key: str) -> int:
        return len(self._counters.get(key, []))

    # ── 规则 ──

    async def set_rule(self, key: str, value: int):
        self._rules[key] = value

    async def get_rules(self) -> dict:
        return dict(self._rules)

    # ── 黑名单 ──

    async def add_to_blacklist(self, source: str, ips: list[str]):
        self._blacklist[source].update(ips)

    async def get_blacklist(self, source: str | None = None) -> list[str]:
        if source:
            return list(self._blacklist.get(source, set()))
        result = set()
        for s in self._blacklist.values():
            result.update(s)
        return list(result)

    async def is_blacklisted(self, ip: str) -> bool:
        for s in self._blacklist.values():
            if ip in s:
                return True
        return False

    # ── 任务队列 ──

    async def create_task(self, task_id: str, task_type: str, params: dict):
        self._tasks[task_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "params": params,
            "status": "pending",
            "result": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def update_task(self, task_id: str, status: str, result: dict | None = None):
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = status
            self._tasks[task_id]["result"] = result
            self._tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

    async def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    async def list_tasks(self, user_id: int, task_type: str | None = None) -> list[dict]:
        results = []
        for t in self._tasks.values():
            if task_type and t["task_type"] != task_type:
                continue
            results.append(t)
        return sorted(results, key=lambda x: x["created_at"], reverse=True)
