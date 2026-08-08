# -*- coding: utf-8 -*-
"""
ToolBridge — 技能与工具注册表的桥接层。

让技能在执行时能够访问内置工具 (read, write, edit, bash 等)，
也让 CLI/TUI 能够直接列出和调用工具。

使用方式 (在技能的 Python 代码中)::

    from butler.core.tool_bridge import get_tools

    def handle_request(input_text, **kwargs):
        tools = get_tools()
        content = tools.read(path="some_file.py")
        tools.edit(path="config.yaml", old_string="old", new_string="new")
        result = tools.bash(command="ls -la")
        return {"content": f"Done: {result}"}
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent_runtime.tool_registry import ToolRegistry, PermissionLevel
from .agent_runtime.builtin_tools import register_builtin_tools

logger = logging.getLogger("ToolBridge")

_default_registry: Optional[ToolRegistry] = None
_default_workspace: Optional[Path] = None


def _ensure_workspace() -> Path:
    global _default_workspace
    if _default_workspace is None:
        _default_workspace = Path.cwd().resolve()
    return _default_workspace


def get_registry() -> ToolRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        register_builtin_tools(_default_registry, str(_ensure_workspace()))
    return _default_registry


def reset_registry() -> None:
    global _default_registry, _default_workspace
    _default_registry = None
    _default_workspace = None


def set_workspace(path: str | Path) -> None:
    global _default_workspace, _default_registry
    _default_workspace = Path(path).resolve()
    _default_registry = None


class ToolContext:
    """
    工具调用上下文。提供便捷方法让技能调用工具。

    用法::

        tools = ToolContext()
        tools.read(path="file.py")
        tools.bash(command="ls")
    """

    def __init__(self, workspace: str | Path | None = None):
        self._registry = get_registry()
        if workspace:
            set_workspace(workspace)
            self._registry = get_registry()

    def __getattr__(self, name: str):
        executor = self._registry.get(name)
        if executor is None:
            raise AttributeError(f"Tool '{name}' not found. Available: {self._registry.list_names()}")

        def _call(**kwargs) -> Dict[str, Any]:
            result = executor.execute(arguments=kwargs)
            return {
                "success": result.success,
                "content": result.content,
                "error": result.error,
                "metadata": result.metadata or {},
            }
        return _call

    def list(self) -> List[str]:
        return self._registry.list_names()

    def info(self, name: str) -> Optional[Dict[str, Any]]:
        executor = self._registry.get(name)
        if executor is None:
            return None
        d = executor.definition
        return {
            "name": d.name,
            "description": d.description,
            "parameters_schema": d.parameters_schema,
            "permission_level": d.permission_level.value if hasattr(d.permission_level, 'value') else str(d.permission_level),
            "is_read_only": d.is_read_only,
            "is_destructive": d.is_destructive,
            "is_concurrency_safe": d.is_concurrency_safe,
        }

    def execute(self, name: str, **arguments) -> Dict[str, Any]:
        executor = self._registry.get(name)
        if executor is None:
            return {"success": False, "error": f"Tool '{name}' not found"}
        result = executor.execute(arguments=arguments)
        return {
            "success": result.success,
            "content": result.content,
            "error": result.error,
            "metadata": result.metadata or {},
        }


def get_tools() -> ToolContext:
    return ToolContext()


def list_tools() -> List[Dict[str, Any]]:
    registry = get_registry()
    tools = []
    for name in registry.list_names():
        info = registry.get(name)
        if info:
            d = info.definition
            tools.append({
                "name": d.name,
                "description": d.description,
                "parameters_schema": d.parameters_schema,
                "permission_level": d.permission_level.value if hasattr(d.permission_level, 'value') else str(d.permission_level),
                "is_read_only": d.is_read_only,
                "is_destructive": d.is_destructive,
            })
    return tools


def execute_tool(name: str, **arguments) -> Dict[str, Any]:
    return ToolContext().execute(name, **arguments)


def get_skill_tools(skill_meta: Dict[str, Any]) -> List[str]:
    """
    获取技能声明需要的工具列表。

    从 manifest.json 的 tools 字段读取。
    """
    return skill_meta.get("tools", [])


def create_skill_tools_context(skill_meta: Dict[str, Any]) -> ToolContext:
    """
    为技能创建限定的工具上下文。

    如果技能声明了 tools 字段，则只暴露声明的工具。
    如果未声明，则暴露所有工具 (向后兼容)。
    """
    allowed = set(get_skill_tools(skill_meta))
    ctx = ToolContext()

    if not allowed:
        return ctx

    original_registry = ctx._registry

    class FilteredToolContext(ToolContext):
        def __init__(self, registry, allowed_tools):
            self._registry = registry
            self._allowed = allowed_tools

        def __getattr__(self, name):
            if name not in self._allowed:
                raise AttributeError(
                    f"Tool '{name}' not declared for this skill. "
                    f"Allowed: {sorted(self._allowed)}"
                )
            return super().__getattr__(name)

        def list(self):
            return [n for n in self._registry.list_names() if n in self._allowed]

        def info(self, name):
            if name not in self._allowed:
                return None
            return super().info(name)

        def execute(self, name, **arguments):
            if name not in self._allowed:
                return {"success": False, "error": f"Tool '{name}' not allowed for this skill"}
            return super().execute(name, **arguments)

    return FilteredToolContext(original_registry, allowed)
