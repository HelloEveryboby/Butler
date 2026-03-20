import asyncio
import json
import logging
import threading
import uuid
import websockets
from typing import Dict, Any, Optional, List, Callable

class RunnerServer:
    """
    WebSocket server for managing remote Butler-Runner nodes.
    By default, it binds to 127.0.0.1 for security.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8000, token: str = None):
        self.host = host
        self.port = port
        self.token = token
        self.logger = logging.getLogger("RunnerServer")
        self.runners: Dict[str, Any] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server_thread: Optional[threading.Thread] = None
        self._event_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        if not self.token or self.token == "BUTLER_SECRET_2026":
            self.logger.warning("⚠️ RunnerServer is using a default or missing token! This is insecure.")

    def register_event_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Registers a callback for messages from runners (e.g., screenshots)."""
        self._event_callbacks.append(callback)

    async def _handler(self, websocket):
        """Handles incoming WebSocket connections."""
        runner_id = "unknown"
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                msg_token = data.get("token")
                msg_runner_id = data.get("runner_id", "anonymous")

                # Validate token
                if not self.token or msg_token != self.token:
                    self.logger.warning(f"Unauthorized connection attempt from {websocket.remote_address}")
                    await websocket.send(json.dumps({"status": "error", "error": "Unauthorized"}))
                    await websocket.close(1008, "Invalid Token")
                    return

                if msg_type == "register":
                    runner_id = msg_runner_id
                    self.runners[runner_id] = websocket
                    self.logger.info(f"Runner registered: {runner_id} from {websocket.remote_address}")
                    await websocket.send(json.dumps({"status": "ok", "data": f"Registered as {runner_id}"}))
                    continue

                # Handle responses/events
                for callback in self._event_callbacks:
                    try:
                        callback(runner_id, data)
                    except Exception as e:
                        self.logger.error(f"Error in event callback: {e}")

        except websockets.ConnectionClosed:
            self.logger.info(f"Runner disconnected: {runner_id}")
        finally:
            if runner_id in self.runners:
                del self.runners[runner_id]

    def start(self):
        """Starts the server in a background thread."""
        if not self.token or self.token == "BUTLER_SECRET_2026":
             self.logger.error("RunnerServer cannot start with a default or missing token. Please configure a secure token.")
             return

        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()
        self.logger.info(f"RunnerServer starting on {self.host}:{self.port}")

    def _run_server(self):
        async def main():
            self._loop = asyncio.get_running_loop()
            async with websockets.serve(self._handler, self.host, self.port):
                await asyncio.Future()  # run forever

        try:
            asyncio.run(main())
        except Exception as e:
            self.logger.error(f"RunnerServer loop crash: {e}")

    def send_command(self, runner_id: str, cmd_type: str, payload: str):
        """Sends a command to a specific runner."""
        if runner_id not in self.runners:
            return False, f"Runner {runner_id} not connected"

        websocket = self.runners[runner_id]
        msg = {
            "type": cmd_type,
            "payload": payload,
            "token": self.token
        }

        future = asyncio.run_coroutine_threadsafe(websocket.send(json.dumps(msg)), self._loop)
        try:
            future.result(timeout=5)
            return True, "Command sent"
        except Exception as e:
            return False, str(e)

    def broadcast_command(self, cmd_type: str, payload: str):
        """Broadcasts a command to all connected runners."""
        results = {}
        for rid in list(self.runners.keys()):
            success, msg = self.send_command(rid, cmd_type, payload)
            results[rid] = (success, msg)
        return results

    def list_runners(self) -> List[str]:
        return list(self.runners.keys())

# Global instance
runner_server = RunnerServer()
