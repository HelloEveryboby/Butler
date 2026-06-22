import logging
import time
import uuid
import threading
from typing import List, Dict, Any, Optional, Callable
from collections import deque
from butler.core.event_bus import event_bus
from butler.core.algorithms import dras_manager

logger = logging.getLogger("WorkflowEngine")

class WorkflowStep:
    def __init__(self, step_id: str, intent: str, entities: Dict[str, Any] = None, depends_on: List[str] = None):
        self.id = step_id
        self.intent = intent
        self.entities = entities or {}
        self.depends_on = depends_on or []
        self.status = "pending" # pending, running, completed, failed
        self.result = None
        self.error = None
        self.retry_count = 0
        self.max_retries = 3

class Workflow:
    def __init__(self, name: str, steps: List[Dict[str, Any]]):
        self.id = f"wf_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.steps: Dict[str, WorkflowStep] = {}
        self.context = {}
        self.status = "pending"

        for s in steps:
            s_id = s.get("id") or f"step_{len(self.steps)}"
            self.steps[s_id] = WorkflowStep(
                s_id,
                s.get("intent"),
                s.get("entities"),
                s.get("depends_on", [])
            )

class WorkflowEngine:
    """
    Butler DAG Workflow Engine.
    支持拓扑排序执行、资源感知调度、容错重试。
    """
    def __init__(self, jarvis_app):
        self.jarvis = jarvis_app
        self.active_workflows: Dict[str, Workflow] = {}
        self.lock = threading.Lock()

    def create_workflow(self, name: str, steps: List[Dict[str, Any]]) -> str:
        wf = Workflow(name, steps)
        with self.lock:
            self.active_workflows[wf.id] = wf
        return wf.id

    def execute_workflow(self, workflow_id: str):
        wf = self.active_workflows.get(workflow_id)
        if not wf: return

        wf.status = "running"
        logger.info(f"Starting DAG Workflow: {wf.name} ({wf.id})")
        self._schedule_next_steps(wf)

    def _schedule_next_steps(self, wf: Workflow):
        """
        根据 DAG 依赖关系调度可以运行的任务。
        """
        with self.lock:
            if wf.status != "running": return

            ready_steps = []
            for step in wf.steps.values():
                if step.status == "pending":
                    # 检查所有依赖是否已完成
                    if all(wf.steps[dep_id].status == "completed" for dep_id in step.depends_on):
                        ready_steps.append(step)

            if not ready_steps:
                if all(s.status == "completed" for s in wf.steps.values()):
                    wf.status = "completed"
                    self.jarvis.ui_print(f"✅ 工作流 '{wf.name}' 执行成功。", tag='system_message')
                elif any(s.status == "failed" for s in wf.steps.values()):
                    wf.status = "failed"
                return

        for step in ready_steps:
            # 资源感知调度：如果系统负载过高，延迟执行
            allowed, msg = dras_manager.check_schedule_allowed()
            if not allowed:
                logger.warning(f"DRAS: {msg} Delaying step {step.id}")
                threading.Timer(2.0, self._schedule_next_steps, args=[wf]).start()
                return

            threading.Thread(target=self._run_step, args=(wf, step), daemon=True).start()

    def _run_step(self, wf: Workflow, step: WorkflowStep):
        step.status = "running"
        logger.info(f"Executing Step: {step.id} ({step.intent})")

        try:
            # 协作式压制：在执行前感知资源
            with dras_manager.cooperative_throttle():
                # 合并上下文数据
                merged_entities = step.entities.copy()
                # 注入上游结果作为引用 (e.g., $step_id.output)
                for sid, s in wf.steps.items():
                    if s.result:
                        merged_entities[f"input_{sid}"] = s.result

                result = self.jarvis.skill_manager.execute(
                    step.intent,
                    merged_entities.get("action", "run"),
                    entities=merged_entities,
                    jarvis_app=self.jarvis
                )

                # 如果返回的是字典且包含状态挂起，则视为特殊处理（如等待确认）
                if isinstance(result, dict) and result.get("status") == "pending_confirmation":
                    self.jarvis.ui_print(f"⚠️ 步骤 {step.id} 需要确认...", tag='system_message')
                    # 这里简化处理，暂不支持工作流中的交互式确认，实际应挂起整个 WF

                step.result = result
                step.status = "completed"
                logger.info(f"Step {step.id} completed.")

        except Exception as e:
            logger.error(f"Step {step.id} failed: {e}")
            if step.retry_count < step.max_retries:
                step.retry_count += 1
                step.status = "pending"
                logger.info(f"Retrying step {step.id} ({step.retry_count}/{step.max_retries})")
            else:
                step.status = "failed"
                step.error = str(e)
                wf.status = "failed"
                self.jarvis.ui_print(f"❌ 工作流 '{wf.name}' 在步骤 {step.id} 出错: {e}", tag='system_message')

        self._schedule_next_steps(wf)

    def get_workflow_status(self, workflow_id: str):
        wf = self.active_workflows.get(workflow_id)
        if not wf: return None
        return {
            "id": wf.id,
            "name": wf.name,
            "status": wf.status,
            "steps": {sid: s.status for sid, s in wf.steps.items()}
        }
