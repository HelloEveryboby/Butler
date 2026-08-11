"""应用配置 — 所有参数通过环境变量 / .env 文件驱动"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── 基础 ──
    PROJECT_NAME: str = "NetGuard API"
    VERSION: str = "1.1.0"
    DEBUG: bool = False

    # ── 安全（必填，无默认值） ──
    SECRET_KEY: str  # 必填，无默认值
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # ── 数据库 ──
    DATABASE_URL: str = "sqlite+aiosqlite:///./netguard.db"

    # ── Redis（可选，用于状态外置） ──
    REDIS_URL: str | None = None  # e.g. redis://localhost:6379/0

    # ── CORS ──
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── 外部 API Keys（可选） ──
    VIRUSTOTAL_API_KEY: str | None = None
    ABUSEIPDB_API_KEY: str | None = None

    # ── 限流（请求/分钟） ──
    FREE_TIER_RATE: int = 10
    PRO_TIER_RATE: int = 100

    # ── 功能阈值 ──
    FREE_SCAN_LIMIT: int = 5
    PRO_SCAN_LIMIT: int = 200

    FREE_THREAT_LIMIT: int = 10
    PRO_THREAT_LIMIT: int = 1000

    FREE_ANALYSIS_LIMIT: int = 3
    PRO_ANALYSIS_LIMIT: int = 50

    FREE_PROTECTION_LIMIT: int = 5
    PRO_PROTECTION_LIMIT: int = 50

    # ── 防护规则默认值 ──
    DDOS_THRESHOLD: int = 100
    DDOS_WINDOW_SECONDS: int = 10
    PORT_SCAN_THRESHOLD: int = 20
    BRUTE_FORCE_THRESHOLD: int = 5
    BRUTE_FORCE_WINDOW_SECONDS: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
