"""统一 LLM 提供商抽象层（Local-First Provider Resolver）。

背景
----
Butler 的 ``.env`` 早已声明了多提供商配置（``AI_PROVIDER`` / ``API_BASE_URL`` /
``MODEL_NAME`` 以及各家的 ``*_API_KEY``），但 ``agent_runtime/jarvis_adapter.py``
里的 LLM 回调仍硬编码 DeepSeek（endpoint、model、key 三处写死）。

本模块把散落在环境变量里的提供商信息收敛为**一份统一的 OpenAI 兼容调用参数**，
让 Butler 可以：

* 切换 DeepSeek / OpenAI / 智谱 / Anthropic / Gemini / 通义 / 文心 等云端提供商；
* 指向本地 OpenAI 兼容服务（Ollama / vLLM / LM Studio / OneAPI 中转），**真正离线运行**；
* 保持向后兼容：未配置时回退到原来的 DeepSeek 默认行为。

用法
----
    from butler.core.llm_providers import resolve_llm_config, chat_completions

    cfg = resolve_llm_config(config_get=jarvis.config.get)
    if not cfg.is_usable:
        raise RuntimeError("no usable LLM provider configured")

    content, tool_calls, stop_reason, total_tokens = chat_completions(
        cfg, messages, tools=tools, max_tokens=4096, temperature=0.7,
    )
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# provider -> (default_endpoint, default_model, key_env_var)
# key_env_var 为 None 表示本地/无需鉴权（如 Ollama）。
_PROVIDER_TABLE: dict[str, tuple[str, str, Optional[str]]] = {
    "deepseek": (
        "https://api.deepseek.com/v1",
        "deepseek-chat",
        "DEEPSEEK_API_KEY",
    ),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
    "zhipu": (
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4-flash",
        "ZHIPU_API_KEY",
    ),
    "anthropic": (
        "https://api.anthropic.com/v1",
        "claude-3-5-sonnet-20241022",
        "ANTHROPIC_API_KEY",
    ),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-1.5-flash",
        "GEMINI_API_KEY",
    ),
    "dashscope": (
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-turbo",
        "DASHSCOPE_API_KEY",
    ),
    "qianfan": (
        "https://qianfan.baidubce.com/v2",
        "ernie-4.0-8k",
        "QIANFAN_API_KEY",
    ),
    # 本地优先：无鉴权，指向本机 Ollama 的 OpenAI 兼容端点。
    "ollama": ("http://localhost:11434/v1", "llama3.1", None),
}

_PLACEHOLDER_MARKERS = ("YOUR_", "<", "xxx")


@dataclass
class LLMConfig:
    """一次解析得到的、可直接用于 OpenAI 兼容调用的参数。"""

    provider: str
    endpoint: str
    model: str
    api_key: str = ""

    @property
    def chat_completions_url(self) -> str:
        return f"{self.endpoint.rstrip('/')}/chat/completions"

    @property
    def is_usable(self) -> bool:
        """本地提供商（无 key）永远可用；云端提供商需要非占位 key。"""
        if self.api_key == "":
            # 仅当该提供商本身不需要鉴权（本地服务）时视为可用。
            return _PROVIDER_TABLE.get(self.provider, (None, None, None))[2] is None
        return not any(marker in self.api_key for marker in _PLACEHOLDER_MARKERS)


def resolve_llm_config(
    config_get: Optional[Callable[[str, Any], Any]] = None,
) -> LLMConfig:
    """解析当前生效的 LLM 提供商配置。

    优先级：环境变量 > 旧版 YAML 配置（``api.deepseek.*``）> 内置默认值。
    环境变量在 ``config/config.py`` 里已由 ``load_dotenv()`` 注入，故此处直接读
    ``os.environ`` 即可，无需重复加载 ``.env``。

    参数
    ----
    config_get:
        可选回调 ``config_get("api.deepseek.key", "")``，用于兼容旧版基于 YAML
        的 DeepSeek 配置。传入 ``None`` 时只读取环境变量。
    """
    provider = (os.getenv("AI_PROVIDER") or "deepseek").strip().lower()

    endpoint, default_model, key_env = _PROVIDER_TABLE.get(
        provider, _PROVIDER_TABLE["deepseek"]
    )

    # API_BASE_URL 可覆盖任意提供商的默认地址，也是 custom/本地服务的入口。
    endpoint = (os.getenv("API_BASE_URL") or "").strip() or endpoint
    model = (os.getenv("MODEL_NAME") or "").strip() or default_model

    if provider == "custom":
        api_key = (os.getenv("CUSTOM_API_KEY") or "").strip()
    elif key_env:
        api_key = (os.getenv(key_env) or "").strip()
    else:
        api_key = ""

    # 向后兼容：旧版代码把 key 存在 YAML 的 api.deepseek.key / endpoint 下。
    if config_get is not None:
        try:
            if not api_key:
                api_key = str(config_get("api.deepseek.key", "") or "").strip()
            if not (os.getenv("API_BASE_URL") or "").strip():
                legacy_endpoint = str(
                    config_get("api.deepseek.endpoint", "") or ""
                ).strip()
                if legacy_endpoint:
                    endpoint = legacy_endpoint
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("legacy config fallback skipped: %s", exc)

    cfg = LLMConfig(provider=provider, endpoint=endpoint, model=model, api_key=api_key)
    logger.debug(
        "resolved LLM provider=%s model=%s endpoint=%s key=%s",
        provider,
        model,
        endpoint,
        "set" if cfg.is_usable else "missing",
    )
    return cfg


def chat_completions(
    cfg: LLMConfig,
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout: int = 60,
    extra_payload: Optional[dict] = None,
) -> tuple[str, list[dict], str, int]:
    """调用 OpenAI 兼容的 ``/chat/completions`` 端点。

    返回 ``(content, tool_calls, stop_reason, total_tokens)``。
    异常会向上抛出，由调用方决定降级策略。
    """
    import requests  # 延迟导入，避免未安装时影响模块加载

    payload: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "tools": tools if tools else None,
        "tool_choice": "auto" if tools else None,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if extra_payload:
        payload.update(extra_payload)
    # 去掉 None 值，保持请求体干净。
    payload = {k: v for k, v in payload.items() if v is not None}

    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    resp = requests.post(
        cfg.chat_completions_url, json=payload, headers=headers, timeout=timeout
    )
    resp.raise_for_status()
    data = resp.json()

    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    stop_reason = choice.get("finish_reason", "end_turn")
    total_tokens = (data.get("usage") or {}).get("total_tokens", 0)

    return (
        message.get("content") or "",
        message.get("tool_calls") or [],
        stop_reason,
        int(total_tokens or 0),
    )
