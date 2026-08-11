"""定时扫描服务"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import ScheduledScan
from app.tasks.queue import TaskQueue


class ScheduleService:
    def __init__(self, db: AsyncSession, task_queue: TaskQueue):
        self.db = db
        self.task_queue = task_queue

    async def create(self, user_id: int, target: str, scan_type: str, cron_expr: str) -> dict:
        schedule = ScheduledScan(
            user_id=user_id,
            target=target,
            scan_type=scan_type,
            cron_expr=cron_expr,
            is_active=True,
        )
        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)

        return {
            "id": schedule.id,
            "target": schedule.target,
            "scan_type": schedule.scan_type,
            "cron_expr": schedule.cron_expr,
            "is_active": schedule.is_active,
            "created_at": schedule.created_at.isoformat(),
        }

    async def list_user_schedules(self, user_id: int) -> list[dict]:
        result = await self.db.execute(
            select(ScheduledScan)
            .where(ScheduledScan.user_id == user_id)
            .order_by(ScheduledScan.created_at.desc())
        )
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "target": r.target,
                "scan_type": r.scan_type,
                "cron_expr": r.cron_expr,
                "is_active": r.is_active,
                "last_run_at": r.last_run_at,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]

    async def toggle(self, schedule_id: int, user_id: int) -> dict:
        result = await self.db.execute(
            select(ScheduledScan).where(
                ScheduledScan.id == schedule_id,
                ScheduledScan.user_id == user_id,
            )
        )
        schedule = result.scalar_one_or_none()
        if not schedule:
            raise ValueError("Schedule not found")

        schedule.is_active = not schedule.is_active
        await self.db.commit()
        return {"id": schedule.id, "is_active": schedule.is_active}

    async def delete(self, schedule_id: int, user_id: int) -> bool:
        result = await self.db.execute(
            select(ScheduledScan).where(
                ScheduledScan.id == schedule_id,
                ScheduledScan.user_id == user_id,
            )
        )
        schedule = result.scalar_one_or_none()
        if not schedule:
            return False
        await self.db.delete(schedule)
        await self.db.commit()
        return True
