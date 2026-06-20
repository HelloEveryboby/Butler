import logging
import json
from typing import Dict, Any, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("SelfHealing")

class SelfHealing:
    """
    Butler Self-Healing System: Analyzes failures and suggests fixes using LLM.
    """

    def __init__(self, jarvis_app):
        self.jarvis = jarvis_app

    def analyze_failure(self, error_msg: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Uses LLM to analyze the error and provide a structured self-healing strategy."""
        logger.info(f"Analyzing failure: {error_msg}")

        prompt = (
            f"Butler 系统在执行任务时遇到了错误：\n"
            f"错误信息: {error_msg}\n"
            f"上下文信息: {json.dumps(context, ensure_ascii=False)}\n\n"
            f"作为高级自愈工程师，请分析原因并决定下一步行动。\n"
            f"你必须返回一个 JSON 对象，包含以下字段：\n"
            f"- 'analysis': 字符串，对错误的简短分析。\n"
            f"- 'strategy': 字符串，取值范围为 ['retry', 'fallback', 'ignore', 'abort']。\n"
            f"- 'parameters': 字典，retry 时可包含新参数，fallback 时包含备用工具名。\n"
            f"- 'explanation': 字符串，给人看的解释。\n"
        )

        try:
            response = self.jarvis.nlu_service.ask_llm(prompt, use_habit=False)
            import re
            json_match = re.search(r"(\{.*\})", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except Exception as e:
            logger.error(f"Self-healing analysis failed: {e}")

        return {"strategy": "abort", "explanation": "无法自动修复。"}

self_healing = None # Initialized in Jarvis
