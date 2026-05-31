import threading
import concurrent.futures
import time
import uuid
import json
import os
from pathlib import Path
from typing import Callable, Any, Dict, Optional, List
from package.core_utils.log_manager import LogManager
from butler.core.constants import DATA_DIR

logger = LogManager.get_logger("TaskManager")

class Task:
    """Volatile background thread task."""
    def __init__(self, func: Callable, args=None, kwargs=None, name: str = None, timeout: float = None):
        self.id = str(uuid.uuid4())[:8]
        self.name = name or f"Task-{self.id}"
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.timeout = timeout
        self.created_at = time.time()
        self.status = "PENDING" # PENDING, RUNNING, COMPLETED, FAILED, TIMEOUT
        self.result = None
        self.error = None

class BusinessTask:
    """Persistent business/logical task for agents."""
    def __init__(self, tid: int, subject: str, description: str = "", status: str = "pending", owner: str = None, blocked_by: List[int] = None):
        self.id = tid
        self.subject = subject
        self.description = description
        self.status = status
        self.owner = owner
        self.blocked_by = blocked_by or []

    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "owner": self.owner,
            "blockedBy": self.blocked_by
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            tid=data["id"],
            subject=data["subject"],
            description=data.get("description", ""),
            status=data.get("status", "pending"),
            owner=data.get("owner"),
            blocked_by=data.get("blockedBy", [])
        )

class TaskManager:
    """
    Butler 中心化任务管理中心 (v2.0 增强版)
    整合了线程池调度 (Background Workers) 与 持久化任务看板 (Business Tasks)。
    """
    _instance = None

    def __init__(self, max_workers: int = 10):
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ButlerWorker"
        )
        self.volatile_tasks: Dict[str, Task] = {}
        self.tasks_dir = DATA_DIR / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TaskManager()
        return cls._instance

    # --- Volatile Background Tasks (Existing functionality) ---

    def submit(self, func: Callable, *args, name: str = None, timeout: float = None, **kwargs) -> str:
        """提交异步执行任务到线程池。"""
        task = Task(func, args, kwargs, name, timeout)
        with self.lock:
            self.volatile_tasks[task.id] = task

        LogManager.set_trace_id(task.id)
        logger.info(f"Submitting worker task: {task.name} (Timeout: {timeout}s)")
        self.executor.submit(self._run_task, task)
        return task.id

    def _run_task(self, task: Task):
        task.status = "RUNNING"
        LogManager.set_trace_id(task.id)
        logger.info(f"Worker task {task.name} started.")

        start_time = time.time()
        try:
            task.result = task.func(*task.args, **task.kwargs)
            task.status = "COMPLETED"
            duration = time.time() - start_time
            logger.info(f"Worker task {task.name} completed in {duration:.2f}s")
        except Exception as e:
            task.status = "FAILED"
            task.error = str(e)
            logger.error(f"Worker task {task.name} failed: {e}", exc_info=True)
        return task.result

    def get_volatile_status(self, task_id: str) -> Optional[str]:
        with self.lock:
            task = self.volatile_tasks.get(task_id)
            return task.status if task else None

    # --- Persistent Business Tasks (New functionality) ---

    def _get_next_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.tasks_dir.glob("task_*.json")]
        return max(ids, default=0) + 1

    def _save_b_task(self, task: BusinessTask):
        path = self.tasks_dir / f"task_{task.id}.json"
        path.write_text(json.dumps(task.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')

    def _load_b_task(self, tid: int) -> BusinessTask:
        path = self.tasks_dir / f"task_{tid}.json"
        if not path.exists():
            raise ValueError(f"Task #{tid} not found.")
        return BusinessTask.from_dict(json.loads(path.read_text(encoding='utf-8')))

    def create_business_task(self, subject: str, description: str = "") -> Dict[str, Any]:
        with self.lock:
            tid = self._get_next_id()
            task = BusinessTask(tid, subject, description)
            self._save_b_task(task)
            logger.info(f"Created business task #{tid}: {subject}")
            return task.to_dict()

    def get_business_task(self, tid: int) -> Dict[str, Any]:
        return self._load_b_task(tid).to_dict()

    def update_business_task(self, tid: int, status: str = None, add_blocked_by: List[int] = None, remove_blocked_by: List[int] = None) -> Dict[str, Any]:
        with self.lock:
            task = self._load_b_task(tid)
            if status:
                task.status = status
                if status == "completed":
                    # Unblock other tasks
                    for f in self.tasks_dir.glob("task_*.json"):
                        try:
                            t_data = json.loads(f.read_text(encoding='utf-8'))
                            if tid in t_data.get("blockedBy", []):
                                t_data["blockedBy"].remove(tid)
                                f.write_text(json.dumps(t_data, indent=2, ensure_ascii=False), encoding='utf-8')
                        except Exception: pass
                if status == "deleted":
                    (self.tasks_dir / f"task_{tid}.json").unlink(missing_ok=True)
                    return {"id": tid, "status": "deleted"}

            if add_blocked_by:
                task.blocked_by = list(set(task.blocked_by + add_blocked_by))
            if remove_blocked_by:
                task.blocked_by = [x for x in task.blocked_by if x not in remove_blocked_by]

            self._save_b_task(task)
            return task.to_dict()

    def list_business_tasks(self) -> List[Dict[str, Any]]:
        tasks = []
        for f in sorted(self.tasks_dir.glob("task_*.json")):
            try:
                tasks.append(json.loads(f.read_text(encoding='utf-8')))
            except Exception: pass
        return tasks

    def claim_business_task(self, tid: int, owner: str) -> str:
        with self.lock:
            task = self._load_b_task(tid)
            if task.status == "completed":
                return f"Task #{tid} is already completed."
            task.owner = owner
            task.status = "in_progress"
            self._save_b_task(task)
            return f"Claimed task #{tid} for {owner}"

task_manager = TaskManager.get_instance()
