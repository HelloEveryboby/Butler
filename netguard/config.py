import os


class Settings:
    PROJECT_NAME = "NetGuard API"
    VERSION = "0.1.0"
    DATABASE_URL = "sqlite+aiosqlite:///./netguard.db"
    SECRET_KEY = os.getenv("SECRET_KEY", "netguard-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

    FREE_TIER_RATE = 10
    PRO_TIER_RATE = 100

    FREE_SCAN_LIMIT = 5
    PRO_SCAN_LIMIT = 200

    FREE_THREAT_LIMIT = 10
    PRO_THREAT_LIMIT = 1000

    FREE_ANALYSIS_LIMIT = 3
    PRO_ANALYSIS_LIMIT = 50

    FREE_PROTECTION_LIMIT = 5
    PRO_PROTECTION_LIMIT = 50


settings = Settings()
