"""WebSocket 实时告警路由"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.alerts import alert_manager
from app.utils.security import decode_token
from app.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket 实时告警推送。
    连接时通过 query param 认证：ws://host/ws/alerts?token=<jwt>
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = int(payload["sub"])

    # 验证用户存在
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="User not found")
            return

    await alert_manager.connect(user_id, websocket)
    try:
        while True:
            # 保持连接，接收心跳
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        alert_manager.disconnect(user_id, websocket)
