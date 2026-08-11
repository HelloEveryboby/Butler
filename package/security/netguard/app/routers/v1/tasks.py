"""任务队列路由"""

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user, get_store, get_task_queue
from app.models.user import User
from app.schemas.tasks import TaskListResponse, TaskStatusResponse, TaskSubmitResponse
from app.tasks.queue import TaskQueue

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    queue: TaskQueue = Depends(get_task_queue),
):
    task = await queue.get_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(
        task_id=task["task_id"],
        task_type=task["task_type"],
        status=task["status"],
        result=task.get("result") if task.get("result") else None,
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    task_type: str | None = None,
    current_user: User = Depends(get_current_user),
    queue: TaskQueue = Depends(get_task_queue),
):
    tasks = await queue.list_user_tasks(current_user.id, task_type)
    return TaskListResponse(
        tasks=[
            TaskStatusResponse(
                task_id=t["task_id"],
                task_type=t["task_type"],
                status=t["status"],
                result=t.get("result") if t.get("result") else None,
                created_at=t["created_at"],
                updated_at=t["updated_at"],
            )
            for t in tasks
        ]
    )
