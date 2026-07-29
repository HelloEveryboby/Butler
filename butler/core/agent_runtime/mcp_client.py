"""
MCP Client — Model Context Protocol 工具服务器集成。

参考架构：OpenHands V1 的 MCP 集成组件。

MCP (Model Context Protocol) 是 Anthropic 提出的标准协议，用于：
    - 连接外部工具服务器
    - 透明地将 MCP 工具转换为 SDK 工具格式
    - 管理服务器生命周期和通信

核心功能：
    1. 发现 MCP 服务器上的工具
    2. 将 MCP 工具注册到 ToolRegistry
    3. 代理工具调用到 MCP 服务器
    4. 管理服务器连接生命周期

注意：这是 MCP 客户端的骨架实现，实际使用需要安装 mcp 包。
"""

from __future__ import annotations

import logging
from typing import Any

from .tool_registry import ToolRegistry
from .types import PermissionLevel, ToolResult

logger = logging.getLogger(__name__)


class MCPServerConfig:
    """
    MCP 服务器配置。

    支持 stdio 和 SSE 两种传输方式：
        - stdio: 通过子进程标准输入/输出通信
        - SSE: 通过 Server-Sent Events 通信
    """

    def __init__(
        self,
        name: str,
        transport: str = "stdio",
        command: str | None = None,
        args: list[str] | None = None,
        url: str | None = None,
        env: dict[str, str] | None = None,
    ):
        self.name = name
        self.transport = transport
        self.command = command
        self.args = args or []
        self.url = url
        self.env = env or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "transport": self.transport,
            "command": self.command,
            "args": self.args,
            "url": self.url,
            "env": self.env,
        }


class MCPClient:
    """
    MCP 客户端。

    参考 OpenHands V1 的 MCP 集成：
        - 连接 MCP 兼容的工具服务器
        - 将 MCP 工具透明转换为 SDK 工具格式
        - 管理服务器生命周期和通信

    使用方式::

        client = MCPClient()

        # 添加服务器配置
        client.add_server(MCPServerConfig(
            name="filesystem",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        ))

        # 连接并发现工具
        tools = client.discover_tools()

        # 注册到 ToolRegistry
        client.register_tools(registry)

        # 调用 MCP 工具
        result = client.call_tool("filesystem_read_file", {"path": "/tmp/test.txt"})
    """

    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._connections: dict[str, Any] = {}
        self._discovered_tools: dict[str, dict[str, Any]] = {}

    def add_server(self, config: MCPServerConfig) -> None:
        """添加 MCP 服务器配置。"""
        self._servers[config.name] = config
        logger.info(f"Added MCP server: {config.name} ({config.transport})")

    def remove_server(self, name: str) -> None:
        """移除 MCP 服务器。"""
        if name in self._servers:
            self.disconnect(name)
            del self._servers[name]
            logger.info(f"Removed MCP server: {name}")

    def list_servers(self) -> list[str]:
        """列出所有已配置的服务器名称。"""
        return list(self._servers.keys())

    async def connect(self, server_name: str) -> bool:
        """
        连接到 MCP 服务器。

        参数:
            server_name: 服务器名称

        返回:
            是否连接成功
        """
        config = self._servers.get(server_name)
        if not config:
            logger.error(f"MCP server '{server_name}' not configured")
            return False

        try:
            # 尝试导入 mcp 包
            try:
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
                from mcp.client.sse import sse_client
            except ImportError:
                logger.warning(
                    "mcp package not installed. Install with: pip install mcp"
                )
                return False

            if config.transport == "stdio":
                if not config.command:
                    logger.error(f"stdio transport requires 'command'")
                    return False

                params = StdioServerParameters(
                    command=config.command,
                    args=config.args,
                    env={**config.env},
                )
                transport = stdio_client(params)

            elif config.transport == "sse":
                if not config.url:
                    logger.error(f"SSE transport requires 'url'")
                    return False
                transport = sse_client(config.url)

            else:
                logger.error(f"Unknown transport: {config.transport}")
                return False

            # 创建会话
            read, write = await transport.__aenter__()
            session = ClientSession(read, write)
            await session.__aenter__()

            # 初始化
            await session.initialize()

            self._connections[server_name] = {
                "session": session,
                "transport": transport,
            }

            logger.info(f"Connected to MCP server: {server_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{server_name}': {e}")
            return False

    def disconnect(self, server_name: str) -> None:
        """断开 MCP 服务器连接。"""
        conn = self._connections.pop(server_name, None)
        if conn:
            try:
                session = conn.get("session")
                transport = conn.get("transport")

                # 尝试同步清理（如果有运行中的事件循环）
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 在运行中的事件循环中，调度异步清理
                        asyncio.ensure_future(self._async_cleanup(session, transport))
                    else:
                        loop.run_until_complete(self._async_cleanup(session, transport))
                except RuntimeError:
                    # 没有事件循环，创建新的来清理
                    asyncio.run(self._async_cleanup(session, transport))
            except Exception as e:
                logger.warning(f"Error disconnecting from '{server_name}': {e}")

            logger.info(f"Disconnected from MCP server: {server_name}")

    async def _async_cleanup(self, session: Any, transport: Any) -> None:
        """异步清理 MCP 会话和传输资源。"""
        try:
            if session and hasattr(session, "__aexit__"):
                await session.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"Session cleanup error: {e}")
        try:
            if transport and hasattr(transport, "__aexit__"):
                await transport.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"Transport cleanup error: {e}")

    def disconnect_all(self) -> None:
        """断开所有 MCP 服务器连接。"""
        for name in list(self._connections.keys()):
            self.disconnect(name)

    async def discover_tools(self, server_name: str | None = None) -> list[dict[str, Any]]:
        """
        发现 MCP 服务器上的工具。

        参数:
            server_name: 指定服务器名称。None 表示所有已连接的服务器。

        返回:
            工具定义列表
        """
        tools: list[dict[str, Any]] = []

        servers = [server_name] if server_name else list(self._connections.keys())

        for name in servers:
            conn = self._connections.get(name)
            if not conn:
                logger.warning(f"Server '{name}' not connected, skipping")
                continue

            session = conn["session"]
            try:
                result = await session.list_tools()

                for tool in result.tools:
                    tool_def = {
                        "server": name,
                        "name": f"{name}_{tool.name}",
                        "original_name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema or {},
                    }
                    tools.append(tool_def)

                    # 缓存工具定义
                    self._discovered_tools[f"{name}_{tool.name}"] = tool_def

                logger.info(f"Discovered {len(result.tools)} tools from '{name}'")

            except Exception as e:
                logger.error(f"Failed to discover tools from '{name}': {e}")

        return tools

    def register_tools(
        self,
        registry: ToolRegistry,
        server_name: str | None = None,
    ) -> int:
        """
        将发现的 MCP 工具注册到 ToolRegistry。

        参数:
            registry: 工具注册表
            server_name: 指定服务器名称。None 表示所有已发现的工具。

        返回:
            注册的工具数量
        """
        count = 0

        for tool_name, tool_def in self._discovered_tools.items():
            if server_name and tool_def["server"] != server_name:
                continue

            # 创建工具处理器（代理调用到 MCP 服务器）
            server = tool_def["server"]
            original_name = tool_def["original_name"]

            def make_handler(srv, orig_name):
                def handler(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
                    return self.call_tool_sync(srv, orig_name, arguments)
                return handler

            registry.register(
                handler=make_handler(server, original_name),
                name=tool_name,
                description=tool_def["description"],
                parameters=tool_def["input_schema"],
                permission_level=PermissionLevel.REQUIRE_CONFIRM,
            )
            count += 1

        logger.info(f"Registered {count} MCP tools to ToolRegistry")
        return count

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """异步调用 MCP 工具。"""
        conn = self._connections.get(server_name)
        if not conn:
            return {"success": False, "error": f"Server '{server_name}' not connected"}

        session = conn["session"]
        try:
            result = await session.call_tool(tool_name, arguments)
            return {
                "success": True,
                "content": str(result.content) if result.content else "",
                "metadata": {"is_error": result.isError if hasattr(result, "isError") else False},
            }
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return {"success": False, "error": str(e)}

    def call_tool_sync(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        同步调用 MCP 工具。

        在运行中的事件循环中使用 asyncio.run_coroutine_threadsafe，
        在无事件循环时使用 asyncio.run。
        """
        conn = self._connections.get(server_name)
        if not conn:
            return {"success": False, "error": f"Server '{server_name}' not connected"}

        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在运行中的事件循环中，使用线程安全调度
                import concurrent.futures
                import threading

                result_container: dict[str, Any] = {}
                done_event = threading.Event()

                def run_in_new_thread():
                    try:
                        new_loop = asyncio.new_event_loop()
                        result_container["result"] = new_loop.run_until_complete(
                            self.call_tool(server_name, tool_name, arguments)
                        )
                        new_loop.close()
                    except Exception as e:
                        result_container["error"] = str(e)
                    finally:
                        done_event.set()

                t = threading.Thread(target=run_in_new_thread)
                t.start()
                done_event.wait(timeout=60)

                if "error" in result_container:
                    return {"success": False, "error": result_container["error"]}
                return result_container.get("result", {"success": False, "error": "Unknown error"})
            else:
                return loop.run_until_complete(
                    self.call_tool(server_name, tool_name, arguments)
                )
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self.call_tool(server_name, tool_name, arguments))
