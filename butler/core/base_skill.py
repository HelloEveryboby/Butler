import os
import json
import logging
import threading
import subprocess
import time
from datetime import datetime
from typing import Callable, Optional, Dict, Any

from butler.core.notifier_system import notifier
from butler.core.event_bus import event_bus
from butler.interpreter import interpreter

class BaseSkill:
    """
    Butler Skill 基类。

    这是所有“软件开发实体模块”的核心基类，提供了以下核心能力：
    1. **生命周期管理**: 通过 start() 和 stop() 管理技能的开启与关闭。
    2. **异步授权请求**: 提供非阻塞的权限提升接口，确保高危操作经过用户许可。
    3. **动态脚本生成与审计**: 支持动态编写并执行 Python/Shell 脚本，所有代码自动存入审计日志。
    """
    def __init__(self, skill_id: str):
        self.skill_id = skill_id
        self.logger = logging.getLogger(f"Skill_{skill_id}")
        self.skill_dir = os.path.join("skills", skill_id)
        self.audit_dir = "data/audit_logs"
        self._pending_auths: Dict[str, Dict[str, Callable]] = {}
        self._running = False
        self._threads = []

        # 确保审计目录存在
        os.makedirs(self.audit_dir, exist_ok=True)

        # 订阅授权响应事件 (由 Notifier 触发)
        if event_bus:
            event_bus.subscribe("NOTIFICATION_RESPONSE", self._handle_auth_response)

    def start(self):
        """
        启动技能。子类可重写此方法以初始化后台监听任务或加载特定数据。
        """
        self._running = True
        self.logger.info(f"技能 '{self.skill_id}' 已启动。")

    def stop(self):
        """
        停止技能。负责清理资源、停止派生的线程或子进程。
        """
        self._running = False
        self.logger.info(f"技能 '{self.skill_id}' 已停止。")

    def request_permission(self, title: str, content: str,
                           on_authorized: Callable,
                           on_denied: Optional[Callable] = None,
                           priority: int = 2) -> str:
        """
        发起异步提权请求。
        此方法是非阻塞的，Skill 发起请求后会立即返回 event_id，并在用户操作后触发回调。

        :param title: 提醒标题
        :param content: 请求权限的具体原因和内容
        :param on_authorized: 用户点击“允许”后的回调函数
        :param on_denied: 用户点击“拒绝”后的回调函数
        :param priority: 提醒优先级 (0-3)
        :return: event_id (用于追踪该请求)
        """
        event_id = notifier.push({
            "title": title,
            "content": content,
            "priority": priority,
            "source": self.skill_id,
            "action_data": {
                "is_auth_request": True,
                "skill_id": self.skill_id
            }
        })

        self._pending_auths[event_id] = {
            "on_authorized": on_authorized,
            "on_denied": on_denied
        }
        return event_id

    def _handle_auth_response(self, response: Dict[str, Any]):
        """
        处理来自 EventBus 的用户授权决策响应。
        """
        event_id = response.get("id")
        decision = response.get("decision") # "authorized" 或 "denied"

        if event_id in self._pending_auths:
            callbacks = self._pending_auths.pop(event_id)
            if decision == "authorized":
                if callbacks["on_authorized"]:
                    callbacks["on_authorized"](response.get("data"))
            else:
                if callbacks["on_denied"]:
                    callbacks["on_denied"](response.get("data"))

    def execute_dynamic_script(self, language: str, code: str, purpose: str = "unknown"):
        """
        生成、审计并执行动态脚本。

        这是“开发实体”核心能力的体现，允许技能根据当前上下文实时编写代码并执行。

        :param language: 脚本语言，支持 'python' 或 'shell'
        :param code: 脚本具体内容
        :param purpose: 脚本用途描述（将记录在审计日志中）
        :return: (success, output) 执行是否成功以及标准输出内容
        """
        # 1. 审计记录：在执行前将完整代码及用途保存至 data/audit_logs
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audit_filename = f"{timestamp}_{self.skill_id}_{language}.log"
        audit_path = os.path.join(self.audit_dir, audit_filename)

        audit_entry = {
            "timestamp": timestamp,
            "skill_id": self.skill_id,
            "language": language,
            "purpose": purpose,
            "code": code
        }

        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit_entry, f, indent=4, ensure_ascii=False)

        self.logger.info(f"动态脚本已审计并存档: {audit_path}")

        # 2. 执行脚本 (通过核心 Interpreter 执行)
        success, output = interpreter.run(language, code)

        # 3. 追加执行结果到审计日志
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n--- 执行结果 ---\n成功: {success}\n输出详情:\n{output}")

        return success, output

    def handle_request(self, action: str, **kwargs):
        """
        技能请求处理的抽象入口。子类必须实现此方法。
        """
        raise NotImplementedError("子类必须实现 handle_request 方法。")
