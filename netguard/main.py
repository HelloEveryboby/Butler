from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from config import settings
from database import init_db
from routers import auth, threat_intel, traffic, scan, protection, stats

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    description="""
# NetGuard API

A network security API platform for security researchers.

## Features
- **Threat Intelligence**: IP/domain/URL reputation lookup
- **Traffic Analysis**: Packet analysis and anomaly detection
- **Scanner**: Port scanning and service detection
- **Protection**: DDoS detection, SQL injection/XSS filtering, rate limiting

## Tiers
- **Free**: Basic access with rate limits
- **Pro**: Full access with higher limits
    """,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}


app.include_router(auth.router)
app.include_router(threat_intel.router)
app.include_router(traffic.router)
app.include_router(scan.router)
app.include_router(protection.router)
app.include_router(stats.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
