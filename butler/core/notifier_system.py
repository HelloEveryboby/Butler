"""
Notifier System (智能事件提醒系统)
作为 Butler 的核心服务，负责处理来自系统后端、硬件或 Skill 的提醒请求。
遵循 Zero-dependency 原则，仅使用 Python 标准库。
"""

import time
import json
import sqlite3
import threading
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

# 尝试导入内部组件，若在独立测试环境下则使用 Mock
try:
    from butler.core.event_bus import event_bus
    from package.device.hardware_manager import HardwareManager
except ImportError:
    event_bus = None
    HardwareManager = None

class Notifier:
    def __init__(self, db_path: str = "data/notifications.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("Notifier")
        self._init_db()
        self._timer_lock = threading.Lock()
        self._active_timers: Dict[str, threading.Timer] = {}

    def _init_db(self):
        """初始化 SQLite 数据库用于持久化提醒事件。"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    priority INTEGER,
                    source TEXT,
                    timestamp TEXT,
                    status TEXT,
                    action_data TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")

    def push(self, event_data: Dict[str, Any]):
        """
        供外部 Skill 或系统组件调用的主接口。

        :param event_data: 包含 title, content, priority, source, action_data 等。
        """
        event_id = f"notif_{int(time.time() * 1000)}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        event = {
            "id": event_id,
            "title": event_data.get("title", "系统提醒"),
            "content": event_data.get("content", ""),
            "priority": event_data.get("priority", 0),
            "source": event_data.get("source", "system"),
            "timestamp": timestamp,
            "action_data": json.dumps(event_data.get("action_data", {})),
            "status": "active"
        }

        # 1. 持久化到数据库
        self._persist_event(event)

        # 2. 音量算法联动 (如果可用)
        self._apply_volume_linkage()

        # 3. 通过 EventBus 发送给前端/其他订阅者
        if event_bus:
            event_bus.emit("NOTIFICATION_PUSH", event)

        # 4. 启动自动关闭计时器 (5-10秒，根据优先级或设定)
        duration = 5 if event["priority"] < 2 else 10
        self._start_auto_close_timer(event_id, duration)

        return event_id

    def _persist_event(self, event: Dict[str, Any]):
        """将事件存入 SQLite。"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO notifications (id, title, content, priority, source, timestamp, status, action_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event["id"], event["title"], event["content"],
                event["priority"], event["source"], event["timestamp"],
                event["status"], event["action_data"]
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"数据持久化失败: {e}")

    def _apply_volume_linkage(self):
        """调用硬件管理器执行音量自适应调节。"""
        # 在真实运行环境中，尝试从 event_bus 或单例模式获取硬件管理器状态并触发更新
        try:
            # 方案 A: 如果 HardwareManager 已经初始化为单例或在全局可用
            # 这里我们发出一个信号，让拥有 HardwareManager 的组件执行音量对齐
            if event_bus:
                event_bus.emit("NOTIFIER_PRE_ALERT_VOLUME_SYNC")
        except Exception as e:
            self.logger.error(f"音量联动失败: {e}")

    def _start_auto_close_timer(self, event_id: str, duration: int):
        """启动定时器，到期后通知前端隐藏该弹窗。"""
        def on_timeout():
            with self._timer_lock:
                if event_id in self._active_timers:
                    del self._active_timers[event_id]

            if event_bus:
                event_bus.emit("NOTIFICATION_CLOSE", {"id": event_id})

            # 更新数据库状态
            self.update_status(event_id, "closed")

        timer = threading.Timer(duration, on_timeout)
        with self._timer_lock:
            self._active_timers[event_id] = timer
            timer.start()

    def update_status(self, event_id: str, status: str):
        """更新通知状态（如：closed, modified）。"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE notifications SET status = ? WHERE id = ?', (status, event_id))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"状态更新失败: {e}")

    def get_history(self, limit: int = 20):
        """获取历史提醒记录。"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?', (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"查询历史失败: {e}")
            return []

# 全局服务实例
notifier = Notifier()

if __name__ == "__main__":
    # 简单测试逻辑
    logging.basicConfig(level=logging.INFO)
    n = Notifier("data/test_notifications.db")
    test_id = n.push({
        "title": "测试提醒",
        "content": "这是一条 5 秒后会自动关闭的测试消息。",
        "priority": 1
    })
    print(f"已发送提醒: {test_id}")
    time.sleep(6)
    print("历史记录:", n.get_history())
