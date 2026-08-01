"""
Butler 强类型配置模型 (TypedConfig)。

基于 Pydantic，统一所有配置读取入口。
密钥类配置强制走 SecretVault，不再允许占位符默认值。
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field


class SecurityError(Exception):
    """配置安全违规异常。"""


class QuotaConfig(BaseModel):
    consumed: float = 0.0


# 预设的 AI 提供商默认配置
PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
        "display_name": "DeepSeek",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-3.5-turbo",
        "key_env": "OPENAI_API_KEY",
        "display_name": "OpenAI",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4-flash",
        "key_env": "ZHIPU_API_KEY",
        "display_name": "智谱 AI",
    },
    "custom": {
        "base_url": "",
        "model_name": "",
        "key_env": "CUSTOM_API_KEY",
        "display_name": "自定义 API",
    },
}


class ApiConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # AI 提供商配置
    provider: str = Field("deepseek", alias="AI_PROVIDER")
    base_url: str | None = Field(None, alias="API_BASE_URL")
    model_name: str | None = Field(None, alias="MODEL_NAME")

    # API 密钥
    deepseek_key: str | None = Field(None, alias="DEEPSEEK_API_KEY")
    openai_key: str | None = Field(None, alias="OPENAI_API_KEY")
    zhipu_key: str | None = Field(None, alias="ZHIPU_API_KEY")
    custom_key: str | None = Field(None, alias="CUSTOM_API_KEY")

    # 百度语音
    baidu_app_id: str | None = Field(None, alias="BAIDU_APP_ID")
    baidu_api_key: str | None = Field(None, alias="BAIDU_API_KEY")
    baidu_secret_key: str | None = Field(None, alias="BAIDU_SECRET_KEY")
    picovoice_access_key: str | None = Field(None, alias="PICOVOICE_ACCESS_KEY")
    quota: QuotaConfig = Field(default_factory=QuotaConfig)

    def get_resolved_base_url(self) -> str:
        """获取解析后的 API 基础地址（用户配置优先，否则用提供商默认）。"""
        if self.base_url:
            return self.base_url.rstrip("/")
        defaults = PROVIDER_DEFAULTS.get(self.provider, PROVIDER_DEFAULTS["deepseek"])
        return defaults["base_url"]

    def get_resolved_model_name(self) -> str:
        """获取解析后的模型名称（用户配置优先，否则用提供商默认）。"""
        if self.model_name:
            return self.model_name
        defaults = PROVIDER_DEFAULTS.get(self.provider, PROVIDER_DEFAULTS["deepseek"])
        return defaults["model_name"]

    def get_active_api_key(self) -> str | None:
        """根据当前 provider 获取对应的 API 密钥。"""
        provider = self.provider
        if provider == "deepseek":
            return self.deepseek_key
        elif provider == "openai":
            return self.openai_key
        elif provider == "zhipu":
            return self.zhipu_key
        elif provider == "custom":
            return self.custom_key
        # 回退到 deepseek
        return self.deepseek_key

    @property
    def ai_available(self) -> bool:
        """检查是否有至少一个可用的 AI 密钥。"""
        key = self.get_active_api_key()
        return bool(key and "YOUR_" not in str(key))


class VoiceConfig(BaseModel):
    mode: str = "online"
    local_stt_model: str = "base"


class USBScreenConfig(BaseModel):
    width: int = 40
    height: int = 8


class DisplayConfig(BaseModel):
    default_mode: str = "host"
    theme: str = "google"
    usb_screen: USBScreenConfig = Field(default_factory=USBScreenConfig)


class PerformanceConfig(BaseModel):
    mode: str = "NORMAL"


class InterpreterConfig(BaseModel):
    safety_mode: bool = True
    max_iterations: int = 10


class RunnerServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    # 不再提供占位符默认值，token 必须显式配置
    token: str | None = None

    def get_token(self, vault=None) -> str:
        """
        从 SecretVault 获取 token，回退到环境变量。

        禁止使用占位符默认值。未配置时抛出 SecurityError。
        """
        token = None
        if vault and getattr(vault, "_master_key", None):
            token = vault.get_secret("runner_token")

        if not token:
            token = os.getenv("BUTLER_RUNNER_TOKEN")

        if not token or token in ("BUTLER_TOKEN_PLACEHOLDER", "YOUR_RUNNER_SERVER_TOKEN_HERE"):
            raise SecurityError(
                "Runner token 未配置。请通过 'butler vault set runner_token <token>' "
                "设置，或设置环境变量 BUTLER_RUNNER_TOKEN。"
            )
        return token


class ApiGatewayConfig(BaseModel):
    """REST API 安全网关配置。"""
    host: str = "127.0.0.1"
    port: int = 5001
    use_ssl: bool = True

    def get_token(self, vault=None) -> str:
        """从 SecretVault 或环境变量获取 API Gateway token。"""
        token = None
        if vault and getattr(vault, "_master_key", None):
            token = vault.get_secret("rest_api_bearer_token")

        if not token:
            token = os.getenv("BUTLER_API_TOKEN")

        if not token or token == "BUTLER_TOKEN_PLACEHOLDER":
            raise SecurityError(
                "API Gateway token 未配置。请通过 'butler vault set rest_api_bearer_token <token>' "
                "设置，或设置环境变量 BUTLER_API_TOKEN。"
            )
        return token


class ButlerConfig(BaseModel):
    api: ApiConfig = Field(default_factory=ApiConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    interpreter: InterpreterConfig = Field(default_factory=InterpreterConfig)
    runner_server: RunnerServerConfig = Field(default_factory=RunnerServerConfig)
    api_gateway: ApiGatewayConfig = Field(default_factory=ApiGatewayConfig)

    model_config = ConfigDict(populate_by_name=True)


def load_config_from_env() -> ButlerConfig:
    """
    从环境变量加载配置。

    优先级: 环境变量 > .env 文件 > dataclass 默认值。
    密钥类配置不在此加载，由各 Config 的 get_token() 方法
    在使用时从 SecretVault 获取。
    """
    config = ButlerConfig()

    # AI 提供商配置
    if provider := os.getenv("AI_PROVIDER"):
        config.api.provider = provider
    if base_url := os.getenv("API_BASE_URL"):
        config.api.base_url = base_url
    if model_name := os.getenv("MODEL_NAME"):
        config.api.model_name = model_name

    # API 密钥
    config.api.deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    config.api.openai_key = os.getenv("OPENAI_API_KEY")
    config.api.zhipu_key = os.getenv("ZHIPU_API_KEY")
    config.api.custom_key = os.getenv("CUSTOM_API_KEY")

    # Runner
    if host := os.getenv("BUTLER_RUNNER_HOST"):
        config.runner_server.host = host
    if port := os.getenv("BUTLER_RUNNER_PORT"):
        config.runner_server.port = int(port)

    # API Gateway
    if host := os.getenv("BUTLER_API_HOST"):
        config.api_gateway.host = host
    if port := os.getenv("BUTLER_API_PORT"):
        config.api_gateway.port = int(port)

    # Voice
    if mode := os.getenv("BUTLER_VOICE_MODE"):
        config.voice.mode = mode

    return config
