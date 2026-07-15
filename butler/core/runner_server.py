import asyncio
import hmac
import hashlib
import json
import logging
import threading
import time
import uuid
import websockets
from typing import Dict, Any, Optional, List, Callable, Tuple

class RunnerInfo:
    """
    用于追踪已连接 Runner 状态的数据类
    """
    def __init__(self, runner_id: str, websocket, ip: str):
        self.runner_id = runner_id
        self.websocket = websocket
        self.ip = ip
        self.connected_at = time.time()
        self.last_seen = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runner_id": self.runner_id,
            "ip": self.ip,
            "connected_at": self.connected_at,
            "last_seen": self.last_seen,
            "alive_seconds": int(time.time() - self.connected_at)
        }

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
        
        # 核心数据结构重构：存储 RunnerInfo 实例
        self.runners: Dict[str, RunnerInfo] = {}
        
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server_thread: Optional[threading.Thread] = None
        self._event_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_counts = {}
        
        # 心跳超时时间 (单位: 秒)，默认60秒
        self.heartbeat_timeout = 60.0

    def _verify_token_strength(self, token: str) -> bool:
        """验证 Token 长度及安全性 (>= 16字符且非默认)"""
        if not token:
            return False
        if len(token) < 16:
            return False
        if token in ["BUTLER_SECRET_2026", "your_strong_token"]:
            return False
        return True

    def _calculate_signature(self, data: Dict[str, Any], token: str) -> str:
        """根据消息内容和 Token 计算 HMAC-SHA256 签名[cite: 1]"""
        # 为确保签名一致性，排除可能携带的旧签名，将 payload 或关键字段转为规范 JSON 字符串
        # 也可以对核心 payload + request_id + timestamp 进行加签
        payload_data = data.get("payload", "")
        if isinstance(payload_data, dict):
            payload_str = json.dumps(payload_data, sort_keys=True)
        else:
            payload_str = str(payload_data)

        # 结合关键字段防篡改
        msg_sig_source = f"{data.get('type','')}:{data.get('request_id','')}:{payload_str}"
        return hmac.new(
            token.encode("utf-8"),
            msg_sig_source.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _verify_signature(self, data: Dict[str, Any], received_sig: str, token: str) -> bool:
        """使用恒定时间比较防止时序攻击[cite: 1]"""
        if not received_sig:
            return False
        expected_sig = self._calculate_signature(data, token)
        return hmac.compare_digest(expected_sig, received_sig)

    def register_event_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Registers a callback for messages from runners (e.g., screenshots)."""
        self._event_callbacks.append(callback)

    async def _handler(self, websocket):
        """Handles incoming WebSocket connections with rate limiting, signature validation & heartbeat checks[cite: 1]."""
        runner_id = "unknown"
        ip = websocket.remote_address[0] if websocket.remote_address else "unknown"

        try:
            async for message in websocket:
                now = time.time()
                
                # 滑动窗口限流 (1s)
                self._request_counts[ip] = [t for t in self._request_counts.get(ip, []) if now - t < 1.0]
                if len(self._request_counts[ip]) > 50:
                    self.logger.warning(f"Rate limit exceeded for IP: {ip}. Dropping request.")
                    await websocket.send(json.dumps({"status": "error", "error": "Rate limit exceeded"}))
                    continue
                self._request_counts[ip].append(now)

                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                received_sig = data.get("sig")  # v2 协议签名[cite: 1]
                msg_runner_id = data.get("runner_id", "anonymous")

                # 获取最新 Token (SecretVault 优先)
                from butler.core.secret_vault import secret_vault
                try:
                    expected_token = secret_vault.get_secret("runner_token") or self.token
                except Exception:
                    expected_token = self.token

                # 1. 拦截不安全的弱密钥配置
                if not self._verify_token_strength(expected_token):
                    self.logger.error("RunnerServer blocked access: Token is missing, under 16 chars, or insecure![cite: 1]")
                    await websocket.close(1008, "Insecure Server Token Configuration")
                    return

                # 2. 验证 HMAC-SHA256 签名 (代替明文 Token 校验)[cite: 1]
                if not self._verify_signature(data, received_sig, expected_token):
                    self.logger.warning(f"Unauthorized connection signature from {websocket.remote_address}[cite: 1]")
                    await websocket.send(json.dumps({"status": "error", "error": "Unauthorized signature"}))
                    await websocket.close(1008, "Invalid HMAC Signature")
                    return

                # 3. 注册行为
                if msg_type == "register":
                    runner_id = msg_runner_id
                    self.runners[runner_id] = RunnerInfo(runner_id, websocket, ip)
                    self.logger.info(f"Runner registered: {runner_id} from {websocket.remote_address}")
                    
                    # 返回注册成功消息
                    resp = {"status": "ok", "data": f"Registered as {runner_id}"}
                    # 将响应签名发回 Go 端（可选，增强 Go 端对服务端的信任）
                    resp["sig"] = self._calculate_signature(resp, expected_token)
                    await websocket.send(json.dumps(resp))
                    continue

                # 更新最后活跃时间（心跳追踪）
                if runner_id in self.runners:
                    self.runners[runner_id].last_seen = now

                # 4. 请求响应路由
                req_id = data.get("request_id")
                if req_id and req_id in self._pending_requests:
                    self._loop.call_soon_threadsafe(
                        lambda r_id=req_id, d=data: self._pending_requests[r_id].set_result(d)
                        if r_id in self._pending_requests and not self._pending_requests[r_id].done() else None
                    )

                # 5. 事件回调分发
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

    async def _heartbeat_monitor(self):
        """异步心跳超时监控：定期清理无响应的僵尸连接[cite: 1]"""
        while True:
            await asyncio.sleep(15)
            now = time.time()
            dead_runners = []
            for rid, info in list(self.runners.items()):
                if now - info.last_seen > self.heartbeat_timeout:
                    self.logger.warning(f"Runner {rid} heartbeat timeout. Closing connection.[cite: 1]")
                    dead_runners.append(rid)
                    try:
                        await info.websocket.close(1011, "Heartbeat Timeout")
                    except Exception:
                        pass
            for rid in dead_runners:
                if rid in self.runners:
                    del self.runners[rid]

    async def _broadcast_metrics_coro(self, stats: Dict[str, Any]):
        """Internal coroutine for broadcasting metrics with signatures."""
        if not self.runners: 
            return
            
        from butler.core.secret_vault import secret_vault
        try:
            expected_token = secret_vault.get_secret("runner_token") or self.token
        except Exception:
            expected_token = self.token

        msg_dict = {"type": "metrics", "data": stats}
        # 如果是安全 Token，附加消息签名[cite: 1]
        if self._verify_token_strength(expected_token):
            msg_dict["sig"] = self._calculate_signature(msg_dict, expected_token)

        msg = json.dumps(msg_dict)
        await asyncio.gather(*(info.websocket.send(msg) for info in self.runners.values()), return_exceptions=True)

    def broadcast_metrics(self, stats: Dict[str, Any]):
        """Thread-safe way to broadcast metrics to all connected clients."""
        cpu = stats.get("cpu", 0)
        if cpu > 90 and time.time() % 2 < 1: # 50% frame skip in red zone
            return

        if self._loop and self.runners:
            asyncio.run_coroutine_threadsafe(self._broadcast_metrics_coro(stats), self._loop)

    def start(self):
        """Starts the server in a background thread."""
        if not self._verify_token_strength(self.token):
             self.logger.error("RunnerServer cannot start: Provided initialization token is too weak or missing.[cite: 1]")
             return

        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()
        self.logger.info(f"RunnerServer starting on {self.host}:{self.port}")

    def _run_server(self):
        async def main():
            self._loop = asyncio.get_running_loop()

            # 开启后台心跳监控协程[cite: 1]
            asyncio.create_task(self._heartbeat_monitor())

            # Setup SSL/TLS context for secure WSS connection[cite: 1]
            import ssl
            from butler.core.sec_utils.certs import generate_self_signed_cert

            ssl_context = None
            try:
                ssl_cert, ssl_key = generate_self_signed_cert()
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(ssl_cert, ssl_key)
                self.logger.info("RunnerServer starting with SSL (wss://) enabled.[cite: 1]")
            except Exception as e:
                self.logger.error(f"Failed to load SSL context for RunnerServer, falling back to plain ws: {e}")

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

    def send_command(self, runner_id: str, cmd_type: str, payload: str, skill_config: dict = None, request_id: str = None) -> Tuple[bool, str]:
        """Sends a command to a specific runner with automatic signature generation[cite: 1]."""
        if runner_id not in self.runners:
            return False, f"Runner {runner_id} not connected"

        websocket = self.runners[runner_id].websocket
        
        # 准备下发的数据结构（不再下发敏感明文 Token，改发 HMAC sig）[cite: 1]
        msg = {
            "type": cmd_type,
            "payload": payload,
        }
        if skill_config:
            msg["skill_config"] = skill_config
        if request_id:
            msg["request_id"] = request_id

        # 动态获取 Token 并为命令计算签名[cite: 1]
        from butler.core.secret_vault import secret_vault
        try:
            expected_token = secret_vault.get_secret("runner_token") or self.token
        except Exception:
            expected_token = self.token

        msg["sig"] = self._calculate_signature(msg, expected_token)

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
            request_id = uuid.uuid4().hex

        websocket = self.runners[runner_id].websocket
        msg = {
            "type": cmd_type,
            "payload": payload,
            "request_id": request_id
        }

        # 计算并填充签名[cite: 1]
        from butler.core.secret_vault import secret_vault
        try:
            expected_token = secret_vault.get_secret("runner_token") or self.token
        except Exception:
            expected_token = self.token
        msg["sig"] = self._calculate_signature(msg, expected_token)

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
        """Synchronously sends a command and blocks the calling thread."""
        if not self._loop:
            return {"status": "fail", "error": "RunnerServer event loop is not running"}

        request_id = uuid.uuid4().hex
        future = asyncio.run_coroutine_threadsafe(
            self.send_command_async(runner_id, cmd_type, payload, request_id, timeout),
            self._loop
        )
        try:
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

    def get_all_runners_info(self) -> List[Dict[str, Any]]:
        """
        获取所有已注册 Runner 的详细跟踪状态数据[cite: 1]
        """
        return [info.to_dict() for info in self.runners.values()]

    def health_check(self) -> Dict[str, Any]:
        """
        服务端健康度及状态自检[cite: 1]
        """
        from butler.core.secret_vault import secret_vault
        try:
            current_token = secret_vault.get_secret("runner_token") or self.token
        except Exception:
            current_token = self.token

        return {
            "server_running": self._loop is not None and self._loop.is_running(),
            "registered_runners_count": len(self.runners),
            "token_configured": current_token is not None,
            "token_secure": self._verify_token_strength(current_token)
        }

# v2 废弃初始化即实例化的不安全做法，提供延迟初始化方法[cite: 1]
_global_server: Optional[RunnerServer] = None

def init_runner_server(host: str = "127.0.0.1", port: int = 8000, token: str = None) -> RunnerServer:
    """初始化并配置全局 RunnerServer 实例[cite: 1]"""
    global _global_server
    _global_server = RunnerServer(host=host, port=port, token=token)
    return _global_server

def get_runner_server() -> Optional[RunnerServer]:
    """获取全局配置的 RunnerServer 实例[cite: 1]"""
    return _global_server
