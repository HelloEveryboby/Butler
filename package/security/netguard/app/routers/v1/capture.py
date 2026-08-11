"""流量抓包路由"""

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user, get_task_queue, require_tier
from app.models.user import User
from app.schemas.tasks import CaptureRequest, CaptureResponse, TaskSubmitResponse
from app.services.capture_service import CaptureService
from app.tasks.queue import TaskQueue

router = APIRouter(prefix="/api/v1/capture", tags=["Packet Capture"])
capture_service = CaptureService()


@router.post("/start", response_model=TaskSubmitResponse)
async def start_capture(
    req: CaptureRequest,
    current_user: User = Depends(require_tier("pro")),
    queue: TaskQueue = Depends(get_task_queue),
):
    """启动抓包任务（Pro 专属，需 root 权限）"""
    task_id = await queue.submit(
        "capture",
        {
            "interface": req.interface,
            "duration": req.duration,
            "filter_expr": req.filter_expr,
            "packet_count": req.packet_count,
        },
        current_user.id,
    )
    return TaskSubmitResponse(task_id=task_id, task_type="capture", status="pending")
