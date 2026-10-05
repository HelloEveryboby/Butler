"""翻译系统配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# 翻译源类型
PROVIDER_TYPES = (
    "deepseek",
    "openai-compat",
    "local-llm",
    "google-free",
    "bing-free",
    "deepl",
    "baidu",
)


@dataclass
class ProviderConfig:
    """单个翻译源的配置。"""

    id: str
    type: str  # PROVIDER_TYPES 之一
    name: str
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    prompt: Optional[str] = None
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "endpoint": self.endpoint,
            "api_key": self.api_key,
            "model": self.model,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProviderConfig":
        return cls(
            id=data["id"],
            type=data["type"],
            name=data.get("name", data["type"]),
            endpoint=data.get("endpoint"),
            api_key=data.get("api_key"),
            model=data.get("model"),
            prompt=data.get("prompt"),
            enabled=data.get("enabled", True),
        )


def _default_providers() -> List[ProviderConfig]:
    """默认翻译源列表：DeepSeek（主）+ Google / Bing 免费降级。"""
    providers: List[ProviderConfig] = [
        ProviderConfig(
            id="deepseek-default",
            type="deepseek",
            name="DeepSeek（默认）",
            endpoint="https://api.deepseek.com/v1",
            model="deepseek-chat",
        ),
        ProviderConfig(
            id="google-free",
            type="google-free",
            name="Google 免费翻译",
        ),
        ProviderConfig(
            id="bing-free",
            type="bing-free",
            name="微软免费翻译",
        ),
        # 本地 LLM（Ollama / llama.cpp），离线模式下唯一可用源；默认不在降级链中
        ProviderConfig(
            id="local-llm",
            type="local-llm",
            name="本地 LLM（Ollama / llama.cpp）",
            endpoint="http://127.0.0.1:11430/v1",
            model="qwen2.5:7b",
            enabled=True,
        ),
    ]
    return providers


@dataclass
class TranslateSystemConfig:
    """翻译系统的全局配置。"""

    target_lang: str = "zh-CN"
    fallback_chain: List[str] = field(
        default_factory=lambda: ["deepseek-default", "google-free", "bing-free"]
    )
    providers: List[ProviderConfig] = field(default_factory=_default_providers)

    # 缓存
    cache_enabled: bool = True
    cache_max_size: int = 2000

    # 数据目录（缓存 / 术语表 / 历史）
    data_dir: str = field(default_factory=lambda: str(Path.home() / ".butler" / "translate"))

    # 降级链最大重试
    fallback_max_retries: int = 2

    # 离线模式：开启后只允许本地源（local-llm），禁用所有远程 provider
    offline_mode: bool = False

    @property
    def active_provider_id(self) -> str:
        return self.fallback_chain[0] if self.fallback_chain else ""

    def get_provider(self, provider_id: str) -> Optional[ProviderConfig]:
        for p in self.providers:
            if p.id == provider_id:
                return p
        return None

    def to_dict(self) -> dict:
        return {
            "target_lang": self.target_lang,
            "fallback_chain": self.fallback_chain,
            "providers": [p.to_dict() for p in self.providers],
            "cache_enabled": self.cache_enabled,
            "cache_max_size": self.cache_max_size,
            "data_dir": self.data_dir,
            "fallback_max_retries": self.fallback_max_retries,
            "offline_mode": self.offline_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TranslateSystemConfig":
        providers = [ProviderConfig.from_dict(p) for p in data.get("providers", [])]
        return cls(
            target_lang=data.get("target_lang", "zh-CN"),
            fallback_chain=data.get("fallback_chain", ["deepseek-default", "google-free", "bing-free"]),
            providers=providers or _default_providers(),
            cache_enabled=data.get("cache_enabled", True),
            cache_max_size=data.get("cache_max_size", 2000),
            data_dir=data.get("data_dir", str(Path.home() / ".butler" / "translate")),
            fallback_max_retries=data.get("fallback_max_retries", 2),
            offline_mode=data.get("offline_mode", False),
        )
