"""Butler 侧北向客户端：与 butler-dsh-connector 通信的唯一入口。

协议：4 字节大端长度前缀 + UTF-8 JSON 帧（见 connector/docs/protocol.md）。
线程模型：单读线程 + 单写锁；调用方通过 Call 对象获取流式 chunk 与终态结果，
无需关心帧多路复用细节。

用法：
    client = ConnectorClient("/run/user/1000/butler-dsh-connector.sock")
    client.start()
    client.wait_ready(timeout=5)

    call = client.invoke("doc-reader", {"path": "report.pdf"})
    for chunk in call.chunks():          # 流式（可选）
        render(chunk)
    result = call.result(timeout=30)     # 终态

    tools = client.capabilities()        # LLM 工具表注入
    client.close()
"""

from __future__ import annotations

import json
import os
import socket
import struct
import threading
import queue
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

PROTOCOL_VERSION = 1
MAX_FRAME_SIZE = 16 << 20  # 16 MiB，与 Go 侧一致

# 帧类型
TYPE_TOOL_INVOKE = "tool.invoke"
TYPE_TOOL_CHUNK = "tool.chunk"
TYPE_TOOL_RESULT = "tool.result"
TYPE_TOOL_CANCEL = "tool.cancel"
TYPE_EVENT_PUSH = "event.push"
TYPE_REGISTRY_SYNC = "registry.sync"
TYPE_REGISTRY_DIFF = "registry.diff"
TYPE_APPROVE_ASK = "approve.ask"
TYPE_APPROVE_ANSWER = "approve.answer"
TYPE_HEALTH_PING = "health.ping"
TYPE_HEALTH_PONG = "health.pong"
TYPE_ERROR = "error"

_DEFAULT_PIPE = r"\\.\pipe\butler-dsh-connector"


class ConnectorError(Exception):
    """连接器协议/执行错误。code 为稳定错误码。"""

    def __init__(self, code: str, message: str, data: Any = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.data = data


@dataclass
class Call:
    """一次工具调用的流式句柄。"""

    call_id: str
    tool: str
    _chunks: "queue.Queue[dict]" = field(default_factory=queue.Queue)
    _done: threading.Event = field(default_factory=threading.Event)
    _result: Optional[dict] = None
    _error: Optional[ConnectorError] = None

    def chunks(self, timeout: Optional[float] = None) -> Iterator[dict]:
        """迭代流式 chunk；结果到达或出错时结束。"""
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self._done.is_set() or not self._chunks.empty():
            remain = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                yield self._chunks.get(timeout=remain)
            except queue.Empty:
                return

    def result(self, timeout: Optional[float] = None) -> dict:
        """阻塞等待终态结果；超时抛 TimeoutError，失败抛 ConnectorError。"""
        if not self._done.wait(timeout):
            raise TimeoutError(f"tool call {self.call_id} timed out")
        if self._error is not None:
            raise self._error
        return self._result or {}


class ConnectorClient:
    """线程安全的北向客户端。"""

    def __init__(
        self,
        addr: Optional[str] = None,
        *,
        on_event: Optional[Callable[[dict], None]] = None,
        on_approve_ask: Optional[Callable[[dict], dict]] = None,
    ):
        self._addr = addr or self._default_addr()
        self._on_event = on_event
        self._on_approve_ask = on_approve_ask

        self._sock: Optional[socket.socket] = None
        self._wlock = threading.Lock()
        self._calls: dict[str, Call] = {}
        self._calls_lock = threading.Lock()

        self._registry: dict[str, dict] = {}
        self._registry_version = 0
        self._registry_cond = threading.Condition()

        self._ready = threading.Event()
        self._closed = threading.Event()
        self._recv_thread: Optional[threading.Thread] = None
        self._seq = 0

    # ---- lifecycle ----

    def start(self) -> None:
        """连接连接器并启动接收线程。"""
        if self._recv_thread is not None:
            return
        self._sock = self._connect()
        self._recv_thread = threading.Thread(
            target=self._recv_loop, name="dsh-connector-recv", daemon=True
        )
        self._recv_thread.start()
        # 主动请求一次能力全量，加速就绪。
        self._send({"type": TYPE_REGISTRY_SYNC, "id": self._next_id("sync")})

    def close(self) -> None:
        self._closed.set()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
        # 唤醒所有等待中的调用
        with self._calls_lock:
            calls = list(self._calls.values())
            self._calls.clear()
        for call in calls:
            call._error = ConnectorError("unavailable", "client closed")
            call._done.set()

    def wait_ready(self, timeout: float = 10.0) -> None:
        """等待首次 registry.sync 到达。"""
        if not self._ready.wait(timeout):
            raise TimeoutError("connector did not report capabilities in time")

    # ---- capabilities (供 LLM 工具表注入) ----

    def capabilities(self) -> list[dict]:
        """返回当前能力快照（name/description/schema/risk/source）。"""
        with self._registry_cond:
            return [dict(c) for c in self._registry.values()]

    def capability_version(self) -> int:
        with self._registry_cond:
            return self._registry_version

    # ---- tool invocation ----

    def invoke(
        self,
        tool: str,
        args: Optional[dict] = None,
        *,
        timeout_ms: int = 0,
    ) -> Call:
        """发起工具调用，立即返回流式句柄。"""
        call = Call(call_id=self._next_id("call"), tool=tool)
        with self._calls_lock:
            self._calls[call.call_id] = call
        payload = {
            "tool": tool,
            "args": args or {},
        }
        if timeout_ms:
            payload["timeoutMs"] = timeout_ms
        self._send({"type": TYPE_TOOL_INVOKE, "id": call.call_id, "payload": payload})
        return call

    def cancel(self, call_id: str, reason: str = "user cancelled") -> None:
        self._send(
            {
                "type": TYPE_TOOL_CANCEL,
                "id": call_id,
                "payload": {"reason": reason},
            }
        )

    def answer_approval(self, request_id: str, allowed: bool,
                        reason: str = "", remember: bool = False) -> None:
        """回答插件发起的审批请求。"""
        self._send(
            {
                "type": TYPE_APPROVE_ANSWER,
                "id": request_id,
                "payload": {
                    "requestId": request_id,
                    "allowed": allowed,
                    "reason": reason,
                    "remember": remember,
                },
            }
        )

    def ping(self, timeout: float = 5.0) -> bool:
        """活性探测。"""
        ping_id = self._next_id("ping")
        ev = threading.Event()
        state: dict[str, Any] = {}

        def _hook(frame: dict) -> bool:
            if frame.get("id") == ping_id and frame.get("type") == TYPE_HEALTH_PONG:
                state["ok"] = True
                ev.set()
                return True
            return False

        with self._pings_lock:
            self._pings.append(_hook)
        self._send({"type": TYPE_HEALTH_PING, "id": ping_id})
        ok = ev.wait(timeout)
        with self._pings_lock:
            self._pings.remove(_hook)
        return ok and state.get("ok", False)

    # ---- internals ----

    _pings: list = []
    _pings_lock = threading.Lock()

    @staticmethod
    def _default_addr() -> str:
        if os.name == "nt":
            return _DEFAULT_PIPE
        runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
        return os.path.join(runtime, "butler-dsh-connector.sock")

    def _connect(self) -> socket.socket:
        if os.name == "nt":
            # Windows named pipe 通过标准文件 API 访问
            return open(rf"{self._addr}", "r+b", buffering=0)  # type: ignore[return-value]
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._addr)
        return sock

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}-{int(time.time() * 1000)}"

    def _send(self, frame: dict) -> None:
        frame.setdefault("v", PROTOCOL_VERSION)
        frame.setdefault("ts", int(time.time() * 1000))
        body = json.dumps(frame, ensure_ascii=False).encode("utf-8")
        if len(body) > MAX_FRAME_SIZE:
            raise ConnectorError("malformed_frame", f"frame of {len(body)} bytes exceeds limit")
        with self._wlock:
            self._sock.sendall(struct.pack(">I", len(body)) + body)

    def _recv_loop(self) -> None:
        buf = b""
        try:
            while not self._closed.is_set():
                chunk = self._sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while len(buf) >= 4:
                    (n,) = struct.unpack(">I", buf[:4])
                    if n > MAX_FRAME_SIZE:
                        raise ConnectorError("malformed_frame", f"frame of {n} bytes exceeds limit")
                    if len(buf) < 4 + n:
                        break
                    body, buf = buf[4 : 4 + n], buf[4 + n :]
                    self._dispatch(json.loads(body.decode("utf-8")))
        except (OSError, ValueError) as exc:
            if not self._closed.is_set():
                self._fail_all(ConnectorError("unavailable", f"connection lost: {exc}"))
        finally:
            self._ready.set()

    def _dispatch(self, frame: dict) -> None:
        ftype = frame.get("type")
        fid = frame.get("id", "")

        with self._pings_lock:
            hooks = list(self._pings)
        for hook in hooks:
            if hook(frame):
                return

        if ftype == TYPE_TOOL_CHUNK:
            with self._calls_lock:
                call = self._calls.get(fid)
            if call is not None:
                call._chunks.put(frame.get("payload", {}))

        elif ftype == TYPE_TOOL_RESULT:
            with self._calls_lock:
                call = self._calls.pop(fid, None)
            if call is not None:
                call._result = frame.get("payload", {})
                call._done.set()

        elif ftype == TYPE_ERROR:
            with self._calls_lock:
                call = self._calls.pop(fid, None)
            err = frame.get("error") or {}
            exc = ConnectorError(
                err.get("code", "internal"), err.get("message", "unknown error"), err.get("data")
            )
            if call is not None:
                call._error = exc
                call._done.set()

        elif ftype == TYPE_REGISTRY_SYNC:
            payload = frame.get("payload", {})
            with self._registry_cond:
                self._registry = {
                    c["name"]: c for c in payload.get("capabilities", [])
                }
                self._registry_version = payload.get("version", 0)
                self._registry_cond.notify_all()
            self._ready.set()

        elif ftype == TYPE_REGISTRY_DIFF:
            payload = frame.get("payload", {})
            with self._registry_cond:
                for c in payload.get("upserts", []):
                    self._registry[c["name"]] = c
                for name in payload.get("removals", []):
                    self._registry.pop(name, None)
                self._registry_version = payload.get("to", self._registry_version)
                self._registry_cond.notify_all()

        elif ftype == TYPE_EVENT_PUSH:
            if self._on_event is not None:
                self._on_event(frame.get("payload", {}))

        elif ftype == TYPE_APPROVE_ASK:
            req = frame.get("payload", {})
            if self._on_approve_ask is not None:
                decision = self._on_approve_ask(req) or {}
                self.answer_approval(
                    req.get("requestId", fid),
                    bool(decision.get("allowed", False)),
                    str(decision.get("reason", "")),
                    bool(decision.get("remember", False)),
                )

    def _fail_all(self, exc: ConnectorError) -> None:
        with self._calls_lock:
            calls = list(self._calls.values())
            self._calls.clear()
        for call in calls:
            call._error = exc
            call._done.set()
