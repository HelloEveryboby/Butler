"""翻译源适配层。

与 frontend/translate 的 Provider 设计保持一致，Python 端使用 requests 实现。
支持：DeepSeek / OpenAI 兼容 / Google 免费 / 微软免费 / DeepL / 百度。
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import requests

from .config import ProviderConfig


class TranslationProvider(ABC):
    """翻译源统一接口。"""

    id: str
    name: str

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
        )

    def _system_prompt(self, from_lang: str, to_lang: str) -> str:
        from .languages import lang_name
        return self.prompt.replace("{from}", lang_name(from_lang)).replace("{to}", lang_name(to_lang))

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
        user_msg = f"请逐条翻译以下文本，保持编号格式不变，每条翻译后空一行：\n\n{numbered}"
        content = self._post(
            [
                {"role": "system", "content": self._system_prompt(from_lang, to_lang)},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=8192,
        )
        results: List[str] = [""] * len(texts)
        current = -1
        for line in content.split("\n"):
            import re
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


# ---------- 降级链 ----------

class FallbackProvider(TranslationProvider):
    """按优先级依次尝试多个翻译源。"""

    def __init__(self, providers: List[TranslationProvider]):
        self.providers = providers
        self.id = providers[0].id if providers else "fallback"
        self.name = f"{providers[0].name}（含降级）" if providers else "Fallback"

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
    if t == "google-free":
        return GoogleFreeProvider()
    if t == "bing-free":
        return BingFreeProvider()
    if t == "deepl":
        return DeepLProvider(config)
    if t == "baidu":
        return BaiduProvider(config)
    raise ValueError(f"Unknown provider type: {t}")
