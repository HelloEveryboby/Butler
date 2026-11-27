"""MCP（Model Context Protocol）stdio 客户端 — 真正接入外部工具服务器。

MCP 的 stdio 传输就是「一行一个 JSON-RPC 消息」：

    客户端 → initialize → initialized 通知 → tools/list → tools/call

本模块不依赖官方 ``mcp`` 包：用 subprocess + JSON-RPC 实现最小可用客户端，
把远端工具注册进 Butler 的 ``ToolRegistry``，于是 Agent 可以直接调用
GitHub / 文件系统 / 数据库等任意 MCP server 提供的工具。
"""

from __future__ import annotations

import atexit
import contextlib
import json
import logging
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from .tool_registry import ToolRegistry
from .types import PermissionLevel

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "2024-11-05"
_NAME_RE = re.compile(r"[^0-9A-Za-z_-]")
_MAX_RESULT_CHARS = 12000
_clients: list[MCPStdioClient] = []


def _clean_name(value: str) -> str:
    return _NAME_RE.sub("_", str(value or ""))[:48] or "tool"


class MCPStdioClient:
    """一个 MCP server 子进程的 JSON-RPC 客户端。"""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        self.name = name
        self.command = command
        self.args = list(args or [])
        self.env = dict(env or {})
        self.process: subprocess.Popen | None = None
        self._next_id = 0
        self._pending: dict[int, threading.Event] = {}
        self._responses: dict[int, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self.server_info: dict[str, Any] = {}

    # ------------------------------------------------------------------ 生命周期
    def start(self, timeout: float = 20.0) -> bool:
        try:
            env = os.environ.copy()
            env.update({str(k): str(v) for k, v in self.env.items()})
            self.process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
        except Exception as exc:
            logger.error("MCP server %s 启动失败: %s", self.name, exc)
            return False

        self._running = True
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

        try:
            result = self.request(
                "initialize",
                {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "butler", "version": "2.0"},
                },
                timeout=timeout,
            )
            self.server_info = result.get("serverInfo", {}) if isinstance(result, dict) else {}
            self.notify("notifications/initialized", {})
            return True
        except Exception as exc:
            logger.error("MCP server %s 初始化失败: %s", self.name, exc)
            self.stop()
            return False

    def stop(self) -> None:
        self._running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                with contextlib.suppress(Exception):
                    self.process.kill()
            self.process = None

    # ------------------------------------------------------------------ IO
    def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        while self._running:
            line = self.process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("MCP %s 非 JSON 输出: %s", self.name, line[:200])
                continue

            request_id = message.get("id")
            if request_id is None:
                continue
            with self._lock:
                event = self._pending.get(request_id)
                if event is not None:
                    self._responses[request_id] = message
                    event.set()

    def _read_stderr(self) -> None:
        assert self.process and self.process.stderr
        while self._running:
            line = self.process.stderr.readline()
            if not line:
                break
            logger.debug("[MCP %s] %s", self.name, line.strip())

    def notify(self, method: str, params: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        with self._lock:
            self.process.stdin.write(json.dumps(payload) + "\n")
            self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any], timeout: float = 20.0) -> Any:
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP server 未启动")
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            event = threading.Event()
            self._pending[request_id] = event
            payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            try:
                self.process.stdin.write(json.dumps(payload) + "\n")
                self.process.stdin.flush()
            except Exception as exc:
                self._pending.pop(request_id, None)
                raise RuntimeError(f"MCP 写入失败: {exc}") from exc

        try:
            if not event.wait(timeout):
                raise TimeoutError(f"MCP {method} 超时")
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

        with self._lock:
            message = self._responses.pop(request_id, {})
        if "error" in message:
            raise RuntimeError(str(message["error"]))
        return message.get("result")

    # ------------------------------------------------------------------ 工具
    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", {})
        if isinstance(result, dict):
            return list(result.get("tools") or [])
        return []

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        result = self.request("tools/call", {"name": tool_name, "arguments": arguments}, timeout=60)
        if not isinstance(result, dict):
            return str(result)
        if result.get("isError"):
            raise RuntimeError(_content_text(result) or "工具返回错误")
        return _content_text(result)


def _content_text(result: dict[str, Any]) -> str:
    parts = []
    for item in result.get("content") or []:
        if isinstance(item, dict):
            if item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
    return "\n".join(parts)


def load_server_configs(config_get: Any = None) -> list[dict[str, Any]]:
    """读取 mcp.servers 配置（config.yaml），也支持 ~/.butler/mcp.json。"""
    servers: list[dict[str, Any]] = []
    try:
        if config_get is None:
            from package.core_utils.config_loader import config_loader

            config_get = config_loader.get
        configured = config_get("mcp.servers")
        if isinstance(configured, list):
            servers.extend(item for item in configured if isinstance(item, dict))
    except Exception:
        pass

    user_file = Path.home() / ".butler" / "mcp.json"
    if user_file.exists():
        try:
            data = json.loads(user_file.read_text(encoding="utf-8"))
            extra = data.get("servers") if isinstance(data, dict) else data
            if isinstance(extra, list):
                servers.extend(item for item in extra if isinstance(item, dict))
        except Exception as exc:
            logger.warning("读取 %s 失败: %s", user_file, exc)

    return servers


def register_mcp_tools(
    registry: ToolRegistry,
    servers: list[dict[str, Any]] | None = None,
    start_timeout: float = 20.0,
) -> list[str]:
    """连接配置中的 MCP server，并把它们的工具注册进 registry。

    返回成功接入的 server 名称列表。
    """
    servers = servers if servers is not None else load_server_configs()
    connected: list[str] = []

    for spec in servers:
        name = str(spec.get("name") or "mcp").strip()
        command = str(spec.get("command") or "").strip()
        if not command:
            logger.warning("MCP server %s 缺少 command，跳过", name)
            continue

        client = MCPStdioClient(
            name=name,
            command=command,
            args=list(spec.get("args") or []),
            env=dict(spec.get("env") or {}),
        )
        if not client.start(timeout=start_timeout):
            continue

        try:
            tools = client.list_tools()
        except Exception as exc:
            logger.error("MCP server %s tools/list 失败: %s", name, exc)
            client.stop()
            continue

        for tool in tools:
            tool_name = str(tool.get("name") or "")
            if not tool_name:
                continue
            exposed = f"mcp_{_clean_name(name)}_{_clean_name(tool_name)}"
            schema = tool.get("inputSchema") or {"type": "object", "properties": {}}

            def handler(
                arguments: dict[str, Any], _client=client, _tool=tool_name
            ) -> dict[str, Any]:
                try:
                    text = _client.call_tool(_tool, arguments or {})
                    return {"success": True, "content": text[:_MAX_RESULT_CHARS]}
                except Exception as exc:
                    return {"success": False, "error": f"MCP 工具 {_tool} 调用失败: {exc}"}

            registry.register(
                handler=handler,
                name=exposed,
                description=f"[MCP:{name}] {tool.get('description') or tool_name}",
                parameters=schema,
                permission_level=PermissionLevel.REQUIRE_CONFIRM,
            )

        _clients.append(client)
        connected.append(name)
        logger.info("MCP server %s 已接入，注册 %d 个工具", name, len(tools))

    if connected:
        atexit.register(_stop_all)
    return connected


def _stop_all() -> None:
    for client in list(_clients):
        with contextlib.suppress(Exception):
            client.stop()
    _clients.clear()
