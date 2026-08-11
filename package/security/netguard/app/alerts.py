"""WebSocket 实时告警管理器"""

import json
from datetime import datetime, timezone

from fastapi import WebSocket


class AlertManager:
    """管理 WebSocket 连接并推送告警"""

    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}  # user_id -> [ws]

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)

    async def send_alert(self, user_id: int, alert: dict):
        """向指定用户的所有连接推送告警"""
        alert["timestamp"] = datetime.now(timezone.utc).isoformat()
        conns = self._connections.get(user_id, [])
        dead = []
        for ws in conns:
            try:
                await ws.send_json(alert)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def broadcast(self, alert: dict):
        """向所有连接广播"""
        alert["timestamp"] = datetime.now(timezone.utc).isoformat()
        for user_id in list(self._connections.keys()):
            await self.send_alert(user_id, alert)

    @property
    def active_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())


# 全局实例
alert_manager = AlertManager()
