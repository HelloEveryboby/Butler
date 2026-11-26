"""能力注册表 — 与技能系统解耦的核心能力声明。

设计分工：
  - ``skills/``：可插拔、可热加载、第三方可提供的扩展能力（One Folder = One Skill）
  - ``butler/core/capabilities``：Butler 自带的核心生产力能力（朗读/扫描/版本/命令/插件）

核心能力直接调度 ``butler/core`` 服务，不经过 ``SkillManager``，也不占用技能目录；
CLI、TUI、Web、REST 与 AI 工具都从本注册表取同一份声明。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilitySpec:
    """一个核心能力的声明。

    actions: ``{动作名: 说明}``，同时用于生成工具 schema 的 enum。
    properties: 除 ``action`` 外的参数 JSON Schema 属性。
    handler: ``(action, payload) -> Any``，返回可 JSON 序列化的结果。
    """

    name: str
    title: str
    description: str
    actions: dict[str, str]
    handler: Callable[[str, dict[str, Any]], Any]
    properties: dict[str, Any] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    risk: str = "low"
    tags: tuple[str, ...] = ()

    def tool_schema(self) -> dict[str, Any]:
        """导出 OpenAI Function Calling 的 function 段。"""
        action_desc = "；".join(f"{key}: {value}" for key, value in self.actions.items())
        properties: dict[str, Any] = {
            "action": {
                "type": "string",
                "enum": list(self.actions),
                "description": action_desc,
            }
        }
        properties.update(self.properties)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": ["action", *self.required],
                },
            },
        }

    def describe(self) -> str:
        lines = [f"- {self.name}（{self.title}）：{self.description}"]
        lines.extend(f"  · {key}：{value}" for key, value in self.actions.items())
        return "\n".join(lines)


class CapabilityRegistry:
    """核心能力注册表（单例）。"""

    def __init__(self) -> None:
        self._items: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> CapabilitySpec:
        if spec.name in self._items:
            raise ValueError(f"能力已注册: {spec.name}")
        self._items[spec.name] = spec
        return spec

    def get(self, name: str) -> CapabilitySpec | None:
        return self._items.get(name)

    def all(self) -> list[CapabilitySpec]:
        return list(self._items.values())

    def names(self) -> list[str]:
        return list(self._items)

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [spec.tool_schema() for spec in self._items.values()]

    def describe(self) -> str:
        return "\n".join(spec.describe() for spec in self._items.values())

    def prompt_section(self) -> str:
        """生成注入 system prompt 的"功能名单"，供模型自由选择。"""
        if not self._items:
            return ""
        lines = [
            "### ⚙️ Butler 核心能力（内置，直接调用，无需安装）",
            "以下是 Butler 自带的一等功能；请优先使用同名工具，技能库仅用于扩展能力。",
        ]
        lines.extend(spec.describe() for spec in self._items.values())
        return "\n".join(lines)

    def execute(self, name: str, action: str, payload: dict[str, Any] | None = None) -> Any:
        """执行能力动作；异常统一转换为 ``{"error": ...}``，避免打断调用方。"""
        spec = self._items.get(name)
        if spec is None:
            raise KeyError(f"未注册的能力: {name}")
        try:
            return spec.handler(str(action), dict(payload or {}))
        except Exception as exc:  # noqa: BLE001 - 边界统一兜底
            return {"error": str(exc), "capability": name, "action": action}


capability_registry = CapabilityRegistry()
