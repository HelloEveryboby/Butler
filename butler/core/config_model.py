from pydantic import BaseModel, Field
from typing import Optional, Dict

class QuotaConfig(BaseModel):
    consumed: float = 0.0

class ApiConfig(BaseModel):
    deepseek_key: Optional[str] = Field(None, alias="DEEPSEEK_API_KEY")
    baidu_app_id: Optional[str] = Field(None, alias="BAIDU_APP_ID")
    baidu_api_key: Optional[str] = Field(None, alias="BAIDU_API_KEY")
    baidu_secret_key: Optional[str] = Field(None, alias="BAIDU_SECRET_KEY")
    picovoice_access_key: Optional[str] = Field(None, alias="PICOVOICE_ACCESS_KEY")
    quota: QuotaConfig = Field(default_factory=QuotaConfig)

class VoiceConfig(BaseModel):
    mode: str = "online" # online, local, offline
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
    token: str = "YOUR_RUNNER_SERVER_TOKEN_HERE"

class ButlerConfig(BaseModel):
    api: ApiConfig = Field(default_factory=ApiConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    interpreter: InterpreterConfig = Field(default_factory=InterpreterConfig)
    runner_server: RunnerServerConfig = Field(default_factory=RunnerServerConfig)

    class Config:
        populate_by_name = True
