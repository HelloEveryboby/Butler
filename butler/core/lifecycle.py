# -*- coding: utf-8 -*-
import logging

logger = logging.getLogger(__name__)

class LifecycleState:
    INIT = "INIT"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    SHUTDOWN = "SHUTDOWN"

class SystemLifecycle:
    """
    管理 Butler v2.0 Alpha 核心系统生命周期的状态机转换。
    """
    def __init__(self):
        self._state = LifecycleState.INIT
        logger.info(f"系统生命周期管理器已初始化，当前状态: {self._state}")

    @property
    def state(self) -> str:
        return self._state

    def set_state(self, new_state: str):
        logger.info(f"系统生命周期状态从 {self._state} 转换至 -> {new_state}")
        self._state = new_state

    def is_running(self) -> bool:
        return self._state == LifecycleState.RUNNING
