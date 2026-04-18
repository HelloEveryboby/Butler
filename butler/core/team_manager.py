import json
import threading
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from butler.core.constants import TEAM_DIR, DATA_DIR
from butler.core.message_bus import message_bus
from butler.core.task_manager import task_manager
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("TeamManager")

class TeamManager:
    """
    Butler 团队管理器 (Teammate Manager)
    负责孵化、配置和监控自主协作智能体。
    """
    _instance = None

    def __init__(self, jarvis_app=None):
        self.jarvis_app = jarvis_app
        self.team_dir = TEAM_DIR
        self.team_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.team_dir / "config.json"
        self.members = self._load_config()
        self.threads = {}
        self.lock = threading.Lock()
        self.poll_interval = 5
        self.idle_timeout = 300 # 5 minutes before shutdown if idle

    @classmethod
    def get_instance(cls, jarvis_app=None):
        if cls._instance is None:
            cls._instance = TeamManager(jarvis_app)
        return cls._instance

    def _load_config(self) -> List[Dict[str, Any]]:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                return data.get("members", [])
            except Exception as e:
                logger.error(f"Failed to load team config: {e}")
        return []

    def _save_config(self):
        with self.lock:
            data = {"members": self.members}
            self.config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _update_member_status(self, name: str, status: str, role: str = None):
        with self.lock:
            found = False
            for m in self.members:
                if m["name"] == name:
                    m["status"] = status
                    if role: m["role"] = role
                    found = True
                    break
            if not found:
                self.members.append({"name": name, "role": role or "assistant", "status": status})
        self._save_config()

    def spawn_teammate(self, name: str, role: str, prompt: str):
        """孵化一个新的自主智能体线程。"""
        with self.lock:
            for m in self.members:
                if m["name"] == name and m["status"] not in ("shutdown", "error"):
                    return f"Error: Teammate '{name}' is already {m['status']}."

        self._update_member_status(name, "starting", role)

        # Start teammate loop in a separate thread
        thread = threading.Thread(
            target=self._teammate_loop,
            args=(name, role, prompt),
            name=f"Teammate-{name}",
            daemon=True
        )
        self.threads[name] = thread
        thread.start()
        logger.info(f"Spawned teammate '{name}' with role '{role}'.")
        return f"Spawned teammate '{name}' (role: {role})."

    def _teammate_loop(self, name: str, role: str, initial_prompt: str):
        """Teammate autonomous execution loop with DeepSeek."""
        from butler.core.nlu_service import NLUService

        # 使用全局 NLU 服务
        nlu = self.jarvis_app.nlu_service if self.jarvis_app else None
        if not nlu:
            logger.error(f"Teammate {name} failed: NLU service not available.")
            return

        self._update_member_status(name, "working")
        messages = [{"role": "user", "content": initial_prompt}]

        # 身份注入
        system_prompt = (
            f"You are '{name}', role: {role}, an autonomous teammate in Butler. "
            f"Use message_bus to communicate and claim_task to take work. "
            f"Current directory: {os.getcwd()}."
        )

        last_activity = time.time()

        while True:
            # 1. 检查收件箱
            inbox = message_bus.read_inbox(name)
            for msg in inbox:
                if msg.get("type") == "shutdown_request":
                    self._update_member_status(name, "shutdown")
                    return
                messages.append({"role": "user", "content": f"Message from {msg['from']}: {msg['content']}"})
                last_activity = time.time()

            # 2. 压缩上下文
            if nlu.estimate_tokens(messages) > 2000:
                messages = nlu.compress_history(messages)

            # 3. 思考并尝试自动认领任务（如果空闲）
            unclaimed = [t for t in task_manager.list_business_tasks() if t["status"] == "pending" and not t["owner"]]
            if unclaimed:
                task = unclaimed[0]
                task_manager.claim_business_task(task["id"], name)
                messages.append({"role": "user", "content": f"Auto-claimed Task #{task['id']}: {task['subject']}"})
                self._update_member_status(name, "working")
                last_activity = time.time()

            # 4. 调用 LLM 进行一轮处理
            if messages:
                response = nlu.ask_llm(messages[-1]["content"], history=messages[:-1], system_override=system_prompt)
                if response and not response.startswith("Error:"):
                    messages.append({"role": "assistant", "content": response})
                    # 模拟任务处理进度（实际可扩展为工具调用）
                    if "完成" in response or "Done" in response:
                         self._update_member_status(name, "idle")

            # 5. 超时检查
            if time.time() - last_activity > self.idle_timeout:
                self._update_member_status(name, "shutdown")
                return

            time.sleep(self.poll_interval)

    def list_teammates(self) -> str:
        if not self.members:
            return "No teammates registered."
        lines = ["--- Teammate Status ---"]
        for m in self.members:
            lines.append(f"- {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

# Global instance
team_manager = TeamManager.get_instance()
