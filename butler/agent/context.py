# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional

class AgentContext:
    """
    保存并维护数字员工在单次任务流转中的运行状态、当前规划和历史结果。
    """
    def __init__(self, task_id: str, task_input: str):
        self.task_id = task_id
        self.task_input = task_input
        self.plan_steps: List[Dict[str, Any]] = []
        self.execution_results: Dict[str, Any] = {}
        self.current_step_index: int = 0
        self.status: str = "pending" # e.g., pending, running, completed, failed
        self.final_report: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
