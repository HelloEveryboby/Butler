import json
import time
import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from butler.core.constants import INBOX_DIR
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("MessageBus")

class MessageBus:
    """
    Butler 协同消息总线 (Persistent Message Bus)
    基于文件系统实现，支持智能体之间的异步通讯、广播及状态持久化。
    """
    _instance = None

    def __init__(self):
        self.inbox_dir = INBOX_DIR
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.valid_msg_types = {
            "message", "broadcast", "shutdown_request",
            "shutdown_response", "plan_approval_request", "plan_approval_response"
        }

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MessageBus()
        return cls._instance

    def send(self, sender: str, to: str, content: str, msg_type: str = "message", extra: Dict[str, Any] = None) -> str:
        """发送消息到指定接收者的收件箱。"""
        # Sanitize recipient name to prevent path traversal
        to = "".join(c for c in to if c.isalnum() or c in ('_', '-')).strip()
        if not to:
            return "Error: Invalid recipient name."

        if msg_type not in self.valid_msg_types:
            logger.warning(f"Unknown message type: {msg_type}")

        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time()
        }
        if extra:
            msg.update(extra)

        with self.lock:
            try:
                # 每个接收者一个 .jsonl 文件
                path = self.inbox_dir / f"{to}.jsonl"
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
                logger.debug(f"Message from '{sender}' to '{to}' sent.")
                return f"Sent {msg_type} to {to}"
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                return f"Error: {e}"

    def read_inbox(self, recipient: str) -> List[Dict[str, Any]]:
        """读取并清空指定接收者的收件箱内容。"""
        recipient = "".join(c for c in recipient if c.isalnum() or c in ('_', '-')).strip()
        if not recipient: return []

        path = self.inbox_dir / f"{recipient}.jsonl"

        with self.lock:
            if not path.exists():
                return []

            try:
                content = path.read_text(encoding="utf-8").strip()
                if not content:
                    return []

                messages = []
                for line in content.splitlines():
                    if line.strip():
                        messages.append(json.loads(line))

                # 读取后清空（消费模式）
                path.write_text("", encoding="utf-8")
                return messages
            except Exception as e:
                logger.error(f"Failed to read inbox for '{recipient}': {e}")
                return []

    def broadcast(self, sender: str, content: str, recipients: List[str]) -> str:
        """向多个接收者广播消息。"""
        count = 0
        for name in recipients:
            if name != sender:
                self.send(sender, name, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"

# Global instance
message_bus = MessageBus.get_instance()
