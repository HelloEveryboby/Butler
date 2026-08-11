"""自定义异常 + 全局异常处理器"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NetGuardError(Exception):
    """NetGuard 业务异常基类"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ScanTargetError(NetGuardError):
    """扫描目标校验失败"""

    def __init__(self, message: str = "Invalid scan target"):
        super().__init__(message, status_code=400)


class TierLimitError(NetGuardError):
    """超出当前 tier 限制"""

    def __init__(self, message: str = "Tier limit exceeded"):
        super().__init__(message, status_code=429)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(NetGuardError)
    async def netguard_error_handler(request: Request, exc: NetGuardError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        # 生产环境不暴露内部错误细节
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
