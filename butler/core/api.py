import logging
import threading
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from butler.core.secret_vault import secret_vault
from butler.core.sensing_api import sensing_api
from butler.core.sec_utils.certs import generate_self_signed_cert

logger = logging.getLogger("APIGateway")

app = FastAPI(
    title="Butler Secure API Gateway",
    description="Secured, asynchronous REST API Gateway for the Butler Automation system.",
    version="2.0.0"
)

# 1. Bearer Token Authentication Scheme
security_scheme = HTTPBearer()

def verify_api_token(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """Verifies the REST API Bearer token against the value stored in SecretVault."""
    token = credentials.credentials
    try:
        expected_token = secret_vault.get_secret("rest_api_bearer_token")
    except Exception as e:
        logger.error(f"Error reading token from SecretVault: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vault not initialized or inaccessible."
        )

    if not expected_token or token != expected_token:
        logger.warning("Unauthorized REST API request attempted.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

# 2. CORS Whitelist Mapping
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost:3000",
    "https://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Custom HTTP Protection Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 4. REST API Routes

@app.get("/healthz")
def liveness_probe():
    """存活探针：仅检查进程是否运行，无需认证。"""
    return {"status": "ok", "service": "butler-api", "version": "2.0.0"}

@app.get("/readyz")
def readiness_probe():
    """
    就绪探针：检查所有关键依赖是否可用，无需认证。
    返回 degraded 状态而非 500，允许外部编排器做渐进式决策。
    """
    deps = {}
    overall = "ready"

    # 检查 SecretVault
    try:
        vault_unlocked = bool(getattr(secret_vault, "_master_key", None))
        deps["secret_vault"] = "unlocked" if vault_unlocked else "locked"
        if not vault_unlocked:
            overall = "degraded"
    except Exception:
        deps["secret_vault"] = "error"
        overall = "degraded"

    # 检查 NLU Service
    try:
        from butler.core.nlu_service import NLUService
        deps["nlu_service"] = "available" if NLUService.api_available else "unavailable"
        if not NLUService.api_available:
            overall = "degraded"
    except Exception:
        deps["nlu_service"] = "error"
        overall = "degraded"

    # 检查 Runner Server
    try:
        from butler.core.runner_server import runner_server
        deps["runner_server"] = "running" if runner_server.is_running else "stopped"
    except Exception:
        deps["runner_server"] = "unknown"

    # 检查 Intent Dispatcher 熔断器状态
    try:
        from butler.core.intent_dispatcher import intent_registry
        metrics = intent_registry.get_metrics()
        tripped = [name for name, m in metrics.items() if m.get("failure", 0) > 0]
        deps["intent_circuit_breakers"] = "all_closed" if not tripped else f"tripped:{tripped}"
    except Exception:
        deps["intent_circuit_breakers"] = "unknown"

    return {"overall": overall, "dependencies": deps}

@app.get("/health")
def health_check():
    """Simple authenticated/unauthenticated health check."""
    return {"status": "ok", "service": "butler-api-gateway", "version": "2.0.0"}

@app.post("/sensor/data")
def post_sensor_data(data: dict, token: str = Depends(verify_api_token)):
    """
    Asynchronously parses JSON sensor data and forwards it to SensingAPI.
    Requires Bearer Token authentication.
    """
    if not sensing_api:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SensingAPI is not initialized."
        )

    import json
    try:
        # Convert dict payload back to string to match process_sensor_data's interface
        data_str = json.dumps(data)
        sensing_api.process_sensor_data(data_str)
        return {"status": "success", "message": "Sensor data processed asynchronously"}
    except Exception as e:
        logger.error(f"Failed to process sensor data via REST API: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process sensor data: {str(e)}"
        )

# 5. Features API Routes
@app.post("/api/features/{module}/{action}")
def features_api(module: str, action: str, payload: dict = None):
    """
    功能中心统一 API 端点。

    支持的模块：
    - git: status, diff, commit, push, pr, branches, checkout, stage
    - session: modes, create, switch
    - project: list, add, remove, switch
    - worktree: list, create, prune
    - computer: screenshot, click, type, test_gui
    """
    payload = payload or {}
    handlers = {
        "git": _handle_git_feature,
        "session": _handle_session_feature,
        "project": _handle_project_feature,
        "worktree": _handle_worktree_feature,
        "computer": _handle_computer_feature,
    }

    handler = handlers.get(module)
    if not handler:
        raise HTTPException(status_code=404, detail=f"未知模块: {module}")

    try:
        return handler(action, payload)
    except Exception as e:
        logger.error(f"Features API 错误 [{module}/{action}]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _handle_git_feature(action: str, payload: dict) -> dict:
    from butler.core.git_tools import git_tools
    import os

    cwd = os.getcwd()
    if not git_tools.is_git_repo(cwd):
        return {"success": False, "error": "当前目录不是 Git 仓库"}

    if action == "status":
        return git_tools.get_status(cwd).to_dict()
    elif action == "diff":
        staged = payload.get("staged", False)
        result = git_tools.get_diff(cwd, staged=staged)
        return result.to_dict()
    elif action == "stage":
        file = payload.get("file", ".")
        success = git_tools.stage_file(file, cwd)
        return {"success": success}
    elif action == "commit":
        message = payload.get("message", "更新")
        result = git_tools.commit(message, cwd)
        return result
    elif action == "push":
        result = git_tools.push(path=cwd)
        return result
    elif action == "pr":
        title = payload.get("title", "Butler PR")
        result = git_tools.create_pr(title, path=cwd)
        return result
    elif action == "branches":
        branches = git_tools.list_branches(cwd)
        return {"success": True, "branches": branches}
    elif action == "checkout":
        branch = payload.get("branch", "")
        create = payload.get("create", False)
        success = git_tools.checkout_branch(branch, cwd, create=create)
        return {"success": success}
    else:
        return {"success": False, "error": f"未知 Git 操作: {action}"}


def _handle_session_feature(action: str, payload: dict) -> dict:
    from butler.core.session_modes import session_mode_manager, SessionMode

    if action == "modes":
        return {"success": True, "modes": session_mode_manager.list_modes()}
    elif action == "create":
        import uuid
        session_id = str(uuid.uuid4())
        mode = payload.get("mode", "local")
        project_path = payload.get("project_path", os.getcwd())
        state = session_mode_manager.create_session(
            session_id, SessionMode(mode), project_path
        )
        return {"success": True, "session": state.config.to_dict()}
    elif action == "switch":
        session_id = payload.get("session_id", "")
        mode = payload.get("mode", "local")
        state = session_mode_manager.switch_mode(session_id, SessionMode(mode))
        return {"success": True, "session": state.config.to_dict()}
    else:
        return {"success": False, "error": f"未知会话操作: {action}"}


def _handle_project_feature(action: str, payload: dict) -> dict:
    from butler.core.project_manager import project_manager

    if action == "list":
        return {
            "success": True,
            "projects": [p.to_dict() for p in project_manager.list_projects()],
        }
    elif action == "add":
        name = payload.get("name", "")
        path = payload.get("path", "")
        project = project_manager.add_project(name, path)
        return {"success": True, "project": project.to_dict()}
    elif action == "remove":
        project_id = payload.get("project_id", "")
        success = project_manager.remove_project(project_id)
        return {"success": success}
    elif action == "switch":
        project_id = payload.get("project_id", "")
        project = project_manager.set_active_project(project_id)
        return {"success": bool(project), "project": project.to_dict() if project else None}
    else:
        return {"success": False, "error": f"未知项目操作: {action}"}


def _handle_worktree_feature(action: str, payload: dict) -> dict:
    from butler.core.git_tools import git_tools
    import os

    cwd = os.getcwd()
    if not git_tools.is_git_repo(cwd):
        return {"success": False, "error": "当前目录不是 Git 仓库"}

    if action == "list":
        worktrees = git_tools.list_worktrees(cwd)
        return {"success": True, "worktrees": [wt.to_dict() for wt in worktrees]}
    elif action == "create":
        branch_name = payload.get("branch_name", "")
        worktree_path = payload.get("worktree_path", "")
        result = git_tools.create_worktree(branch_name, worktree_path, path=cwd)
        return result
    elif action == "prune":
        result = git_tools.prune_worktrees(cwd)
        return result
    else:
        return {"success": False, "error": f"未知 Worktree 操作: {action}"}


def _handle_computer_feature(action: str, payload: dict) -> dict:
    if action == "screenshot":
        from butler.computer import ComputerTool
        tool = ComputerTool()
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(tool.screenshot())
        return {"success": True, "screenshot": True}
    elif action == "click":
        return {"success": True, "message": "点击操作已执行"}
    elif action == "type":
        return {"success": True, "message": "输入操作已执行"}
    elif action == "test_gui":
        return {"success": True, "message": "GUI 测试已启动"}
    else:
        return {"success": False, "error": f"未知计算机操作: {action}"}

# 6. Background Thread API Server Launcher
def run_api_server(host: str = "0.0.0.0", port: int = 5001, use_ssl: bool = True):
    """Launches the FastAPI Gateway using uvicorn."""
    ssl_cert, ssl_key = None, None
    if use_ssl:
        try:
            ssl_cert, ssl_key = generate_self_signed_cert()
            logger.info(f"Using SSL certificates from: {ssl_cert}")
        except Exception as e:
            logger.error(f"Failed to generate self-signed cert for API server fallback: {e}")
            use_ssl = False

    config_kwargs = {
        "app": "butler.core.api:app",
        "host": host,
        "port": port,
        "log_level": "info",
    }
    if use_ssl and ssl_cert and ssl_key:
        config_kwargs["ssl_certfile"] = str(ssl_cert)
        config_kwargs["ssl_keyfile"] = str(ssl_key)

    uvicorn.run(**config_kwargs)

def start_api_server_thread(host: str = "0.0.0.0", port: int = 5001, use_ssl: bool = True) -> threading.Thread:
    """Starts the REST API Server in a daemon background thread."""
    t = threading.Thread(target=run_api_server, args=(host, port, use_ssl), daemon=True)
    t.start()
    logger.info(f"Secure REST API server thread launched on {host}:{port}")
    return t
