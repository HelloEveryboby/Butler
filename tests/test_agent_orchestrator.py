import os
import shutil
import pytest
import threading
import time
from pathlib import Path
from butler.core.task_manager import (
    TASKS_DIR,
    list_tasks,
    load_task,
    can_start
)
from butler.core.agent_orchestrator import (
    decompose_task,
    run_decompose_task
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


def test_task_decomposition_logic():
    """Verify that decompose_task correctly parses temp labels and creates valid physical tasks with correct dependencies."""
    macro_goal = "Build a microservice"
    sub_tasks = [
        {
            "temp_label": "lbl_db",
            "subject": "Create DB schemas",
            "description": "Create Postgres schemas and tables.",
            "depends_on_labels": []
        },
        {
            "temp_label": "lbl_api",
            "subject": "Develop REST API",
            "description": "Implement CRUD endpoints in FastAPI.",
            "depends_on_labels": ["lbl_db"]
        }
    ]

    report = decompose_task(macro_goal, sub_tasks)
    assert "Successfully decomposed macro goal" in report
    assert "lbl_db" in report
    assert "lbl_api" in report

    # Retrieve all created tasks
    tasks = list_tasks()
    assert len(tasks) == 2

    # Map physical task subjects to objects
    task_map = {t.subject: t for t in tasks}
    assert "Create DB schemas" in task_map
    assert "Develop REST API" in task_map

    task_db = task_map["Create DB schemas"]
    task_api = task_map["Develop REST API"]

    # Verify relationships
    assert task_db.status == "pending"
    assert task_api.status == "pending"
    assert task_db.blockedBy == []
    assert task_api.blockedBy == [task_db.id]


def test_multi_agent_collaboration_simulation():
    """Verify a simulated dynamic claiming collaborative workflow across multiple concurrent agents."""
    macro_goal = "Audit safety"
    sub_tasks = [
        {
            "temp_label": "step1",
            "subject": "Run security scan",
            "description": "Analyze source code.",
            "depends_on_labels": []
        },
        {
            "temp_label": "step2",
            "subject": "Fix findings",
            "description": "Implement fixes.",
            "depends_on_labels": ["step1"]
        }
    ]

    decompose_task(macro_goal, sub_tasks)

    # We will simulate two agents: Inspector and Developer
    execution_order = []
    errors = []

    def inspector_loop():
        try:
            # Poll for step1
            for _ in range(50):
                tasks = list_tasks()
                target = next((t for t in tasks if t.subject == "Run security scan"), None)
                if target and target.status == "pending" and can_start(target.id):
                    # Claim
                    from butler.core.task_manager import claim_task, complete_task
                    claim_res = claim_task(target.id, owner="Inspector")
                    if "Success" in claim_res:
                        execution_order.append("Inspector started scan")
                        time.sleep(0.1)
                        complete_task(target.id)
                        execution_order.append("Inspector completed scan")
                        break
                time.sleep(0.02)
        except Exception as e:
            errors.append(e)

    def developer_loop():
        try:
            # Poll for step2 (Fix findings) which is blocked by step1
            for _ in range(50):
                tasks = list_tasks()
                target = next((t for t in tasks if t.subject == "Fix findings"), None)
                if target and target.status == "pending" and can_start(target.id):
                    # Claim
                    from butler.core.task_manager import claim_task, complete_task
                    claim_res = claim_task(target.id, owner="Developer")
                    if "Success" in claim_res:
                        execution_order.append("Developer started fix")
                        time.sleep(0.1)
                        complete_task(target.id)
                        execution_order.append("Developer completed fix")
                        break
                time.sleep(0.02)
        except Exception as e:
            errors.append(e)

    t_inspector = threading.Thread(target=inspector_loop, daemon=True)
    t_developer = threading.Thread(target=developer_loop, daemon=True)

    t_inspector.start()
    t_developer.start()

    t_inspector.join()
    t_developer.join()

    # Ensure no exceptions occurred
    assert len(errors) == 0

    # Ensure all tasks are completed
    tasks_after = list_tasks()
    assert all(t.status == "completed" for t in tasks_after)

    # Ensure order of execution is correct: Inspector must finish scan before Developer can start fix
    expected_sequence = [
        "Inspector started scan",
        "Inspector completed scan",
        "Developer started fix",
        "Developer completed fix"
    ]
    assert execution_order == expected_sequence
