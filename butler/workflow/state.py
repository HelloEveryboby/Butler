# -*- coding: utf-8 -*-
from typing import Dict, Any, List

class WorkflowState:
    """
    跟踪并管理活跃运行工作流的状态机流转。
    """
    def __init__(self, workflow_name: str, steps: List[Dict[str, Any]]):
        self.workflow_name = workflow_name
        self.steps = steps
        self.status = "INIT" # INIT -> RUNNING -> SUCCESS / FAILED
        self.current_step_index = 0
        self.step_outputs: Dict[int, Any] = {}
        self.errors: List[str] = []

    def start(self):
        self.status = "RUNNING"

    def complete_step(self, step_index: int, output: Any):
        self.step_outputs[step_index] = output
        self.current_step_index = step_index + 1
        if self.current_step_index >= len(self.steps):
            self.status = "SUCCESS"

    def fail_step(self, step_index: int, error_msg: str):
        self.errors.append(f"步骤 {step_index} 运行失败: {error_msg}")
        self.status = "FAILED"
