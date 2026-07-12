import os
import json
import requests
import logging
from typing import Dict, Any, List, Optional
from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader
from package.core_utils.quota_manager import quota_manager
from butler.core.habit_manager import habit_manager

logger = LogManager.get_logger(__name__)

class NLUService:
    def __init__(self, api_key: str, prompts: Dict[str, Any]):
        # Prefer the provided api_key (from .env or direct call), or fall back to centralized config
        self.api_key = api_key or config_loader.get("api.deepseek.key")
        self.prompts = prompts
        # Centralized endpoint with fallback
        self.url = config_loader.get("api.deepseek.endpoint", "https://api.deepseek.com/v1") + "/chat/completions"

    def _get_augmented_system_prompt(self, base_prompt_key: str) -> str:
        """Augments the system prompt with the current user habit profile."""
        base_prompt = self.prompts.get(base_prompt_key, {}).get("prompt", "")
        habit_summary = habit_manager.get_profile_summary()

        # Avoid adding conversational instructions for structured extraction tasks
        if base_prompt_key == "nlu_intent_extraction":
            return f"{base_prompt}\n\n{habit_summary}\n\n注意：请仅在匹配意图时参考上述习惯（例如通过历史确定常开的程序或模糊的文件路径），并始终严格返回 JSON 格式。"

        personality_injection = (
            f"\n\n--- 🤖 核心记忆与协同协议 ---\n"
            f"以下是你通过长期交互学习到的用户偏好与默契，请将这些信息融入你的行为逻辑：\n"
            f"{habit_summary}\n"
            f"你要像一个多年老友一样，通过以上信息预判用户的需求，提供更默契、更个性化的响应。"
        )

        return f"{base_prompt}{personality_injection}"

    def _is_prompt_injection(self, text: str) -> bool:
        """
        Detects common prompt injection patterns to protect the NLU Service boundary.
        """
        import re
        patterns = [
            r"(ignore|bypass|override)\s+(all\s+)?(previous|above)\s+(instructions|directives|prompts|rules)",
            r"system:\s*now\s+in\s+developer\s+mode",
            r"dan\s+mode",
            r"忽略(上述|之前|所有)?(指令|规则|提示词|设定|约束)",
            r"现在进入(开发者|developer|dan)模式",
            r"强制返回",
            r"--- end of text ---",
        ]
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def extract_intent(self, text: str, history: List[Any] = None) -> Dict[str, Any]:
        """使用 DeepSeek API 从用户文本中提取意图和实体。"""
        # 1. Input-side Prompt Injection Filter
        if self._is_prompt_injection(text):
            logger.warning(f"Prompt injection detected in extract_intent: '{text}'")
            return {"intent": "unauthorized_attempt", "entities": {"error": "Adversarial prompt injection attempt detected and blocked."}}

        if not self.api_key or "YOUR_" in self.api_key:
             return {"intent": "unknown", "entities": {"error": "DeepSeek API Key missing or placeholder"}}

        if not quota_manager.check_quota():
            logger.error("API 额度已用尽，提取意图停止。")
            return {"intent": "quota_exceeded", "entities": {}}

        system_prompt = self._get_augmented_system_prompt("nlu_intent_extraction")

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for item in history:
                role = item.metadata.get('role', 'user') if hasattr(item, 'metadata') else item.get('role', 'user')
                content = item.content if hasattr(item, 'content') else item.get('content', '')
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": text})

        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0
        }

        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            response = requests.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            resp_json = response.json()

            # Update quota based on tokens consumed
            usage = resp_json.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            if total_tokens > 0:
                quota_manager.update_usage(total_tokens)

            result_text = resp_json['choices'][0]['message']['content']

            if result_text.strip().startswith("```json"):
                result_text = result_text.strip()[7:-4].strip()

            # Output-side structural & content validation (JSON Schema/Safety)
            try:
                parsed = json.loads(result_text)
                if not isinstance(parsed, dict) or "intent" not in parsed or "entities" not in parsed:
                    raise ValueError("JSON does not conform to intent schema")

                # Check for malicious script/command leakage inside JSON values
                import re
                forbidden_patterns = [r"os\s*\.\s*system", r"subprocess\s*\.", r"exec\s*\(", r"eval\s*\("]
                def check_malicious_values(val):
                    if isinstance(val, str):
                        for fp in forbidden_patterns:
                            if re.search(fp, val):
                                raise ValueError("Malicious execution patterns detected inside JSON entity values.")
                    elif isinstance(val, dict):
                        for k, v in val.items():
                            check_malicious_values(v)
                    elif isinstance(val, list):
                        for v in val:
                            check_malicious_values(v)

                check_malicious_values(parsed)
                return parsed
            except Exception as schema_err:
                logger.error(f"JSON Schema/Safety verification failed: {schema_err}")
                return {"intent": "malformed_response", "entities": {"error": f"JSON Schema/Safety validation failed: {str(schema_err)}"}}
        except Exception as e:
            logger.error(f"NLU extraction failed: {e}")
            return {"intent": "unknown", "entities": {"error": str(e)}}

    def generate_general_response(self, text: str) -> str:
        """生成简单的聊天响应。"""
        # 1. Input-side Prompt Injection Filter
        if self._is_prompt_injection(text):
            logger.warning(f"Prompt injection detected in generate_general_response: '{text}'")
            return "对不起，您的输入包含不安全的安全载荷，请求已被拦截。"

        if not quota_manager.check_quota():
            return "对不起，API 额度已用尽。请联系管理员充值或提高限额。"

        system_prompt = self._get_augmented_system_prompt("general_response")
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "max_tokens": 150,
            "temperature": 0.5
        }
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            response = requests.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            resp_json = response.json()

            # Update quota
            usage = resp_json.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            if total_tokens > 0:
                quota_manager.update_usage(total_tokens)

            return resp_json['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"General response generation failed: {e}")
            return "抱歉，我暂时无法回答这个问题。"

    def ask_llm(self, prompt: str, history: List[Any] = None, use_habit: bool = True, system_override: str = None, image_b64: str = None) -> str:
        """通用 LLM 问答接口，支持多模态输入。"""
        # 1. Input-side Prompt Injection Filter
        if self._is_prompt_injection(prompt):
            logger.warning(f"Prompt injection detected in ask_llm: '{prompt}'")
            return "【安全拦截】系统检测到潜在的提示词注入或越权攻击载荷，该请求已被安全过滤器拦截。"

        if not self.api_key or "YOUR_" in self.api_key:
            return "【离线提示】当前未配置 API 密钥，仅支持本地指令。如需进行智能对话，请在设置中完成 API 配置。"

        if not quota_manager.check_quota():
            return "Error: API 额度已用尽。"

        # 如果存在图片，注入视觉分析指令
        if image_b64 and not system_override:
            vision_instruction = (
                "\n\n--- 👁️ 视觉辅助分析模式 ---\n"
                "用户提供了一张当前屏幕的截图。请结合图片内容进行分析：\n"
                "1. **排障识别**: 如果图片包含错误弹窗、报错日志或 UI 异常，请精准定位问题并给出修复建议。\n"
                "2. **上下文关联**: 图片反映了用户的操作环境，请根据 UI 状态判断用户的真实意图。\n"
                "3. **一键修复**: 如果识别出明确的软件错误，请尝试给出自动化修复的指令或脚本建议。"
            )
            system_prompt = self._get_augmented_system_prompt("general_response") + vision_instruction
        elif system_override:
            system_prompt = system_override
        else:
            system_prompt = self._get_augmented_system_prompt("general_response") if use_habit else self.prompts.get("general_response", {}).get("prompt", "")

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for item in history:
                if isinstance(item, dict):
                    role = item.get('role', 'user')
                    content = item.get('content', '')
                    # 保持历史中的多模态结构（如果有）
                    messages.append({"role": role, "content": content})
                else:
                    role = item.metadata.get('role', 'user') if hasattr(item, 'metadata') else 'user'
                    content = item.content if hasattr(item, 'content') else str(item)
                    messages.append({"role": role, "content": content})

        # 构建当前用户消息
        user_content = prompt
        if image_b64:
            # 如果提供了图片，则转换为多模态消息格式
            user_content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                }
            ]

        messages.append({"role": "user", "content": user_content})

        # 动态选择模型：如果有图片，则尝试使用支持多模态的模型 (如 gpt-4o 或 deepseek-vl)
        # 这里默认尝试使用配置中的模型，或者根据有无图片自动切换
        model = config_loader.get("api.deepseek.model", "deepseek-chat")
        if image_b64 and model == "deepseek-chat":
            model = "gpt-4o" # 默认降级/切换到 GPT-4o 处理图片，如果 DeepSeek 不支持

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.2
        }

        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            response = requests.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            resp_json = response.json()

            # Update quota
            usage = resp_json.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            if total_tokens > 0:
                quota_manager.update_usage(total_tokens)

            return resp_json['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"ask_llm failed: {e}")
            return f"Error: {e}"

    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """极简 Token 估算 (字符数/3)。"""
        return sum(len(m.get('content', '')) for m in messages) // 3

    def compress_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """使用 LLM 压缩对话历史。"""
        if len(history) < 10:
            return history

        logger.info("Compressing conversation history...")
        context_text = json.dumps(history[-15:], ensure_ascii=False)
        prompt = f"请简要总结以下对话的上下文以便维持后续对话的连续性，保留关键的任务状态、用户偏好和重要事实：\n\n{context_text}"

        summary = self.ask_llm(prompt, use_habit=False)
        return [
            {"role": "system", "content": f"以下是之前的对话摘要：{summary}"}
        ]
