# -*- coding: utf-8 -*-
import os
import sys
import threading
import logging
from typing import Dict, Any, Optional

from butler.core.lifecycle import SystemLifecycle, LifecycleState
from butler.core.scheduler import BackgroundScheduler
from butler.core.db_migrations import run_all_migrations
from butler.package_runtime.loader import PackageLoader
from butler.memory.manager import MemoryManager
from butler.agent.agent import Agent
from butler.workflow.engine import WorkflowEngine
from butler.security.audit import SecurityAuditor

logger = logging.getLogger(__name__)

class ButlerRuntime:
    """
    Butler v2.0 Alpha 的核心运行时协调器（Runtime Coordinator）。
    负责统一初始化数据库表迁移、技能包加载、长期/短期记忆加载、后台调度、并开启 REST API 网关。
    """
    def __init__(self, db_path: str = None, host: str = "0.0.0.0", port: int = 5001):
        self.lifecycle = SystemLifecycle()
        self.scheduler = BackgroundScheduler()
        self.host = host
        self.port = port
        self.db_path = db_path

        self.loader: Optional[PackageLoader] = None
        self.memory: Optional[MemoryManager] = None
        self.agent: Optional[Agent] = None
        self.workflow: Optional[WorkflowEngine] = None
        self.auditor = SecurityAuditor()

    def init(self):
        """
        加载核心运行组件：数据库表、加载技能包、加载记忆系统并启动生命周期。
        """
        self.lifecycle.set_state(LifecycleState.STARTING)

        # 1. 自动执行 SQLite 数据表升级迁移
        logger.info("正在执行数据库升级与表迁移自检...")
        run_all_migrations()

        # 2. 依次加载核心框架层
        self.loader = PackageLoader(db_path=self.db_path)
        self.memory = MemoryManager(db_path=self.db_path)
        self.agent = Agent(db_path=self.db_path)
        self.workflow = WorkflowEngine(loader=self.loader)

        # 3. 添加默认的诊断心跳调度服务
        self.scheduler.add_job("system_ping", 60, lambda: logger.info("系统定时心跳检查正常。"))

        self.lifecycle.set_state(LifecycleState.RUNNING)
        logger.info("Butler 核心运行时已全部就位并处于激活（RUNNING）状态。")

    def start(self, run_api_server: bool = True):
        """
        启动后台工作流调度引擎，并常驻拉起 API 安全网关对外提供连接。
        """
        self.init()
        self.scheduler.start()

        if run_api_server:
            self._start_api_server()

    def stop(self):
        self.lifecycle.set_state(LifecycleState.STOPPING)
        self.scheduler.stop()
        self.lifecycle.set_state(LifecycleState.SHUTDOWN)
        logger.info("Butler 运行时已平稳退出。")

    def _start_api_server(self):
        """
        启动用于连接 2x2 UI 交互前端的 FastAPI API 高安全网关。
        """
        try:
            from fastapi import FastAPI, HTTPException, Header, Depends
            import uvicorn
        except ImportError:
            logger.warning("FastAPI 或 Uvicorn 未安装，正在尝试自动热安装依赖...")
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"])
            from fastapi import FastAPI, HTTPException, Header, Depends
            import uvicorn

        app = FastAPI(title="Butler AI Employee OS API Gateway", version="2.0.0-Alpha")
        runtime_instance = self

        # 简单高效的 API 鉴权令牌，默认与配置对齐
        API_TOKEN = os.getenv("BUTLER_API_TOKEN", "BUTLER_TOKEN_PLACEHOLDER")

        def verify_token(authorization: Optional[str] = Header(None)):
            if not authorization:
                raise HTTPException(status_code=401, detail="请求未携带 Authorization 头（缺失 Token）")
            token = authorization.split(" ")[-1]
            if token != API_TOKEN:
                raise HTTPException(status_code=403, detail="API Token 校验未通过，无权访问")
            return True

        @app.get("/api/health")
        def health_check():
            return {
                "status": runtime_instance.lifecycle.state,
                "version": "2.0.0-Alpha"
            }

        @app.post("/api/task")
        def create_task(payload: Dict[str, Any], authenticated: bool = Depends(verify_token)):
            task_input = payload.get("task")
            if not task_input:
                raise HTTPException(status_code=400, detail="请求体中缺失必填的 'task' 字段。")

            task_id = f"task_{os.urandom(4).hex()}"
            runtime_instance.auditor.log_action_permission("api-gateway", f"通过 API 创建任务: {task_input}", "approved")

            # 开启后台线程非阻塞运行，防止 HTTP 请求堵塞
            def run():
                try:
                    runtime_instance.agent.run_task(task_input)
                except Exception as ex:
                    logger.error(f"异步执行 API 任务时抛出错误: {ex}")

            threading.Thread(target=run, daemon=True).start()

            return {
                "id": task_id,
                "status": "running"
            }

        @app.get("/api/packages")
        def list_packages(authenticated: bool = Depends(verify_token)):
            return runtime_instance.loader.registry.list_packages()

        @app.get("/api/tasks")
        def list_tasks(authenticated: bool = Depends(verify_token)):
            return runtime_instance.agent.list_tasks()

        logger.info(f"正在启动 API Gateway 高性能网关，监听地址: http://{self.host}:{self.port}")
        uvicorn.run(app, host=self.host, port=self.port, log_level="warning")
