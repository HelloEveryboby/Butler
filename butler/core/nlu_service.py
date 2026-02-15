import os
import json
import requests
import logging
from typing import Dict, Any, List
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class NLUService:
    def __init__(self, api_key: str, prompts: Dict[str, Any]):
        self.api_key = api_key
        self.prompts = prompts
        self.url = "https://api.deepseek.com/v1/chat/completions"

    def extract_intent(self, text: str, history: List[Any] = None) -> Dict[str, Any]:
        """使用 DeepSeek API 从用户文本中提取意图和实体。"""
        system_prompt = self.prompts.get("nlu_intent_extraction", {}).get("prompt", "Extract intent and entities as JSON.")

        # 动态注入可用意图和工具
        try:
            from .extension_manager import extension_manager
            from .intent_dispatcher import intent_registry

            tool_descriptions = []
            # 1. 获取已注册的硬编码意图
            for intent_name, doc in intent_registry.get_all_intents().items():
                tool_descriptions.append(f"- `{intent_name}`: {doc or '执行特定操作。'}")

            # 2. 获取动态加载的扩展工具（包、插件、外部程序）
            for tool in extension_manager.get_all_tools():
                # 避免与已注册意图重复描述
                if tool['name'] not in intent_registry.get_all_intents():
                    tool_descriptions.append(f"- `{tool['name']}`: {tool['description']}")

            tools_str = "\n".join(tool_descriptions)
            if "{{TOOLS}}" in system_prompt:
                system_prompt = system_prompt.replace("{{TOOLS}}", tools_str)
            else:
                # 回退：如果没有占位符，尝试将其附加到提示末尾
                system_prompt += f"\n\n可能的意图/工具列表:\n{tools_str}"
        except Exception as e:
            logger.error(f"Failed to inject dynamic tools into NLU prompt: {e}")

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
            result_text = response.json()['choices'][0]['message']['content']

            if result_text.strip().startswith("```json"):
                result_text = result_text.strip()[7:-4].strip()

            return json.loads(result_text)
        except Exception as e:
            logger.error(f"NLU extraction failed: {e}")
            return {"intent": "unknown", "entities": {"error": str(e)}}

    def generate_general_response(self, text: str) -> str:
        """生成简单的聊天响应。"""
        system_prompt = self.prompts.get("general_response", {}).get("prompt", "You are a helpful assistant.")
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
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"General response generation failed: {e}")
            return "抱歉，我暂时无法回答这个问题。"
