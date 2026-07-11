import os
import shutil
import pytest
import threading
import time
from pathlib import Path
from butler.core.task_manager import (
    create_task,
    load_task,
    list_tasks,
    can_start,
    claim_task,
    complete_task,
    TASKS_DIR,
    Task,
    asdict
)

@pytest.fixture(autouse=True)
def clean_tasks_dir():
    """Ensure .tasks directory is completely clean before and after each test."""
    if TASKS_DIR.exists():
        shutil.rmtree(TASKS_DIR)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if TASKS_DIR.exists():
        shutil.rmtree(TASKS_DIR)


def test_create_and_load_task():
    """Verify file persistence and basic dataclass properties."""
    task = create_task(subject="Database migration", description="Migrate tables to V2")

    assert task.id.startswith("task_")
    assert task.subject == "Database migration"
    assert task.description == "Migrate tables to V2"
    assert task.status == "pending"
    assert task.owner is None
    assert task.blockedBy == []

    # Check that file exists on disk
    task_file = TASKS_DIR / f"{task.id}.json"
    assert task_file.exists()

    # Load from disk
    loaded = load_task(task.id)
    assert loaded.id == task.id
    assert loaded.subject == task.subject
    assert loaded.status == "pending"


def test_dependency_strong_validation():
    """Verify that creating a task with non-existent dependencies raises ValueError."""
    with pytest.raises(ValueError) as excinfo:
        create_task(subject="Deploy to Prod", blockedBy=["task_non_existent_1234"])

    assert "Dependency task 'task_non_existent_1234' does not exist." in str(excinfo.value)


def test_dependency_blocking_and_unblocking():
    """Verify that tasks cannot be started if they are blocked by uncompleted dependencies."""
    # Create upstream task A
    task_a = create_task(subject="Setup AWS")
    # Create downstream task B blocked by task A
    task_b = create_task(subject="Deploy Server", blockedBy=[task_a.id])

    # Task A has no dependencies, should be able to start
    assert can_start(task_a.id) is True
    # Task B is blocked by A (which is pending), should not be able to start
    assert can_start(task_b.id) is False

    # Attempt to claim B should fail
    claim_res = claim_task(task_b.id, owner="agent_bob")
    assert "Blocked by incomplete dependencies" in claim_res

    # Claim and complete A
    claim_task(task_a.id, owner="agent_alice")
    loaded_a = load_task(task_a.id)
    assert loaded_a.status == "in_progress"
    assert loaded_a.owner == "agent_alice"

    complete_res = complete_task(task_a.id)
    assert f"Completed {task_a.id}" in complete_res
    # Downstream task B should be listed as unblocked
    assert "Unblocked downstream tasks: Deploy Server" in complete_res

    # Task B should now be unblocked
    assert can_start(task_b.id) is True

    # Now claim task B successfully
    claim_res_b = claim_task(task_b.id, owner="agent_bob")
    assert f"Success: Butler claimed {task_b.id}" in claim_res_b
    assert load_task(task_b.id).status == "in_progress"


def test_list_tasks():
    """Verify list_tasks retrieves all created tasks in order."""
    task_1 = create_task(subject="Task 1")
    task_2 = create_task(subject="Task 2")

    all_tasks = list_tasks()
    assert len(all_tasks) == 2
    task_ids = [t.id for t in all_tasks]
    assert task_1.id in task_ids
    assert task_2.id in task_ids


def test_file_concurrency_locking():
    """Verify file locking under concurrent stress testing."""
    # Create initial task
    base_task = create_task(subject="Initial Work")
    claim_task(base_task.id, owner="InitialOwner")

    num_threads = 10
    threads = []
    errors = []

    def worker(worker_id):
        try:
            # Let multiple threads try to complete and/or view the task concurrently
            for _ in range(5):
                # Try reading/listing
                list_tasks()
                # Try getting details
                load_task(base_task.id)
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)

    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # There should be no concurrency/read/write corruption errors
    assert len(errors) == 0
