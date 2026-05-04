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

    def analyze_failure(self, error_msg: str, context: Dict[str, Any]) -> str:
        """Uses LLM to analyze the error and provide a self-healing strategy."""
        logger.info(f"Analyzing failure: {error_msg}")

        prompt = (
            f"Butler 系统在执行任务时遇到了错误：\n"
            f"错误信息: {error_msg}\n"
            f"上下文信息: {json.dumps(context, ensure_ascii=False)}\n\n"
            f"请作为高级自愈工程师，分析错误原因并提供一个修复建议或备用方案。\n"
            f"如果可以尝试自动修复（例如重试、清理缓存、切换 API），请以 JSON 格式输出修复指令。\n"
            f"修复指令示例: {{\"action\": \"retry\", \"reason\": \"网络抖动\"}} 或 {{\"action\": \"fallback\", \"tool\": \"alternative_tool\"}}\n"
        )

        # Call LLM via NLU service
        try:
            analysis = self.jarvis.nlu_service.ask_llm(prompt, use_habit=False)
            logger.info(f"Self-healing analysis: {analysis}")
            return analysis
        except Exception as e:
            logger.error(f"Self-healing analysis failed: {e}")
            return "无法分析错误原因，请检查日志。"

    def apply_fix(self, fix_instruction: str):
        """Applies the suggested fix."""
        # Parse fix instruction if it's JSON
        try:
            # Logic to actually retry or fallback
            pass
        except:
            pass

self_healing = None # Initialized in Jarvis
