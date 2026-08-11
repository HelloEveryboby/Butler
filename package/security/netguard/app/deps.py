"""统一依赖注入"""

from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.store.base import StateStore
from app.utils.security import decode_token


# ── 状态存储（单例） ──
_store_instance: StateStore | None = None


async def get_store() -> StateStore:
    """获取状态存储实例（Redis 或内存）"""
    global _store_instance
    if _store_instance is None:
        settings = get_settings()
        if settings.REDIS_URL:
            try:
                import redis.asyncio as aioredis
                client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                from app.store.redis_store import RedisStore
                _store_instance = RedisStore(client)
            except Exception:
                from app.store.memory_store import MemoryStore
                _store_instance = MemoryStore()
        else:
            from app.store.memory_store import MemoryStore
            _store_instance = MemoryStore()
    return _store_instance


# ── 任务队列（单例） ──
_task_queue_instance = None


async def get_task_queue():
    """获取任务队列实例"""
    global _task_queue_instance
    if _task_queue_instance is None:
        from app.tasks.queue import TaskQueue
        store = await get_store()
        _task_queue_instance = TaskQueue(store)
    return _task_queue_instance


# ── 认证 ──

async def get_current_user(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    双认证方式：
    1. X-API-Key Header
    2. Authorization: Bearer <token>
    优先检查 API Key。
    """
    # ── API Key 认证 ──
    if x_api_key:
        result = await db.execute(
            select(User).where(User.api_key == x_api_key)
        )
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user

    # ── JWT 认证 ──
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = decode_token(token)
        if payload and payload.get("sub"):
            result = await db.execute(
                select(User).where(User.id == int(payload["sub"]))
            )
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing credentials",
    )


def require_tier(min_tier: str):
    """
    Tier 守卫依赖工厂。
    用法：current_user: User = Depends(require_tier("pro"))
    """
    tier_order = {"free": 0, "pro": 1}

    async def _check(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if tier_order.get(current_user.tier, 0) < tier_order.get(min_tier, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires '{min_tier}' tier or higher",
            )
        return current_user

    return _check
