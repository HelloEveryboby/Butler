"""请求日志中间件"""

import time
from datetime import datetime, timezone

from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database import AsyncSessionLocal


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """记录所有 /api/ 请求到 api_call_logs 表"""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)

        if request.url.path.startswith("/api/"):
            duration_ms = int((time.time() - start) * 1000)
            user_id = getattr(request.state, "user_id", 0)
            try:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text(
                            "INSERT INTO api_call_logs "
                            "(user_id, endpoint, method, status_code, cost_usd, created_at) "
                            "VALUES (:uid, :ep, :method, :status, 0.0, :now)"
                        ),
                        {
                            "uid": user_id,
                            "ep": request.url.path,
                            "method": request.method,
                            "status": response.status_code,
                            "now": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    await db.commit()
            except Exception:
                pass  # 日志写入失败不影响正常请求

        return response
