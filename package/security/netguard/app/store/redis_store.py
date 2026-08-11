"""Redis 状态存储 — 生产环境，支持多 worker 共享"""

import json
import time
from datetime import datetime, timezone

from app.store.base import StateStore


class RedisStore(StateStore):
    def __init__(self, redis_client):
        self._r = redis_client

    # ── IP 阻断 ──

    async def is_ip_blocked(self, ip: str) -> bool:
        return await self._r.exists(f"blocked:{ip}") > 0

    async def block_ip(self, ip: str, ttl_seconds: int = 3600):
        await self._r.setex(f"blocked:{ip}", ttl_seconds, "1")

    async def unblock_ip(self, ip: str):
        await self._r.delete(f"blocked:{ip}")

    async def get_blocked_ips(self) -> list[str]:
        keys = []
        async for key in self._r.scan_iter("blocked:*"):
            keys.append(key.decode().split(":", 1)[1] if isinstance(key, bytes) else key.split(":", 1)[1])
        return keys

    # ── 请求计数 ──

    async def increment_counter(self, key: str, window_seconds: int) -> int:
        pipe = self._r.pipeline()
        redis_key = f"counter:{key}"
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds)
        result = await pipe.execute()
        return result[0]

    async def get_counter(self, key: str) -> int:
        val = await self._r.get(f"counter:{key}")
        return int(val) if val else 0

    # ── 规则 ──

    async def set_rule(self, key: str, value: int):
        await self._r.hset("netguard:rules", key, str(value))

    async def get_rules(self) -> dict:
        raw = await self._r.hgetall("netguard:rules")
        return {k.decode() if isinstance(k, bytes) else k: int(v) for k, v in raw.items()}

    # ── 黑名单 ──

    async def add_to_blacklist(self, source: str, ips: list[str]):
        if ips:
            await self._r.sadd(f"blacklist:{source}", *ips)

    async def get_blacklist(self, source: str | None = None) -> list[str]:
        if source:
            members = await self._r.smembers(f"blacklist:{source}")
            return [m.decode() if isinstance(m, bytes) else m for m in members]
        # 合并所有源
        keys = []
        async for key in self._r.scan_iter("blacklist:*"):
            keys.append(key)
        result = set()
        for key in keys:
            members = await self._r.smembers(key)
            result.update(m.decode() if isinstance(m, bytes) else m for m in members)
        return list(result)

    async def is_blacklisted(self, ip: str) -> bool:
        sources = []
        async for key in self._r.scan_iter("blacklist:*"):
            sources.append(key)
        for source_key in sources:
            if await self._r.sismember(source_key, ip):
                return True
        return False

    # ── 任务队列 ──

    async def create_task(self, task_id: str, task_type: str, params: dict):
        data = {
            "task_id": task_id,
            "task_type": task_type,
            "params": json.dumps(params),
            "status": "pending",
            "result": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._r.hset(f"task:{task_id}", mapping=data)
        await self._r.sadd(f"tasks:{task_type}", task_id)

    async def update_task(self, task_id: str, status: str, result: dict | None = None):
        mapping = {
            "status": status,
            "result": json.dumps(result) if result else "",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._r.hset(f"task:{task_id}", mapping=mapping)

    async def get_task(self, task_id: str) -> dict | None:
        data = await self._r.hgetall(f"task:{task_id}")
        if not data:
            return None
        return {
            k.decode() if isinstance(k, bytes) else k:
            v.decode() if isinstance(v, bytes) else v
            for k, v in data.items()
        }

    async def list_tasks(self, user_id: int, task_type: str | None = None) -> list[dict]:
        # 简化实现：扫描所有 task key
        results = []
        async for key in self._r.scan_iter("task:*"):
            data = await self._r.hgetall(key)
            if data:
                decoded = {
                    k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in data.items()
                }
                results.append(decoded)
        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)
