"""后台任务队列 — asyncio 实现"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from app.store.base import StateStore


class TaskQueue:
    """轻量级异步任务队列"""

    def __init__(self, store: StateStore):
        self.store = store
        self._handlers: dict[str, Callable] = {}
        self._running: dict[str, asyncio.Task] = {}

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务类型处理器"""
        self._handlers[task_type] = handler

    async def submit(self, task_type: str, params: dict, user_id: int) -> str:
        """提交任务，返回 task_id"""
        task_id = str(uuid.uuid4())[:8]
        params["user_id"] = user_id
        await self.store.create_task(task_id, task_type, params)

        # 异步执行
        if task_type in self._handlers:
            asyncio.create_task(self._execute(task_id, task_type, params))

        return task_id

    async def _execute(self, task_id: str, task_type: str, params: dict):
        """执行任务并更新状态"""
        await self.store.update_task(task_id, "running")
        try:
            handler = self._handlers[task_type]
            result = await handler(params)
            await self.store.update_task(task_id, "completed", result)
        except Exception as e:
            await self.store.update_task(task_id, "failed", {"error": str(e)})

    async def get_status(self, task_id: str) -> dict | None:
        return await self.store.get_task(task_id)

    async def list_user_tasks(self, user_id: int, task_type: str | None = None) -> list[dict]:
        return await self.store.list_tasks(user_id, task_type)
