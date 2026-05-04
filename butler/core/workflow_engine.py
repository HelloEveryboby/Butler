import json
import logging
import time
from typing import List, Dict, Any, Optional
from butler.core.event_bus import event_bus

logger = logging.getLogger("WorkflowEngine")

class WorkflowEngine:
    """
    Butler Workflow Engine: Orchestrates multi-step tasks.
    Supports sequential execution, simple branching, and state persistence.
    """

    def __init__(self, jarvis_app):
        self.jarvis = jarvis_app
        self.active_workflows = {}

    def create_workflow(self, name: str, steps: List[Dict[str, Any]]) -> str:
        workflow_id = f"wf_{int(time.time())}"
        self.active_workflows[workflow_id] = {
            "name": name,
            "steps": steps,
            "current_step": 0,
            "context": {},
            "status": "pending"
        }
        return workflow_id

    def execute_step(self, workflow_id: str):
        wf = self.active_workflows.get(workflow_id)
        if not wf or wf["status"] == "completed":
            return

        steps = wf["steps"]
        idx = wf["current_step"]

        if idx >= len(steps):
            wf["status"] = "completed"
            return "Workflow completed."

        step = steps[idx]
        wf["status"] = "running"

        logger.info(f"Executing workflow {workflow_id} step {idx}: {step.get('intent')}")

        # Execute the intent via Jarvis
        # We simulate a user command for the step
        intent = step.get("intent")
        entities = step.get("entities", {})

        # Merge context into entities
        entities.update(wf["context"])

        # Use Jarvis's internal dispatching or a direct skill call
        # For simplicity, we use the skill manager if it looks like a skill
        try:
            result = self.jarvis.skill_manager.execute(intent, entities.get("action", "run"), entities=entities, jarvis_app=self.jarvis)
            wf["context"][f"step_{idx}_result"] = result
            wf["current_step"] += 1

            if wf["current_step"] < len(steps):
                # Trigger next step after a short delay
                event_bus.emit("workflow_next", workflow_id)
            else:
                wf["status"] = "completed"
                self.jarvis.ui_print(f"✅ 工作流 '{wf['name']}' 已完成。", tag='system_message')

            return result
        except Exception as e:
            wf["status"] = "failed"
            wf["error"] = str(e)
            return f"Step failed: {e}"

workflow_engine = None # Initialized in Jarvis
