import logging
import json
import re
from typing import Dict, Any, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("SelfHealing")

# ── 规则引擎：基于错误模式的快速 fallback 映射 ──────────────────
# 在调用 LLM 之前先尝试规则匹配，避免不必要的 API 调用和延迟
_FALLBACK_RULES: list[dict[str, Any]] = [
    {
        "pattern": r"(?i)(connection\s*refused|timeout|timed?\s*out|unreachable)",
        "strategy": "retry",
        "parameters": {"delay": 2, "max_retries": 3},
        "explanation": "网络连接超时，将自动重试。",
    },
    {
        "pattern": r"(?i)(rate\s*limit|429|too\s*many\s*requests)",
        "strategy": "retry",
        "parameters": {"delay": 30, "max_retries": 1},
        "explanation": "API 速率限制，等待后重试。",
    },
    {
        "pattern": r"(?i)(module\s*not\s*found|import\s*error|no\s*module)",
        "strategy": "fallback",
        "parameters": {"tool": "pip_install"},
        "explanation": "缺少依赖模块，尝试自动安装。",
    },
    {
        "pattern": r"(?i)(permission\s*denied|access\s*denied|forbidden|403)",
        "strategy": "abort",
        "parameters": {},
        "explanation": "权限不足，需要用户手动授权。",
    },
    {
        "pattern": r"(?i)(file\s*not\s*found|no\s*such\s*file|404)",
        "strategy": "fallback",
        "parameters": {"tool": "search_file"},
        "explanation": "文件未找到，尝试搜索替代文件。",
    },
    {
        "pattern": r"(?i)(syntax\s*error|invalid\s*syntax|parse\s*error)",
        "strategy": "fallback",
        "parameters": {"tool": "code_review"},
        "explanation": "代码语法错误，触发代码审查。",
    },
    {
        "pattern": r"(?i)(out\s*of\s*memory|oom|memory\s*error)",
        "strategy": "abort",
        "parameters": {},
        "explanation": "内存不足，建议关闭其他程序后重试。",
    },
]


def _match_rules(error_msg: str) -> Optional[dict[str, Any]]:
    """通过正则模式匹配错误，返回规则匹配结果或 None。"""
    for rule in _FALLBACK_RULES:
        if re.search(rule["pattern"], error_msg):
            logger.info(f"规则匹配命中: strategy={rule['strategy']}, pattern={rule['pattern'][:40]}")
            return {
                "strategy": rule["strategy"],
                "parameters": rule["parameters"],
                "explanation": rule["explanation"],
                "analysis": f"规则引擎匹配: {rule['pattern'][:60]}",
            }
    return None


class SelfHealing:
    """
    Butler Self-Healing System: Analyzes failures and suggests fixes.

    两阶段策略：
    1. 规则引擎快速匹配常见错误模式（零延迟，不调用 LLM）
    2. 规则未命中时，降级到 LLM 深度分析
    """

    def __init__(self, jarvis_app):
        self.jarvis = jarvis_app

    def analyze_failure(self, error_msg: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析失败并返回自愈策略。

        优先使用规则引擎匹配常见错误，未命中时降级到 LLM 分析。
        """
        logger.info(f"Analyzing failure: {error_msg[:200]}")

        # Phase 1: 规则引擎快速匹配
        rule_result = _match_rules(error_msg)
        if rule_result:
            logger.info(f"规则引擎命中，跳过 LLM 分析: {rule_result['strategy']}")
            return rule_result

        # Phase 2: LLM 深度分析
        return self._llm_analyze(error_msg, context)

    def _llm_analyze(self, error_msg: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用 LLM 进行深度错误分析。"""
        prompt = (
            f"Butler 系统在执行任务时遇到了错误：\n"
            f"错误信息: {error_msg}\n"
            f"上下文信息: {json.dumps(context, ensure_ascii=False, default=str)}\n\n"
            f"作为高级自愈工程师，请分析原因并决定下一步行动。\n"
            f"你必须返回一个 JSON 对象，包含以下字段：\n"
            f"- 'analysis': 字符串，对错误的简短分析。\n"
            f"- 'strategy': 字符串，取值范围为 ['retry', 'fallback', 'ignore', 'abort']。\n"
            f"- 'parameters': 字典，retry 时可包含新参数，fallback 时包含备用工具名。\n"
            f"- 'explanation': 字符串，给人看的解释。\n"
        )

        try:
            response = self.jarvis.nlu_service.ask_llm(prompt, use_habit=False)
            json_match = re.search(r"(\{.*\})", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
                result.setdefault("analysis", "LLM 分析完成")
                return result
        except Exception as e:
            logger.error(f"Self-healing LLM analysis failed: {e}")

        return {"strategy": "abort", "explanation": "无法自动修复，规则引擎和 LLM 均未命中。"}

    def add_rule(self, pattern: str, strategy: str, parameters: dict, explanation: str) -> None:
        """运行时动态添加自愈规则。"""
        _FALLBACK_RULES.append({
            "pattern": pattern,
            "strategy": strategy,
            "parameters": parameters,
            "explanation": explanation,
        })
        logger.info(f"新增自愈规则: pattern={pattern[:40]}, strategy={strategy}")

self_healing = None # Initialized in Jarvis
