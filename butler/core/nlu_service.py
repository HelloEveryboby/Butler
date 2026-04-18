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
        """Augments the system prompt with the current user habit profile and available skills."""
        base_prompt = self.prompts.get(base_prompt_key, {}).get("prompt", "")
        habit_summary = habit_manager.get_profile_summary()

        # Skill metadata injection (Layer 1)
        from butler.core.skill_manager import SkillManager
        sm = SkillManager()
        # Mock load to get manifests if not already loaded in this instance
        skill_list = []
        for s_id, manifest in sm.manifests.items():
            desc = manifest.get("description", "No description")
            skill_list.append(f"  - {s_id}: {desc}")

        skills_summary = "\n可用专业技能 (使用 load_skill 加载详情):\n" + ("\n".join(skill_list) if skill_list else "  (无)")

        # Avoid adding conversational instructions for structured extraction tasks
        if base_prompt_key == "nlu_intent_extraction":
            return f"{base_prompt}\n\n{skills_summary}\n\n{habit_summary}\n\n注意：请仅在匹配意图时参考上述习惯和技能列表，并始终严格返回 JSON 格式。"

        personality_injection = (
            f"\n\n--- 🤖 核心记忆与协同协议 ---\n"
            f"以下是你通过长期交互学习到的用户偏好与默契，请将这些信息融入你的行为逻辑：\n"
            f"{habit_summary}\n"
            f"你要像一个多年老友一样，通过以上信息预判用户的需求，提供更默契、更个性化的响应。"
        )

        return f"{base_prompt}{personality_injection}"

    def extract_intent(self, text: str, history: List[Any] = None) -> Dict[str, Any]:
        """使用 DeepSeek API 从用户文本中提取意图和实体。"""
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

            return json.loads(result_text)
        except Exception as e:
            logger.error(f"NLU extraction failed: {e}")
            return {"intent": "unknown", "entities": {"error": str(e)}}

    def generate_general_response(self, text: str) -> str:
        """生成简单的聊天响应。"""
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

    def ask_llm(self, prompt: str, history: List[Any] = None, use_habit: bool = True, system_override: str = None) -> str:
        """通用 LLM 问答接口。"""
        if not quota_manager.check_quota():
            return "Error: API 额度已用尽。"

        if system_override:
            system_prompt = system_override
        else:
            system_prompt = self._get_augmented_system_prompt("general_response") if use_habit else self.prompts.get("general_response", {}).get("prompt", "")

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for item in history:
                if isinstance(item, dict):
                    role = item.get('role', 'user')
                    content = item.get('content', '')
                else:
                    role = item.metadata.get('role', 'user') if hasattr(item, 'metadata') else 'user'
                    content = item.content if hasattr(item, 'content') else str(item)
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "deepseek-chat",
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

    def micro_compact(self, messages: List[Dict[str, str]], keep_recent: int = 3) -> List[Dict[str, str]]:
        """微压缩：将较旧的工具执行结果替换为占位符。"""
        tool_indices = []
        for i, msg in enumerate(messages):
            if "I used tool" in msg.get("content", ""):
                tool_indices.append(i)

        if len(tool_indices) <= keep_recent:
            return messages

        # 仅保留最近 keep_recent 个工具结果的内容
        to_clear = tool_indices[:-keep_recent]
        for idx in to_clear:
            content = messages[idx]["content"]
            # 提取工具名
            import re
            match = re.search(r"I used tool '(.*?)'", content)
            tool_name = match.group(1) if match else "unknown"
            messages[idx]["content"] = f"I used tool '{tool_name}' [Output truncated for brevity]"

        return messages

    def compress_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """使用 LLM 压缩对话历史。"""
        if len(history) < 10:
            return history

        logger.info("Compressing conversation history...")
        # 选最后 15 条进行总结
        context_text = json.dumps(history[-15:], ensure_ascii=False)
        prompt = f"请简要总结以下对话的上下文以便维持后续对话的连续性，保留关键的任务状态、用户偏好和重要事实：\n\n{context_text}"

        summary = self.ask_llm(prompt, use_habit=False)
        return [
            {"role": "system", "content": f"以下是之前的对话摘要：{summary}"}
        ]
