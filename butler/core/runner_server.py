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
        """Handles incoming WebSocket connections with rate limiting and Token validation."""
        import time
        runner_id = "unknown"
        ip = websocket.remote_address[0] if websocket.remote_address else "unknown"

        # Simple IP Rate Limiting Initialization
        if not hasattr(self, "_request_counts"):
            self._request_counts = {}

        try:
            async for message in websocket:
                # Rate limit check (sliding window 1s)
                now = time.time()
                self._request_counts[ip] = [t for t in self._request_counts.get(ip, []) if now - t < 1.0]
                if len(self._request_counts[ip]) > 50:  # Max 50 requests/sec limit
                    self.logger.warning(f"Rate limit exceeded for IP: {ip}. Dropping request.")
                    await websocket.send(json.dumps({"status": "error", "error": "Rate limit exceeded"}))
                    continue
                self._request_counts[ip].append(now)

                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                msg_token = data.get("token")
                msg_runner_id = data.get("runner_id", "anonymous")

                # Dynamic Token Validation from SecretVault (with fallback to configuration token)
                from butler.core.secret_vault import secret_vault
                try:
                    expected_token = secret_vault.get_secret("runner_token") or self.token
                except Exception:
                    expected_token = self.token

                if not expected_token or msg_token != expected_token:
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

    async def _broadcast_metrics_coro(self, stats: Dict[str, Any]):
        """Internal coroutine for broadcasting metrics."""
        if not self.runners: return
        msg = json.dumps({"type": "metrics", "data": stats})
        # Use asyncio.wait to handle all sends in parallel
        await asyncio.gather(*(r.send(msg) for r in self.runners.values()), return_exceptions=True)

    def broadcast_metrics(self, stats: Dict[str, Any]):
        """Thread-safe way to broadcast metrics to all connected clients."""
        # Implement DWT-aware broadcast: skip frames if system load is too high
        cpu = stats.get("cpu", 0)
        if cpu > 90 and time.time() % 2 < 1: # 50% frame skip in red zone
            return

        if self._loop and self.runners:
            asyncio.run_coroutine_threadsafe(self._broadcast_metrics_coro(stats), self._loop)

    def start(self):
        """Starts the server in a background thread."""
        if not self.token:
             self.logger.error("RunnerServer cannot start without a valid token.")
             return

        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()
        self.logger.info(f"RunnerServer starting on {self.host}:{self.port}")

    def _run_server(self):
        async def main():
            self._loop = asyncio.get_running_loop()

            # Setup SSL/TLS context for secure WSS connection
            import ssl
            from butler.core.sec_utils.certs import generate_self_signed_cert

            ssl_context = None
            try:
                ssl_cert, ssl_key = generate_self_signed_cert()
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(ssl_cert, ssl_key)
                self.logger.info("RunnerServer starting with SSL (wss://) enabled.")
            except Exception as e:
                self.logger.error(f"Failed to load SSL context for RunnerServer, falling back to plain ws: {e}")

            # Enforce max connection size limit (2MB) to prevent buffer-based DOS
            async with websockets.serve(
                self._handler,
                self.host,
                self.port,
                ssl=ssl_context,
                max_size=2 * 1024 * 1024 # 2MB limit
            ):
                await asyncio.Future()  # run forever

        try:
            asyncio.run(main())
        except Exception as e:
            self.logger.error(f"RunnerServer loop crash: {e}")

    def send_command(self, runner_id: str, cmd_type: str, payload: str, skill_config: dict = None):
        """Sends a command to a specific runner."""
        if runner_id not in self.runners:
            return False, f"Runner {runner_id} not connected"

        websocket = self.runners[runner_id]
        msg = {
            "type": cmd_type,
            "payload": payload,
            "token": self.token
        }
        if skill_config:
            msg["skill_config"] = skill_config

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
