"""翻译系统 BHL WebSocket 服务端。

供 Chrome 扩展的 butler-bhl Provider 调用，统一走后端翻译系统。
协议与 frontend/translate/background/providers/butler-bhl.ts 对齐。

请求:
  {"action": "translate.text", "payload": {"id": "...", "text": "...", "from": "auto", "to": "zh-CN"}}
响应:
  {"action": "translate.result", "payload": {"id": "...", "translated": "..."}}

额外支持（用于扩展与后端术语表/历史同步）:
  glossary.list  -> glossary.data
  glossary.add   -> ok
  history.list   -> history.data
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None

from .engine import TranslationSystem

logger = logging.getLogger("butler.translate.bhl")


class TranslationBHPServer:
    """翻译系统的 WebSocket 服务端。"""

    def __init__(self, system: Optional[TranslationSystem] = None,
                 host: str = "127.0.0.1", port: int = 8765):
        if websockets is None:
            raise RuntimeError("websockets library is required for the BHL server")
        self.system = system or TranslationSystem()
        self.host = host
        self.port = port

    async def _handler(self, websocket):
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            action = msg.get("action")
            payload = msg.get("payload", {}) or {}

            if action == "translate.text":
                await self._handle_translate(websocket, payload)
            elif action == "glossary.list":
                await websocket.send(json.dumps({
                    "action": "glossary.data",
                    "payload": {"terms": self.system.glossary.all()},
                }, ensure_ascii=False))
            elif action == "glossary.add":
                self.system.glossary.add(payload.get("source", ""), payload.get("target", ""))
                await websocket.send(json.dumps({"action": "ok"}))
            elif action == "history.list":
                entries = [e.to_dict() for e in self.system.history.all(limit=payload.get("limit", 50))]
                await websocket.send(json.dumps({
                    "action": "history.data",
                    "payload": {"entries": entries},
                }, ensure_ascii=False))
            else:
                await websocket.send(json.dumps({"action": "error", "payload": {"message": f"unknown action: {action}"}}))

    async def _handle_translate(self, websocket, payload):
        req_id = payload.get("id")
        text = payload.get("text", "")
        from_lang = payload.get("from", "auto")
        to_lang = payload.get("to", "zh-CN")
        try:
            translated = await asyncio.to_thread(
                self.system.translate, text, to_lang, from_lang
            )
            await websocket.send(json.dumps({
                "action": "translate.result",
                "payload": {"id": req_id, "translated": translated},
            }, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            logger.exception("translate.text failed")
            await websocket.send(json.dumps({
                "action": "translate.error",
                "payload": {"id": req_id, "error": str(e)},
            }, ensure_ascii=False))

    async def serve_forever(self):
        async with websockets.serve(self._handler, self.host, self.port):
            logger.info("Translation BHL server listening on ws://%s:%s", self.host, self.port)
            await asyncio.Future()  # run forever

    def run(self):
        asyncio.run(self.serve_forever())


def main():
    logging.basicConfig(level=logging.INFO)
    server = TranslationBHPServer()
    server.run()


if __name__ == "__main__":
    main()
