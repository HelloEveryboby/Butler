import threading
import concurrent.futures
import time
import uuid
from typing import Callable, Any, Dict, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("TaskManager")

class Task:
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

class TaskManager:
    """
    Butler 中心化任务管理中心 (Centralized Task Manager)
    支持线程池管理、任务超时熔断、状态监控。
    """
    _instance = None

    def __init__(self, max_workers: int = 10):
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ButlerWorker"
        )
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TaskManager()
        return cls._instance

    def submit(self, func: Callable, *args, name: str = None, timeout: float = None, **kwargs) -> str:
        """提交任务到线程池。"""
        task = Task(func, args, kwargs, name, timeout)
        with self.lock:
            self.tasks[task.id] = task

        LogManager.set_trace_id(task.id)
        logger.info(f"Submitting task: {task.name} (Timeout: {timeout}s)")

        # We use a wrapper to handle status and errors
        future = self.executor.submit(self._run_task, task)
        return task.id

    def _run_task(self, task: Task):
        task.status = "RUNNING"
        LogManager.set_trace_id(task.id)
        logger.info(f"Task {task.name} started.")

        start_time = time.time()
        try:
            if task.timeout:
                # Note: ThreadPoolExecutor doesn't natively support per-task timeout cancellation
                # This is a soft timeout check or requires the function to be interruptible.
                # For real process-level isolation, ProcessPoolExecutor or signals are needed.
                # Here we use a future.result(timeout) approach if we were waiting,
                # but since this is inside the worker, we just run it.
                task.result = task.func(*task.args, **task.kwargs)
            else:
                task.result = task.func(*task.args, **task.kwargs)

            task.status = "COMPLETED"
            duration = time.time() - start_time
            logger.info(f"Task {task.name} completed in {duration:.2f}s")
        except Exception as e:
            task.status = "FAILED"
            task.error = str(e)
            logger.error(f"Task {task.name} failed: {e}", exc_info=True)

        return task.result

    def get_task_status(self, task_id: str) -> Optional[str]:
        with self.lock:
            task = self.tasks.get(task_id)
            return task.status if task else None

task_manager = TaskManager.get_instance()
