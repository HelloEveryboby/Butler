import os
import json
import time
import uuid
import threading
from pathlib import Path
from typing import List, Dict, Any
from butler.core.task_manager import (
    create_task,
    load_task,
    list_tasks,
    claim_task,
    complete_task,
    can_start,
    _task_path,
    _save_task_unlocked,
    _load_task_unlocked,
    task_lock,
    Task,
    asdict
)

# ── Multi-Agent Orchestrator (编排高层层) ──

def decompose_task(macro_goal: str, sub_tasks: List[Dict[str, Any]]) -> str:
    """
    Decomposes a macro-level objective into a structured DAG of sub-tasks.
    Each sub-task maps its local temporary label to physical UUIDs.
    """
    # Step 1: Generate UUIDs and register labels to physical ID mappings
    label_to_id = {}
    with task_lock:
        for st in sub_tasks:
            temp_label = st.get("temp_label")
            unique_segment = uuid.uuid4().hex[:8]
            physical_id = f"task_{int(time.time())}_{unique_segment}"
            label_to_id[temp_label] = physical_id

        # Step 2: Create all task entries in the storage first (to pass dependency strong validation)
        created_tasks = []
        for st in sub_tasks:
            temp_label = st.get("temp_label")
            physical_id = label_to_id[temp_label]

            task = Task(
                id=physical_id,
                subject=st.get("subject", "Untitled Task"),
                description=f"[{macro_goal}] {st.get('description', '')}",
                status="pending",
                owner=None,
                blockedBy=[] # Fill this in next step
            )
            _save_task_unlocked(task)
            created_tasks.append((task, st.get("depends_on_labels", [])))

        # Step 3: Map temporary dependencies to physical UUIDs and save tasks
        for task, depends_on in created_tasks:
            physical_deps = []
            for dep_label in depends_on:
                if dep_label in label_to_id:
                    physical_deps.append(label_to_id[dep_label])
                else:
                    # If label not found, treat it as exact ID
                    physical_deps.append(dep_label)
            task.blockedBy = physical_deps
            _save_task_unlocked(task)

    # Compile report
    report = f"Successfully decomposed macro goal: '{macro_goal}' into {len(sub_tasks)} tasks.\n"
    for label, pid in label_to_id.items():
        report += f"  - {label} -> {pid}\n"
    return report


def run_decompose_task(**kwargs) -> str:
    try:
        macro_goal = kwargs.get("macro_goal")
        sub_tasks = kwargs.get("sub_tasks", [])
        if not macro_goal or not sub_tasks:
            return "Error: macro_goal and sub_tasks are required."
        return decompose_task(macro_goal, sub_tasks)
    except Exception as e:
        return f"Error during decomposition: {e}"


BUTLER_ORCHESTRATOR_TOOLS = [
    {
        "name": "decompose_task",
        "description": "Break down a complex, multi-step goal into a structured graph of sub-tasks with explicit standard dependencies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "macro_goal": {"type": "string", "description": "The high-level objective to achieve."},
                "sub_tasks": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "temp_label": {"type": "string", "description": "A local identifier to build dependencies, e.g., 'task_db_design'."},
                      "subject": {"type": "string", "description": "Short name of subtask"},
                      "description": {"type": "string", "description": "Details of the subtask requirements"},
                      "depends_on_labels": {"type": "array", "items": {"type": "string"}, "description": "Local temp_labels this task depends on."}
                    },
                    "required": ["temp_label", "subject"]
                  }
                }
            },
            "required": ["macro_goal", "sub_tasks"]
        }
    }
]

ORCHESTRATOR_HANDLERS = {
    "decompose_task": run_decompose_task
}


# ── Interactive Multi-Agent Dynamic Claiming Scenario Demo ──

class SimulatedTeammateAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.running = True

    def run_agent_loop(self):
        print(f"  \033[1;35m[Agent Ready]\033[0m {self.name} ({self.role}) initialized and listening for tasks.")
        while self.running:
            # Poll tasks
            tasks = list_tasks()
            # Find any unblocked pending task
            target_task = None
            for t in tasks:
                if t.status == "pending" and can_start(t.id):
                    # Check if the description contains role-matching tags or if this agent is ready to grab it
                    # In this simulation, any worker can grab an unblocked task
                    target_task = t
                    break

            if target_task:
                # Attempt to claim task
                print(f"  \033[1;33m[Claiming]\033[0m {self.name} is attempting to claim: '{target_task.subject}'...")
                res = claim_task(target_task.id, owner=self.name)
                if "Success" in res:
                    print(f"  \033[1;32m[Working]\033[0m {self.name} successfully claimed and is processing task: '{target_task.subject}'")
                    # Simulate performing work
                    time.sleep(1.5)
                    # Complete task
                    comp_res = complete_task(target_task.id)
                    print(f"  \033[1;36m[Completed]\033[0m {self.name} completed task: '{target_task.subject}'. Result: {comp_res.splitlines()[0]}")
                else:
                    print(f"  \033[1;31m[Collision]\033[0m {self.name} failed to claim task (probably grabbed by another teammate).")
            else:
                # No tasks available to start (either all done or blocked)
                time.sleep(0.5)


if __name__ == "__main__":
    print("\033[1;34m======================================================================\033[0m")
    print("\033[1;34m      Butler Multi-Agent Collaboration & Decomposition Demo           \033[0m")
    print("\033[1;34m======================================================================\033[0m")

    # Step 1: Clean tasks directory
    import shutil
    from butler.core.task_manager import TASKS_DIR
    if TASKS_DIR.exists():
        shutil.rmtree(TASKS_DIR)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    print("Step 1: Lead Agent is decomposing macro goal: '审计安全隐患并编写修复补丁'...")
    demo_macro_goal = "审计安全隐患并编写修复补丁"
    demo_subtasks = [
        {
            "temp_label": "task_scan",
            "subject": "代码安全漏洞扫描",
            "description": "对代码库运行静态和动态漏洞扫描，找出潜在漏洞。",
            "depends_on_labels": []
        },
        {
            "temp_label": "task_patch",
            "subject": "编写修复安全补丁",
            "description": "基于扫描结果编写漏洞修复补丁。",
            "depends_on_labels": ["task_scan"]
        },
        {
            "temp_label": "task_regression",
            "subject": "安全回归验证",
            "description": "验证补丁是否成功修复漏洞，并确保无功能退化。",
            "depends_on_labels": ["task_patch"]
        }
    ]

    decomp_report = decompose_task(demo_macro_goal, demo_subtasks)
    print("\033[1;32m✓ Decomposition complete!\033[0m")
    print(decomp_report)

    print("\nStep 2: Spawning virtual Teammate Agents...")
    agent_inspector = SimulatedTeammateAgent(name="Security_Inspector", role="Security Expert")
    agent_patcher = SimulatedTeammateAgent(name="Code_Patcher", role="Senior Developer")

    thread_inspector = threading.Thread(target=agent_inspector.run_agent_loop, daemon=True)
    thread_patcher = threading.Thread(target=agent_patcher.run_agent_loop, daemon=True)

    thread_inspector.start()
    thread_patcher.start()

    # Step 3: Monitor until all tasks are completed
    print("\nStep 3: Multi-agent asynchronous task flow running...")
    start_time = time.time()
    all_completed = False

    while time.time() - start_time < 10:
        tasks = list_tasks()
        if tasks and all(t.status == "completed" for t in tasks):
            all_completed = True
            break
        time.sleep(0.5)

    # Shutdown agents
    agent_inspector.running = False
    agent_patcher.running = False

    if all_completed:
        print("\n\033[1;32m======================================================================\033[0m")
        print("\033[1;32m🏆 All tasks successfully completed! Multi-agent flow finished.     \033[0m")
        print("\033[1;32m======================================================================\033[0m")
        for t in list_tasks():
            print(f"  ✓ [{t.status.upper()}] ID: {t.id} | Subject: {t.subject} | Owner: {t.owner}")
    else:
        print("\n\033[1;31m⚠ Simulation timed out or failed to complete all tasks.\033[0m")
