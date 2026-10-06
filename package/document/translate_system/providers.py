"""翻译源适配层。

与 frontend/translate 的 Provider 设计保持一致，Python 端使用 requests 实现。
支持：DeepSeek / OpenAI 兼容 / Google 免费 / 微软免费 / DeepL / 百度 / 本地 LLM。
"""

from __future__ import annotations

import hashlib
import re
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import requests

from .config import ProviderConfig


class TranslationProvider(ABC):
    """翻译源统一接口。"""

    id: str
    name: str
    is_local: bool = False   # 是否本地源（离线模式下只允许本地源）

    # system prompt 追加片段（术语约束 / 专家预设 / 文档上下文），由引擎注入
    _prompt_extras: str = ""
    # few-shot 示例（TM 相似命中时注入）
    _fewshot: List[Tuple[str, str]] = []

    def set_prompt_extras(self, extras: str) -> None:
        """注入 system prompt 追加片段（术语约束 / 预设 / 上下文）。"""
        self._prompt_extras = extras or ""

    def set_fewshot(self, pairs: List[Tuple[str, str]]) -> None:
        """注入 few-shot 翻译示例（来自翻译记忆库的相似命中）。"""
        self._fewshot = list(pairs or [])

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """直接对话调用（供 AI 上下文构建等使用）。默认不支持。"""
        raise NotImplementedError(f"{self.name} does not support chat")

    @abstractmethod
    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        ...

    def translate_batch(self, texts: List[str], from_lang: str, to_lang: str) -> List[str]:
        """默认逐条翻译，支持批量的源可覆写。"""
        return [self.translate(t, from_lang, to_lang) for t in texts]


# ---------- OpenAI 兼容（DeepSeek / GPT / Ollama 等） ----------

class OpenAICompatProvider(TranslationProvider):
    id = "openai-compat"

    def __init__(self, config: ProviderConfig):
        self.name = config.name or "OpenAI 兼容"
        self.endpoint = (config.endpoint or "https://api.deepseek.com/v1").rstrip("/")
        self.api_key = config.api_key or ""
        self.model = config.model or "deepseek-chat"
        self.prompt = config.prompt or (
            "请将以下{from}文本翻译为{to}，只输出译文，不要解释、不要加引号、不要附加任何其他内容。"
            "必须严格保留原文中的换行符、缩进和空白字符，译文的排版与原文完全一致。"
        )

    def _system_prompt(self, from_lang: str, to_lang: str) -> str:
        from .languages import lang_name
        base = self.prompt.replace("{from}", lang_name(from_lang)).replace("{to}", lang_name(to_lang))
        # 注入：专家预设 + 术语强制约束 + 文档上下文（由 engine 组合后传入）
        if self._prompt_extras:
            base = f"{self._prompt_extras}\n\n{base}"
        return base

    def _fewshot_messages(self, text: str) -> List[dict]:
        """把 TM 的相似翻译对组装成 few-shot 消息。"""
        msgs: List[dict] = []
        for src, tgt in self._fewshot:
            msgs.append({"role": "user", "content": src})
            msgs.append({"role": "assistant", "content": tgt})
        return msgs

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """直接对话调用（上下文构建 / 术语抽取）。"""
        return self._post([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

    def _post(self, messages, max_tokens=4096, temperature=0.1):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(
            f"{self.endpoint}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        content = self._post(
            [
                {"role": "system", "content": self._system_prompt(from_lang, to_lang)},
                *self._fewshot_messages(text),
                {"role": "user", "content": text},
            ]
        )
        # 去掉模型可能加的引号
        if len(content) >= 2 and (
            (content[0] == '"' and content[-1] == '"')
            or (content[0] == "「" and content[-1] == "」")
        ):
            content = content[1:-1]
        return content

    def translate_batch(self, texts: List[str], from_lang: str, to_lang: str) -> List[str]:
        numbered = "\n\n".join(f"[{i}] {t}" for i, t in enumerate(texts))
        user_msg = (
            "请逐条翻译以下文本，保持编号格式不变，每条翻译后空一行。"
            "每条内部的换行符和空白必须严格保留，排版与原文一致：\n\n"
            f"{numbered}"
        )
        content = self._post(
            [
                {"role": "system", "content": self._system_prompt(from_lang, to_lang)},
                *self._fewshot_messages(numbered),
                {"role": "user", "content": user_msg},
            ],
            max_tokens=8192,
        )
        results: List[str] = [""] * len(texts)
        current = -1
        for line in content.split("\n"):
            m = re.match(r"^\[(\d+)\]\s*(.*)", line)
            if m:
                current = int(m.group(1))
                results[current] = m.group(2)
            elif current >= 0 and line.strip():
                results[current] += "\n" + line.strip()
        for i in range(len(results)):
            if not results[i]:
                results[i] = texts[i]
        return results


# ---------- Google 免费翻译 ----------

class GoogleFreeProvider(TranslationProvider):
    id = "google-free"
    name = "Google 免费翻译"

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={from_lang}&tl={to_lang}&dt=t&q={requests.utils.quote(text)}"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data or not data[0]:
            raise ValueError("Google translate: empty result")
        return "".join(item[0] for item in data[0])

    def translate_batch(self, texts: List[str], from_lang: str, to_lang: str) -> List[str]:
        separator = "\n\n"
        joined = separator.join(texts)
        translated = self.translate(joined, from_lang, to_lang)
        parts = translated.split("\n\n")
        if len(parts) != len(texts):
            return super().translate_batch(texts, from_lang, to_lang)
        return parts


# ---------- 微软免费翻译 ----------

class BingFreeProvider(TranslationProvider):
    id = "bing-free"
    name = "微软免费翻译"

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry = 0.0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token
        resp = requests.get("https://edge.microsoft.com/translate/auth", timeout=30)
        resp.raise_for_status()
        self._token = resp.text
        self._token_expiry = time.time() + 8 * 60
        return self._token

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        return self.translate_batch([text], from_lang, to_lang)[0]

    def translate_batch(self, texts: List[str], from_lang: str, to_lang: str) -> List[str]:
        token = self._get_token()
        url = (
            "https://api-edge.cognitive.microsofttranslator.com/translate"
            f"?api-version=3.0&from={from_lang}&to={to_lang}"
        )
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=[{"Text": t} for t in texts],
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["translations"][0]["text"] for item in data]


# ---------- DeepL ----------

class DeepLProvider(TranslationProvider):
    id = "deepl"
    name = "DeepL"

    def __init__(self, config: ProviderConfig):
        self.api_key = config.api_key or ""
        endpoint = (config.endpoint or "").lower()
        self.free = (not endpoint) or ("free" in endpoint)

    @property
    def endpoint(self) -> str:
        return (
            "https://api-free.deepl.com/v2/translate"
            if self.free
            else "https://api.deepl.com/v2/translate"
        )

    @staticmethod
    def _lang(code: str) -> str:
        return code.replace("-", "_").split("_")[0].upper()

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        return self.translate_batch([text], from_lang, to_lang)[0]

    def translate_batch(self, texts: List[str], from_lang: str, to_lang: str) -> List[str]:
        data = {"text": texts, "target_lang": self._lang(to_lang)}
        if from_lang != "auto":
            data["source_lang"] = self._lang(from_lang)
        resp = requests.post(
            self.endpoint,
            headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
            data=data,
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        return [t["text"] for t in result.get("translations", [])]


# ---------- 百度翻译 ----------

class BaiduProvider(TranslationProvider):
    id = "baidu"
    name = "百度翻译"

    def __init__(self, config: ProviderConfig):
        parts = (config.api_key or "").split(":")
        self.app_id = parts[0] if len(parts) > 0 else ""
        self.secret_key = parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _lang(code: str) -> str:
        return "zh" if code == "zh-CN" else code

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        salt = str(int(time.time() * 1000))
        sign_str = self.app_id + text + salt + self.secret_key
        sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
        params = {
            "q": text,
            "from": self._lang(from_lang),
            "to": self._lang(to_lang),
            "appid": self.app_id,
            "salt": salt,
            "sign": sign,
        }
        resp = requests.get(
            "https://fanyi-api.baidu.com/api/trans/vip/translate",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error_code" in data:
            raise ValueError(f"Baidu: {data.get('error_msg')} ({data['error_code']})")
        return "\n".join(item["dst"] for item in data.get("trans_result", []))


# ---------- 本地 LLM（Ollama / llama.cpp 等 OpenAI 兼容接口） ----------

# 常见本地推理服务端点（按顺序探测）
LOCAL_LLM_ENDPOINTS = (
    "http://127.0.0.1:11430/v1",
    "http://127.0.0.1:11434/v1",
    "http://127.0.0.1:8000/v1",
)


class LocalLLMProvider(OpenAICompatProvider):
    """本地 LLM 翻译源（Ollama / llama.cpp 的 OpenAI 兼容 HTTP 接口）。

    完全离线可用，是 offline_mode 下唯一允许的翻译源。
    """

    id = "local-llm"
    is_local = True

    def __init__(self, config: Optional[ProviderConfig] = None):
        config = config or ProviderConfig(id="local-llm", type="local-llm", name="本地 LLM")
        super().__init__(config)
        self.name = config.name or "本地 LLM"
        self.endpoint = (config.endpoint or LOCAL_LLM_ENDPOINTS[0]).rstrip("/")
        self.api_key = config.api_key or "local"
        self.model = config.model or "qwen2.5:7b"


def list_local_models(endpoints: Optional[List[str]] = None,
                      timeout: float = 3.0) -> List[dict]:
    """探测本地可用模型。

    依次请求各本地端点的 `/models`，返回
    `[{'endpoint':..., 'model':...}, ...]`；全部失败时返回空列表。
    """
    found: List[dict] = []
    for ep in (endpoints or list(LOCAL_LLM_ENDPOINTS)):
        ep = ep.rstrip("/")
        try:
            resp = requests.get(f"{ep}/models", timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("data", []):
                model_id = item.get("id")
                if model_id:
                    found.append({"endpoint": ep, "model": model_id})
        except Exception:  # noqa: BLE001
            continue
    return found


# ---------- 降级链 ----------

class FallbackProvider(TranslationProvider):
    """按优先级依次尝试多个翻译源。"""

    def __init__(self, providers: List[TranslationProvider]):
        self.providers = providers
        self.id = providers[0].id if providers else "fallback"
        self.name = f"{providers[0].name}（含降级）" if providers else "Fallback"
        self.is_local = all(p.is_local for p in providers) if providers else False

    def set_prompt_extras(self, extras: str) -> None:
        super().set_prompt_extras(extras)
        for p in self.providers:
            p.set_prompt_extras(extras)

    def set_fewshot(self, pairs) -> None:
        super().set_fewshot(pairs)
        for p in self.providers:
            p.set_fewshot(pairs)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        last_error: Optional[Exception] = None
        for provider in self.providers:
            try:
                return provider.chat(system_prompt, user_prompt)
            except NotImplementedError:
                continue
            except Exception as e:  # noqa: BLE001
                last_error = e
        if last_error:
            raise last_error
        raise NotImplementedError("No provider supports chat")

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        last_error: Optional[Exception] = None
        for provider in self.providers:
            try:
                return provider.translate(text, from_lang, to_lang)
            except Exception as e:  # noqa: BLE001
                last_error = e
        raise last_error or RuntimeError("All providers failed")

    def translate_batch(self, texts: List[str], from_lang: str, to_lang: str) -> List[str]:
        last_error: Optional[Exception] = None
        for provider in self.providers:
            try:
                return provider.translate_batch(texts, from_lang, to_lang)
            except Exception as e:  # noqa: BLE001
                last_error = e
        raise last_error or RuntimeError("All batch providers failed")


def create_provider(config: ProviderConfig) -> TranslationProvider:
    """根据配置创建翻译源实例。"""
    t = config.type
    if t in ("deepseek", "openai-compat"):
        return OpenAICompatProvider(config)
    if t in ("local-llm", "ollama", "llamacpp"):
        return LocalLLMProvider(config)
    if t == "google-free":
        return GoogleFreeProvider()
    if t == "bing-free":
        return BingFreeProvider()
    if t == "deepl":
        return DeepLProvider(config)
    if t == "baidu":
        return BaiduProvider(config)
    raise ValueError(f"Unknown provider type: {t}")
