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
        self._pending_requests: Dict[str, asyncio.Future] = {}

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

                # Check if this is a response to a pending request with a request_id correlation
                req_id = data.get("request_id")
                if req_id and req_id in self._pending_requests:
                    self._loop.call_soon_threadsafe(
                        lambda r_id=req_id, d=data: self._pending_requests[r_id].set_result(d)
                        if r_id in self._pending_requests and not self._pending_requests[r_id].done() else None
                    )

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

    def send_command(self, runner_id: str, cmd_type: str, payload: str, skill_config: dict = None, request_id: str = None):
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
        if request_id:
            msg["request_id"] = request_id

        future = asyncio.run_coroutine_threadsafe(websocket.send(json.dumps(msg)), self._loop)
        try:
            future.result(timeout=5)
            return True, "Command sent"
        except Exception as e:
            return False, str(e)

    async def send_command_async(self, runner_id: str, cmd_type: str, payload: str, request_id: str = None, timeout: float = 30.0) -> Dict[str, Any]:
        """Asynchronously sends a command and waits for a response containing the same request_id."""
        if runner_id not in self.runners:
            return {"status": "fail", "error": f"Runner {runner_id} not connected"}

        if not request_id:
            import uuid
            request_id = uuid.uuid4().hex

        websocket = self.runners[runner_id]
        msg = {
            "type": cmd_type,
            "payload": payload,
            "token": self.token,
            "request_id": request_id
        }

        # Create future to wait for response
        future = self._loop.create_future()
        self._pending_requests[request_id] = future

        try:
            await websocket.send(json.dumps(msg))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return {"status": "fail", "error": f"Request {request_id} timed out after {timeout} seconds"}
        except Exception as e:
            return {"status": "fail", "error": str(e)}
        finally:
            self._pending_requests.pop(request_id, None)

    def send_command_sync(self, runner_id: str, cmd_type: str, payload: str, timeout: float = 30.0) -> Dict[str, Any]:
        """Synchronously sends a command and blocks the calling thread until a response with a matching request_id is received."""
        if not self._loop:
            return {"status": "fail", "error": "RunnerServer event loop is not running"}

        import uuid
        request_id = uuid.uuid4().hex

        future = asyncio.run_coroutine_threadsafe(
            self.send_command_async(runner_id, cmd_type, payload, request_id, timeout),
            self._loop
        )
        try:
            # Wait for the async operation to complete (timeout + 1s padding for safe thread wait)
            return future.result(timeout=timeout + 1.0)
        except Exception as e:
            return {"status": "fail", "error": f"Synchronous execution failed: {e}"}

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
