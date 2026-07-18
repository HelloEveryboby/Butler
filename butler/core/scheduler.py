# -*- coding: utf-8 -*-
import time
import threading
import logging
from typing import Callable, List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class BackgroundScheduler:
    """
    后台轻量级自动化任务和定时事件调度管理器。
    """
    def __init__(self):
        self._jobs: List[Dict[str, Any]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_job(self, name: str, interval_seconds: int, callback: Callable[[], None]):
        self._jobs.append({
            "name": name,
            "interval": interval_seconds,
            "callback": callback,
            "last_run": time.time()
        })
        logger.info(f"成功添加后台调度任务 '{name}'，调度间隔 {interval_seconds} 秒。")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("后台定时任务调度器启动成功。")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        logger.info("后台定时任务调度器已停止。")

    def _run_loop(self):
        while self._running:
            now = time.time()
            for job in self._jobs:
                if now - job["last_run"] >= job["interval"]:
                    try:
                        logger.info(f"正在调起执行定时任务: {job['name']}")
                        job["callback"]()
                    except Exception as e:
                        logger.error(f"执行定时任务 {job['name']} 时遇到异常: {e}")
                    finally:
                        job["last_run"] = now
            time.sleep(1)
