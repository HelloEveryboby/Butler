"""main.py — FastAPI 应用工厂（完整版）"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.alerts import alert_manager
from app.config import get_settings
from app.database import init_db
from app.deps import get_store, get_task_queue
from app.exceptions import register_exception_handlers
from app.middleware.request_logger import RequestLoggerMiddleware

# 路由
from app.routers.v1 import (
    auth,
    blacklist,
    capture,
    dns,
    protection,
    reports,
    scan,
    schedules,
    stats,
    tasks,
    threat_intel,
    traffic,
    ws,
)

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


async def _register_task_handlers():
    """注册后台任务处理器"""
    queue = await get_task_queue()

    async def handle_capture(params: dict) -> dict:
        from app.services.capture_service import CaptureService
        svc = CaptureService()
        return await svc.capture(
            interface=params.get("interface", "eth0"),
            duration=params.get("duration", 10),
            filter_expr=params.get("filter_expr", ""),
            packet_count=params.get("packet_count", 100),
        )

    queue.register_handler("capture", handle_capture)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库 + 任务队列，关闭时清理"""
    await init_db()
    await _register_task_handlers()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    description="""
# NetGuard API v1.1

Network security API platform for security researchers.

## Features
- **Threat Intelligence**: IP/domain/URL reputation lookup + VirusTotal/AbuseIPDB
- **Traffic Analysis**: Packet analysis and anomaly detection
- **Scanner**: Port scanning, service detection, SSL checking
- **Protection**: DDoS detection, SQL injection/XSS filtering, rate limiting
- **DNS**: DNS lookup, reverse DNS, subdomain enumeration
- **Blacklist**: Auto-fetch from Spamhaus, Feodo, CINS, Blocklist.de
- **Capture**: Live packet capture (requires root)
- **Reports**: CSV/JSON export of all data
- **Schedules**: Cron-based periodic scanning
- **WebSocket**: Real-time alert push at /ws/alerts

## Authentication
- **JWT Bearer Token**: `Authorization: Bearer <token>`
- **API Key**: `X-API-Key: ***

## Tiers
- **Free**: Basic access with rate limits
- **Pro**: Full access, capture, rule modification
    """,
)

# ── 限流 ──
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ── 请求日志 ──
app.add_middleware(RequestLoggerMiddleware)

# ── 全局异常处理 ──
register_exception_handlers(app)

# ── 路由 ──
app.include_router(auth.router)
app.include_router(threat_intel.router)
app.include_router(traffic.router)
app.include_router(scan.router)
app.include_router(protection.router)
app.include_router(stats.router)
app.include_router(dns.router)
app.include_router(tasks.router)
app.include_router(capture.router)
app.include_router(blacklist.router)
app.include_router(schedules.router)
app.include_router(reports.router)
app.include_router(ws.router)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "endpoints": {
            "auth": "/api/v1/auth",
            "threat_intel": "/api/v1/threat-intel",
            "traffic": "/api/v1/traffic",
            "scan": "/api/v1/scan",
            "protection": "/api/v1/protection",
            "stats": "/api/v1/stats",
            "dns": "/api/v1/dns",
            "tasks": "/api/v1/tasks",
            "capture": "/api/v1/capture",
            "blacklist": "/api/v1/blacklist",
            "schedules": "/api/v1/schedules",
            "reports": "/api/v1/reports",
            "websocket": "/ws/alerts",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}
