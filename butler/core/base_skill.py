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
    支持生命周期管理、异步授权请求、动态脚本生成与审计。
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

        # 订阅授权响应事件
        if event_bus:
            event_bus.subscribe("NOTIFICATION_RESPONSE", self._handle_auth_response)

    def start(self):
        """启动技能，子类可重写以初始化后台任务。"""
        self._running = True
        self.logger.info(f"Skill {self.skill_id} started.")

    def stop(self):
        """停止技能，清理资源。"""
        self._running = False
        self.logger.info(f"Skill {self.skill_id} stopped.")
        # 子类应负责关闭自己派生的特定进程或线程

    def request_permission(self, title: str, content: str,
                           on_authorized: Callable,
                           on_denied: Optional[Callable] = None,
                           priority: int = 2) -> str:
        """
        发起异步提权请求。

        :return: event_id
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
        """处理来自 EventBus 的授权响应。"""
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

        :param language: 'python' 或 'shell'
        :param code: 脚本代码内容
        :param purpose: 脚本用途说明（用于审计）
        """
        # 1. 审计记录
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

        self.logger.info(f"Dynamic script audited at {audit_path}")

        # 2. 执行脚本 (使用 Interpreter)
        # 注意：这里使用 Interpreter 的 run 方法，它内部会处理捕获输出
        success, output = interpreter.run(language, code)

        # 3. 记录执行结果到审计日志
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n--- EXECUTION RESULT ---\nSuccess: {success}\nOutput:\n{output}")

        return success, output

    def handle_request(self, action: str, **kwargs):
        """
        技能请求处理入口。子类应实现具体逻辑。
        """
        raise NotImplementedError("Subclasses must implement handle_request")
