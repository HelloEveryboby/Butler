import threading
import concurrent.futures
import time
import uuid
import json
import os
from pathlib import Path
from typing import Callable, Any, Dict, Optional, List
from dataclasses import dataclass, asdict
from filelock import FileLock
from package.core_utils.log_manager import LogManager
from butler.core.constants import DATA_DIR

logger = LogManager.get_logger("TaskManager")

# ── Volatile Background Worker Tasks ──

class VolatileTask:
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


# ── Persistent Business Task System ──

WORKDIR = Path.cwd()
TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)
LOCK_FILE = TASKS_DIR / "tasks.lock"
task_lock = FileLock(LOCK_FILE)


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str          # pending | in_progress | completed
    owner: str | None    # Agent name
    blockedBy: list[str] # Dependency task IDs


def _task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def _find_task_id(task_id: str | int) -> str:
    """Helper to flexibly search task ID by trailing digits, exact name, or numeric ID."""
    tid_str = str(task_id).strip()
    if tid_str.startswith("task_"):
        return tid_str

    # Exact JSON file check
    exact_path = TASKS_DIR / f"{tid_str}.json"
    if exact_path.exists():
        return tid_str

    # Search for match in task_*.json filenames
    for p in sorted(TASKS_DIR.glob("task_*.json")):
        stem = p.stem
        parts = stem.split("_")
        if tid_str in parts or stem.endswith(tid_str) or tid_str == stem:
            return stem

    return tid_str


# Unlocked private helper functions for file operations (to be called inside with task_lock)

def _save_task_unlocked(task: Task):
    _task_path(task.id).write_text(json.dumps(asdict(task), indent=2, ensure_ascii=False), encoding="utf-8")


def _load_task_unlocked(task_id: str) -> Task:
    path = _task_path(task_id)
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Task(
        id=data["id"],
        subject=data["subject"],
        description=data.get("description", ""),
        status=data.get("status", "pending"),
        owner=data.get("owner"),
        blockedBy=data.get("blockedBy", [])
    )


def _list_tasks_unlocked() -> list[Task]:
    tasks = []
    for p in sorted(TASKS_DIR.glob("task_*.json")):
        try:
            tasks.append(_load_task_unlocked(p.stem))
        except Exception:
            pass
    return tasks


def _can_start_unlocked(task_id: str) -> bool:
    """Check if all blockedBy dependencies are completed. Unlocked version."""
    try:
        task = _load_task_unlocked(task_id)
    except Exception:
        return False

    for dep_id in task.blockedBy:
        resolved_dep = _find_task_id(dep_id)
        if not _task_path(resolved_dep).exists():
            return False
        try:
            dep_task = _load_task_unlocked(resolved_dep)
            if dep_task.status != "completed":
                return False
        except Exception:
            return False
    return True


# Public Thread-Safe / Process-Safe Business Task API

def create_task(subject: str, description: str = "", blockedBy: list[str] | None = None) -> Task:
    deps = blockedBy or []
    with task_lock:
        # Strong validation of upstream dependencies
        for dep_id in deps:
            resolved_dep = _find_task_id(dep_id)
            if not _task_path(resolved_dep).exists():
                raise ValueError(f"Dependency task '{dep_id}' does not exist.")

        # High-entropy unique ID with timestamp and uuid4 hex segment to prevent collisions
        unique_segment = uuid.uuid4().hex[:8]
        task = Task(
            id=f"task_{int(time.time())}_{unique_segment}",
            subject=subject,
            description=description,
            status="pending",
            owner=None,
            blockedBy=[_find_task_id(d) for d in deps],
        )
        _save_task_unlocked(task)
    return task


def save_task(task: Task):
    with task_lock:
        _save_task_unlocked(task)


def load_task(task_id: str) -> Task:
    with task_lock:
        resolved = _find_task_id(task_id)
        return _load_task_unlocked(resolved)


def list_tasks() -> list[Task]:
    with task_lock:
        return _list_tasks_unlocked()


def get_task(task_id: str) -> str:
    with task_lock:
        resolved = _find_task_id(task_id)
        task = _load_task_unlocked(resolved)
        return json.dumps(asdict(task), indent=2, ensure_ascii=False)


def can_start(task_id: str) -> bool:
    with task_lock:
        resolved = _find_task_id(task_id)
        return _can_start_unlocked(resolved)


def claim_task(task_id: str, owner: str = "Butler") -> str:
    with task_lock:
        resolved = _find_task_id(task_id)
        task = _load_task_unlocked(resolved)
        if task.status != "pending":
            return f"Task {resolved} is {task.status}, cannot claim"
        if not _can_start_unlocked(resolved):
            deps = [d for d in task.blockedBy if not _task_path(_find_task_id(d)).exists() or _load_task_unlocked(_find_task_id(d)).status != "completed"]
            return f"Blocked by incomplete dependencies: {deps}"

        task.owner = owner
        task.status = "in_progress"
        _save_task_unlocked(task)
        return f"Success: Butler claimed {task.id} ({task.subject})"


def complete_task(task_id: str) -> str:
    with task_lock:
        resolved = _find_task_id(task_id)
        task = _load_task_unlocked(resolved)
        if task.status != "in_progress":
            return f"Task {resolved} is {task.status}, cannot complete"

        task.status = "completed"
        _save_task_unlocked(task)

        all_tasks = _list_tasks_unlocked()
        unblocked = [t.subject for t in all_tasks if t.status == "pending" and t.blockedBy and _can_start_unlocked(t.id)]
        msg = f"Success: Completed {task.id} ({task.subject})"
        if unblocked:
            msg += f"\nUnblocked downstream tasks: {', '.join(unblocked)}"
        return msg


# ── Butler Calling Interfaces ──

def run_create_task(**kwargs) -> str:
    try:
        task = create_task(kwargs.get("subject"), kwargs.get("description", ""), kwargs.get("blockedBy"))
        return f"Created {task.id}: {task.subject}"
    except Exception as e:
        return f"Error creating task: {e}"


def run_list_tasks(**kwargs) -> str:
    tasks = list_tasks()
    if not tasks:
        return "No tasks found."
    lines = []
    for t in tasks:
        icon = {"pending": "○", "in_progress": "●", "completed": "✓"}.get(t.status, "?")
        deps = f" (blockedBy: {', '.join(t.blockedBy)})" if t.blockedBy else ""
        owner = f" [{t.owner}]" if t.owner else ""
        lines.append(f"{icon} {t.id}: {t.subject} [{t.status}]{owner}{deps}")
    return "\n".join(lines)


def run_get_task(**kwargs) -> str:
    try:
        return get_task(kwargs.get("task_id"))
    except Exception as e:
        return f"Error: {e}"


def run_claim_task(**kwargs) -> str:
    try:
        return claim_task(kwargs.get("task_id"), owner=kwargs.get("owner", "Butler"))
    except Exception as e:
        return f"Error: {e}"


def run_complete_task(**kwargs) -> str:
    try:
        return complete_task(kwargs.get("task_id"))
    except Exception as e:
        return f"Error: {e}"


# ── Butler Tool Schema Definitions (BUTLER_TASK_TOOLS & TASK_HANDLERS) ──

BUTLER_TASK_TOOLS = [
    {
        "name": "create_task",
        "description": "Create a new task with optional blockedBy dependencies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Short title of the task"},
                "description": {"type": "string", "description": "Detailed requirements"},
                "blockedBy": {"type": "array", "items": {"type": "string"}, "description": "List of prerequisite task IDs"}
            },
            "required": ["subject"]
        }
    },
    {
        "name": "list_tasks",
        "description": "List all tasks within the system with statuses and dependencies.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_task",
        "description": "Retrieve full definition and metadata of a task by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"]
        }
    },
    {
        "name": "claim_task",
        "description": "Claim a pending task to change its state to in_progress.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "owner": {"type": "string"}},
            "required": ["task_id"]
        }
    },
    {
        "name": "complete_task",
        "description": "Mark an in-progress task as completed and check for downstream unblocks.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"]
        }
    }
]

TASK_HANDLERS = {
    "create_task": run_create_task,
    "list_tasks": run_list_tasks,
    "get_task": run_get_task,
    "claim_task": run_claim_task,
    "complete_task": run_complete_task
}


# ── TaskManager Central Dispatcher Class (v2.0 Enhanced) ──

class TaskManager:
    _instance = None

    def __init__(self, max_workers: int = 10):
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ButlerWorker"
        )
        self.volatile_tasks: Dict[str, VolatileTask] = {}
        self.lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TaskManager()
        return cls._instance

    # --- Volatile Background Tasks (Existing thread worker functionality) ---

    def submit(self, func: Callable, *args, name: str = None, timeout: float = None, **kwargs) -> str:
        """提交异步执行任务到线程池。"""
        task = VolatileTask(func, args, kwargs, name, timeout)
        with self.lock:
            self.volatile_tasks[task.id] = task

        LogManager.set_trace_id(task.id)
        logger.info(f"Submitting worker task: {task.name} (Timeout: {timeout}s)")
        self.executor.submit(self._run_task, task)
        return task.id

    def _run_task(self, task: VolatileTask):
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

    # --- Persistent Business Tasks (Delegated to s12 task_system backend) ---

    def create_business_task(self, subject: str, description: str = "") -> Dict[str, Any]:
        task = create_task(subject, description)
        logger.info(f"Created business task {task.id}: {subject}")
        return asdict(task)

    def get_business_task(self, tid: Any) -> Dict[str, Any]:
        task = load_task(tid)
        return asdict(task)

    def update_business_task(self, tid: Any, status: str = None, add_blocked_by: List[Any] = None, remove_blocked_by: List[Any] = None) -> Dict[str, Any]:
        with task_lock:
            resolved_tid = _find_task_id(tid)
            if status == "deleted":
                _task_path(resolved_tid).unlink(missing_ok=True)
                return {"id": tid, "status": "deleted"}

            task = _load_task_unlocked(resolved_tid)
            if status:
                if status == "completed":
                    if task.status != "completed":
                        task.status = "completed"
                else:
                    task.status = status

            if add_blocked_by:
                for b in add_blocked_by:
                    res_b = _find_task_id(b)
                    if not _task_path(res_b).exists():
                        raise ValueError(f"Dependency task '{b}' does not exist.")
                    if res_b not in task.blockedBy:
                        task.blockedBy.append(res_b)

            if remove_blocked_by:
                for b in remove_blocked_by:
                    res_b = _find_task_id(b)
                    if res_b in task.blockedBy:
                        task.blockedBy.remove(res_b)

            _save_task_unlocked(task)
            return asdict(task)

    def list_business_tasks(self) -> List[Dict[str, Any]]:
        return [asdict(t) for t in list_tasks()]

    def claim_business_task(self, tid: Any, owner: str) -> str:
        return claim_task(tid, owner=owner)


task_manager = TaskManager.get_instance()


# ── Standalone CLI Interactive Debugger Block ──

if __name__ == "__main__":
    import sys
    print("\033[1;36m==================================================\033[0m")
    print("\033[1;36m      Butler Task System — Persistent Board        \033[0m")
    print("\033[1;36m==================================================\033[0m")

    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print("  python -m butler.core.task_manager create <subject> [description] [--blocked-by <dep1,dep2>]")
        print("  python -m butler.core.task_manager list")
        print("  python -m butler.core.task_manager get <task_id>")
        print("  python -m butler.core.task_manager claim <task_id> [owner]")
        print("  python -m butler.core.task_manager complete <task_id>")
        sys.exit(0)

    cmd = args[0].lower()
    try:
        if cmd == "create":
            if len(args) < 2:
                print("Error: subject is required.")
                sys.exit(1)
            subject = args[1]
            description = ""
            blocked_by = []

            rem = args[2:]
            if rem:
                if "--blocked-by" in rem:
                    idx = rem.index("--blocked-by")
                    description = " ".join(rem[:idx])
                    if idx + 1 < len(rem):
                        blocked_by = [x.strip() for x in rem[idx+1].split(",") if x.strip()]
                else:
                    description = " ".join(rem)

            task = create_task(subject, description, blocked_by)
            print(f"\033[1;32m✓ Task created successfully!\033[0m")
            print(json.dumps(asdict(task), indent=2, ensure_ascii=False))

        elif cmd == "list":
            print(run_list_tasks())

        elif cmd == "get":
            if len(args) < 2:
                print("Error: task_id is required.")
                sys.exit(1)
            print(run_get_task(task_id=args[1]))

        elif cmd == "claim":
            if len(args) < 2:
                print("Error: task_id is required.")
                sys.exit(1)
            owner = args[2] if len(args) > 2 else "Butler"
            print(run_claim_task(task_id=args[1], owner=owner))

        elif cmd == "complete":
            if len(args) < 2:
                print("Error: task_id is required.")
                sys.exit(1)
            print(run_complete_task(task_id=args[1]))

        else:
            print(f"Unknown command: {cmd}")
    except Exception as e:
        print(f"\033[1;31mError:\033[0m {e}")
