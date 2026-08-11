"""定时扫描路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_task_queue
from app.models.user import User
from app.schemas.tasks import (
    ScheduleCreateRequest,
    ScheduleListResponse,
    ScheduleResponse,
)
from app.services.schedule_service import ScheduleService
from app.tasks.queue import TaskQueue

router = APIRouter(prefix="/api/v1/schedules", tags=["Scheduled Scans"])


@router.post("/", response_model=ScheduleResponse)
async def create_schedule(
    req: ScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: TaskQueue = Depends(get_task_queue),
):
    service = ScheduleService(db, queue)
    return await service.create(
        current_user.id, req.target, req.scan_type, req.cron_expr
    )


@router.get("/", response_model=ScheduleListResponse)
async def list_schedules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: TaskQueue = Depends(get_task_queue),
):
    service = ScheduleService(db, queue)
    schedules = await service.list_user_schedules(current_user.id)
    return ScheduleListResponse(schedules=schedules)


@router.put("/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: TaskQueue = Depends(get_task_queue),
):
    service = ScheduleService(db, queue)
    try:
        return await service.toggle(schedule_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: TaskQueue = Depends(get_task_queue),
):
    service = ScheduleService(db, queue)
    if not await service.delete(schedule_id, current_user.id):
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"message": "Schedule deleted"}
