import os
import json
import requests
import logging
from typing import Dict, Any, List, Optional
from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader
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

    def extract_intent(self, text: str, history: List[Any] = None) -> Dict[str, Any]:
        """使用 DeepSeek API 从用户文本中提取意图和实体。"""
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
            result_text = response.json()['choices'][0]['message']['content']

            if result_text.strip().startswith("```json"):
                result_text = result_text.strip()[7:-4].strip()

            return json.loads(result_text)
        except Exception as e:
            logger.error(f"NLU extraction failed: {e}")
            return {"intent": "unknown", "entities": {"error": str(e)}}

    def generate_general_response(self, text: str) -> str:
        """生成简单的聊天响应。"""
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
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"General response generation failed: {e}")
            return "抱歉，我暂时无法回答这个问题。"

    def ask_llm(self, prompt: str, history: List[Any] = None, use_habit: bool = True, stream: bool = False):
        """通用 LLM 问答接口，支持流式输出。"""
        system_prompt = self._get_augmented_system_prompt("general_response") if use_habit else self.prompts.get("general_response", {}).get("prompt", "")

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for item in history:
                role = item.metadata.get('role', 'user') if hasattr(item, 'metadata') else item.get('role', 'user')
                content = item.content if hasattr(item, 'content') else item.get('content', '')
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.2,
            "stream": stream
        }

        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            if stream:
                return self._stream_request(payload, headers)
            else:
                response = requests.post(self.url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"ask_llm failed: {e}")
            if stream:
                def error_gen(): yield f"Error: {e}"
                return error_gen()
            return f"Error: {e}"

    def _stream_request(self, payload, headers):
        """处理 DeepSeek 的流式响应。"""
        try:
            response = requests.post(self.url, headers=headers, json=payload, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        data_content = line_str[6:]
                        if data_content == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_content)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Streaming request failed: {e}")
            yield f"\n[Streaming Error: {e}]"
