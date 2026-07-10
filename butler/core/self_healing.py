import logging
import json
import os
from typing import Dict, Any, Optional, List
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("SelfHealing")

class SelfHealing:
    """
    Butler Self-Healing System: Analyzes failures and suggests fixes using LLM.
    支持“最大重试3次”的硬件沙箱化阻断：超过3次则强行隔离/下线该故障技能。
    """

    def __init__(self, jarvis_app):
        self.jarvis = jarvis_app
        # 用于对失败技能/任务进行重试计数
        self.retry_counters: Dict[str, int] = {}
        # 隔离技能配置文件路径
        self.isolated_config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "isolated_skills.json"
        )
        self._load_isolated_skills()

    def _load_isolated_skills(self) -> List[str]:
        """加载已隔离下线的技能"""
        self.isolated_skills = []
        if os.path.exists(self.isolated_config_path):
            try:
                with open(self.isolated_config_path, 'r', encoding='utf-8') as f:
                    self.isolated_skills = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load isolated skills: {e}")
        return self.isolated_skills

    def _save_isolated_skills(self):
        """保存已隔离下线的技能"""
        try:
            os.makedirs(os.path.dirname(self.isolated_config_path), exist_ok=True)
            with open(self.isolated_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.isolated_skills, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save isolated skills: {e}")

    def isolate_skill(self, skill_name: str):
        """将有故障的技能执行强行隔离并下线"""
        if skill_name not in self.isolated_skills:
            self.isolated_skills.append(skill_name)
            self._save_isolated_skills()
            logger.warning(f"⚠️ 技能 '{skill_name}' 因超过最大自愈重试次数被加入硬件隔离下线名单！")

            # 从 SkillManager 内存状态中标记为 disabled/isolated
            if self.jarvis and hasattr(self.jarvis, 'skill_manager'):
                sm = self.jarvis.skill_manager
                if skill_name in sm.manifests:
                    # 动态下线/移除
                    try:
                        sm.manifests[skill_name]["status"] = "isolated"
                        logger.info(f"SkillManager successfully isolated internal status of: {skill_name}")
                    except Exception as e:
                        logger.error(f"Failed to adjust skill manifest status: {e}")

    def analyze_failure(self, error_msg: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Uses LLM to analyze the error and provide a structured self-healing strategy."""
        # 提取技能标识 (作为重试计数的 key)
        skill_name = context.get("intent") or "unknown_skill"

        # 检查是否已经被隔离
        if skill_name in self.isolated_skills:
            logger.info(f"Skill '{skill_name}' is already isolated. Aborting self-healing.")
            return {"strategy": "abort", "explanation": f"技能 {skill_name} 已由于过度故障被隔离，拒绝自愈尝试。"}

        # 计数自愈次数
        current_retries = self.retry_counters.get(skill_name, 0)
        if current_retries >= 3:
            # 已经尝试自愈重试了 3 次！熔断隔离下线该技能。
            self.isolate_skill(skill_name)
            return {
                "strategy": "abort",
                "explanation": f"由于该技能故障在尝试自愈 3 次后仍未恢复，主程序已启动硬件沙箱熔断，将该技能完全隔离下线。"
            }
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

        # 递增自愈重试次数
        self.retry_counters[skill_name] = current_retries + 1

        try:
            response = self.jarvis.nlu_service.ask_llm(prompt, use_habit=False)
            import re
            json_match = re.search(r"(\{.*\})", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
                # 即使 LLM 想要继续重试，也增加安全护栏，重试次数在此进行底层校验
                if result.get("strategy") == "retry" and self.retry_counters.get(skill_name, 0) >= 3:
                    self.isolate_skill(skill_name)
                    return {
                        "strategy": "abort",
                        "explanation": f"技能 {skill_name} 触发自愈策略达到最大限制，主程序强行执行三板斧熔断隔离。"
                    }
                return result
        except Exception as e:
            logger.error(f"Self-healing analysis failed: {e}")

        return {"strategy": "abort", "explanation": "无法自动修复。"}

self_healing = None # Initialized in Jarvis
