# -*- coding: utf-8 -*-
import os
import json
import logging
from typing import List, Dict, Any
from package.core_utils.config_loader import config_loader

logger = logging.getLogger(__name__)

class Planner:
    """
    负责将最终的任务总目标（Task Goal/Intent）转换为一系列有序的、可执行的子步骤（Sub-steps）。
    支持接入 OpenAI, Claude, DeepSeek 并能在无密钥环境下自动切入 Mock 规划器，维持执行闭环。
    """
    def __init__(self, use_mock: bool = None):
        self.api_key = config_loader.get("api.deepseek.key")

        # 如果没有配置 API Key，或者使用的是占位符，默认使用 Mock
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            self.use_mock = not self.api_key or "YOUR_" in str(self.api_key)

    def create_plan(self, task_input: str) -> List[Dict[str, Any]]:
        """
        根据用户输入，规划一个子步骤清单。
        """
        if self.use_mock:
            return self._create_mock_plan(task_input)

        try:
            return self._create_llm_plan(task_input)
        except Exception as e:
            logger.warning(f"大模型规划执行失败: {e}。已自动切入 Mock 模拟规划模式。")
            return self._create_mock_plan(task_input)

    def _create_mock_plan(self, task_input: str) -> List[Dict[str, Any]]:
        """
        为常见的高频任务生成结构美观的本地预置 Mock 规划模板。
        """
        lower_input = task_input.lower()

        # 1. 如果是邮件类任务
        if "mail" in lower_input or "邮件" in lower_input:
            return [
                {"id": "1", "action": "email-reader", "description": "抓取并读取未读邮件列表", "input": {}},
                {"id": "2", "action": "summarize", "description": "提炼并汇总所有关键邮件内容", "input": {"source_step": "1"}},
                {"id": "3", "action": "report_writer", "description": "生成最终的 Markdown 每日周报", "input": {"source_step": "2"}}
            ]

        # 2. 如果是报告或文件分析类任务
        if "report" in lower_input or "报告" in lower_input or "文件" in lower_input:
            return [
                {"id": "1", "action": "collect_data", "description": "抓取并收集本地业务数据记录", "input": {}},
                {"id": "2", "action": "summarize", "description": "分析并合并财务/业务核心指标", "input": {"source_step": "1"}},
                {"id": "3", "action": "generate_report", "description": "对格式化的最终报告进行排版美化输出", "input": {"source_step": "2"}}
            ]

        # 3. 兜底默认规划
        return [
            {"id": "1", "action": "analyze_intent", "description": "分解用户总需求的细节参数", "input": {"text": task_input}},
            {"id": "2", "action": "execute_mock_task", "description": "运行核心任务执行器", "input": {}},
            {"id": "3", "action": "compile_output", "description": "对执行成果进行汇总报告", "input": {}}
        ]

    def _create_llm_plan(self, task_input: str) -> List[Dict[str, Any]]:
        """
        调用真实大模型服务，生成规范化的任务 DAG 步骤清单。
        """
        from butler.core.nlu_service import NLUService
        prompts = {"system_prompt": "You are a professional Planner agent. Output JSON list of steps. Each step must have 'id', 'action', 'description', 'input'."}
        nlu = NLUService(self.api_key, prompts)

        prompt = (
            f"Please decompose this goal into a list of step objects.\n"
            f"Each step must be formatted as JSON with keys: 'id', 'action', 'description', 'input'.\n\n"
            f"Goal: {task_input}"
        )

        resp = nlu.ask_llm(prompt, [])
        import re
        match = re.search(r"(\[.*\])", resp, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        return self._create_mock_plan(task_input)
