"""
工具注册表 — JSON Schema 驱动的标准化工具注册系统。

参考架构：
    - OpenHands ToolExecutor: 分离工具定义和执行，Pydantic 模型自动生成 JSON Schema
    - Claude Code buildTool(): 标准契约（输入/输出 Schema + 权限检查 + 元数据标志）

每个工具注册时声明：
    1. JSON Schema 参数定义（供 LLM 自主选择工具）
    2. 权限层级（always_allow / require_confirm / never_allow）
    3. 元数据标志（is_read_only / is_destructive / is_concurrency_safe）
    4. 执行函数（接收参数字典，返回 ToolResult）
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .types import PermissionLevel, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    工具执行器。

    封装单个工具的执行逻辑，包括：
        - 参数验证
        - 执行计时
        - 错误捕获
        - 结果包装

    参考 OpenHands 的 ToolExecutor 模式：分离工具定义和执行。
    """

    def __init__(
        self,
        definition: ToolDefinition,
        handler: Callable[..., dict[str, Any]],
    ):
        self.definition = definition
        self._handler = handler

    @property
    def name(self) -> str:
        return self.definition.name

    def execute(self, arguments: dict[str, Any], **context: Any) -> ToolResult:
        """
        执行工具。

        参数:
            arguments: 工具参数（已通过 JSON Schema 验证）
            **context: 执行上下文（workspace、container 等）

        返回:
            ToolResult: 工具执行结果
        """
        start = time.time()
        try:
            result = self._handler(arguments=arguments, **context)
            elapsed = (time.time() - start) * 1000

            if isinstance(result, ToolResult):
                return result

            # 包装字典结果
            if isinstance(result, dict):
                success = result.get("success", True)
                content = result.get("content") or result.get("output", "")
                error = result.get("error") if not success else None
                return ToolResult(
                    tool_call_id="",
                    content=str(content),
                    success=success,
                    error=error,
                    metadata={"elapsed_ms": elapsed, **result.get("metadata", {})},
                )

            return ToolResult(
                tool_call_id="",
                content=str(result),
                success=True,
                metadata={"elapsed_ms": elapsed},
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(
                f"Tool '{self.name}' execution failed: {e}",
                exc_info=True,
            )
            return ToolResult(
                tool_call_id="",
                content="",
                success=False,
                error=f"{type(e).__name__}: {e}",
                metadata={"elapsed_ms": elapsed},
            )

    def validate_arguments(self, arguments: dict[str, Any]) -> tuple[bool, str]:
        """
        验证参数是否符合 JSON Schema。

        简化验证：检查 required 字段是否存在。
        完整验证可集成 jsonschema 库。
        """
        schema = self.definition.parameters_schema
        required = schema.get("required", [])
        missing = [r for r in required if r not in arguments]
        if missing:
            return False, f"Missing required parameters: {missing}"
        return True, ""


class ToolRegistry:
    """
    工具注册表。

    管理所有已注册工具的定义和执行器，提供：
        - 工具注册（装饰器或方法调用）
        - 工具发现（获取 OpenAI 兼容的 schema 列表）
        - 工具执行（按名称调用，自动验证参数）
        - 权限查询

    使用方式::

        registry = ToolRegistry()

        @registry.tool(
            name="read_file",
            description="读取文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"]
            },
            permission_level=PermissionLevel.ALWAYS_ALLOW,
            is_read_only=True,
        )
        def read_file(arguments):
            path = arguments["path"]
            with open(path) as f:
                return {"content": f.read()}
    """

    def __init__(self):
        self._tools: dict[str, ToolExecutor] = {}

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        permission_level: PermissionLevel = PermissionLevel.REQUIRE_CONFIRM,
        is_read_only: bool = False,
        is_destructive: bool = False,
        is_concurrency_safe: bool = False,
    ) -> Callable:
        """
        装饰器：注册工具。

        参数:
            name: 工具名称（唯一标识符）
            description: 工具描述
            parameters: JSON Schema 格式的参数定义
            permission_level: 权限层级
            is_read_only: 是否只读操作
            is_destructive: 是否破坏性操作
            is_concurrency_safe: 是否并发安全
        """

        def decorator(func: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
            self.register(
                handler=func,
                name=name,
                description=description,
                parameters=parameters,
                permission_level=permission_level,
                is_read_only=is_read_only,
                is_destructive=is_destructive,
                is_concurrency_safe=is_concurrency_safe,
            )
            return func

        return decorator

    def register(
        self,
        handler: Callable[..., dict[str, Any]],
        name: str,
        description: str,
        parameters: dict[str, Any],
        permission_level: PermissionLevel = PermissionLevel.REQUIRE_CONFIRM,
        is_read_only: bool = False,
        is_destructive: bool = False,
        is_concurrency_safe: bool = False,
    ) -> None:
        """直接注册工具（非装饰器方式）。"""
        definition = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters,
            permission_level=permission_level,
            is_read_only=is_read_only,
            is_destructive=is_destructive,
            is_concurrency_safe=is_concurrency_safe,
        )
        executor = ToolExecutor(definition, handler)
        self._tools[name] = executor
        logger.info(
            f"Registered tool '{name}' "
            f"(permission={permission_level.value}, read_only={is_read_only})"
        )

    def unregister(self, name: str) -> bool:
        """注销工具。"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool '{name}'")
            return True
        return False

    def get(self, name: str) -> ToolExecutor | None:
        """获取工具执行器。"""
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """列出所有工具名称。"""
        return list(self._tools.keys())

    def get_schemas(self) -> list[dict[str, Any]]:
        """
        获取所有工具的 OpenAI 兼容 schema 列表。

        用于传递给 LLM 的 tools 参数。
        """
        return [executor.definition.to_openai_schema() for executor in self._tools.values()]

    def get_definitions(self) -> list[ToolDefinition]:
        """获取所有工具定义。"""
        return [executor.definition for executor in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        **context: Any,
    ) -> ToolResult:
        """
        执行指定工具。

        参数:
            name: 工具名称
            arguments: 工具参数
            **context: 执行上下文

        返回:
            ToolResult: 执行结果

        异常:
            KeyError: 工具未注册
        """
        executor = self._tools.get(name)
        if not executor:
            raise KeyError(f"Tool '{name}' not registered")

        # 参数验证
        ok, msg = executor.validate_arguments(arguments)
        if not ok:
            return ToolResult(
                tool_call_id="",
                content="",
                success=False,
                error=f"Parameter validation failed: {msg}",
            )

        return executor.execute(arguments, **context)

    def get_read_only_tools(self) -> list[str]:
        """获取所有只读工具名称（可并行执行）。"""
        return [
            name
            for name, executor in self._tools.items()
            if executor.definition.is_read_only
        ]

    def get_concurrency_safe_tools(self) -> list[str]:
        """获取所有并发安全工具名称。"""
        return [
            name
            for name, executor in self._tools.items()
            if executor.definition.is_concurrency_safe
        ]
