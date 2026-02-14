from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, fields, replace
from typing import Any

class BaseTool(metaclass=ABCMeta):
    """工具的基类。"""

    @abstractmethod
    def __call__(self, **kwargs) -> Any:
        """使用给定参数执行工具。"""
        ...

@dataclass(kw_only=True, frozen=True)
class ToolResult:
    """表示工具执行的结果。"""

    output: str | None = None
    error: str | None = None
    base64_image: str | None = None
    system: str | None = None

    def __bool__(self):
        return any(getattr(self, field.name) for field in fields(self))

    def __add__(self, other: "ToolResult"):
        def combine_fields(
            field: str | None, other_field: str | None, concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
        )

    def replace(self, **kwargs):
        """返回一个新的 ToolResult，其中给定的字段已被替换。"""
        return replace(self, **kwargs)


class CLIResult(ToolResult):
    """可以渲染为 CLI 输出的 ToolResult。"""


class ToolFailure(ToolResult):
    """表示失败的 ToolResult。"""


class ToolError(Exception):
    """当工具遇到错误时抛出。"""

    def __init__(self, message):
        self.message = message
