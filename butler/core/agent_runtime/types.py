"""
Agent Runtime 核心类型定义。

所有类型均为不可变 dataclass（或 Pydantic 模型），遵循 OpenHands V1 的
"默认无状态，单一状态源" 原则。唯一可变实体是 ConversationState。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """事件流中的事件类型。"""

    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_RESPONSE = "permission_response"
    COMPACTION = "compaction"
    SUBAGENT_SPAWN = "subagent_spawn"
    SUBAGENT_RETURN = "subagent_return"
    ERROR = "error"
    STOP = "stop"


class PermissionLevel(str, Enum):
    """
    工具权限层级。

    参考 Claude Code 的三层权限模型：
        - ALWAYS_ALLOW: 只读操作，安全静默执行
        - REQUIRE_CONFIRM: 状态修改操作，执行前弹出权限提示
        - NEVER_ALLOW: 危险操作，无论设置如何都阻止
    """

    ALWAYS_ALLOW = "always_allow"
    REQUIRE_CONFIRM = "require_confirm"
    NEVER_ALLOW = "never_allow"


class StopReason(str, Enum):
    """Agent 循环终止原因。"""

    END_TURN = "end_turn"
    MAX_TURNS = "max_turns"
    ERROR = "error"
    USER_INTERRUPT = "user_interrupt"
    PERMISSION_DENIED = "permission_denied"


@dataclass(frozen=True)
class Message:
    """
    对话消息（不可变）。

    与 OpenAI/Claude 消息格式兼容：
        role: "system" | "user" | "assistant" | "tool"
        content: 消息文本
        tool_calls: assistant 消息中的工具调用列表
        tool_call_id: tool 消息对应的工具调用 ID
        metadata: 附加元数据（时间戳、来源等）
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI 兼容的字典格式。"""
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        """从字典创建消息。"""
        tool_calls = [ToolCall.from_dict(tc) for tc in d.get("tool_calls", [])]
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=tool_calls,
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
            metadata=d.get("metadata", {}),
        )


@dataclass(frozen=True)
class ToolCall:
    """工具调用请求（不可变）。"""

    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": _json_dumps(self.arguments),
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ToolCall:
        return cls(
            id=d["id"],
            name=d["function"]["name"],
            arguments=_json_loads(d["function"]["arguments"]),
        )


@dataclass(frozen=True)
class ToolResult:
    """工具执行结果（不可变）。"""

    tool_call_id: str
    content: str
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> Message:
        """转换为 tool 角色消息。"""
        return Message(
            role="tool",
            content=self.content,
            tool_call_id=self.tool_call_id,
            metadata=self.metadata,
        )


@dataclass(frozen=True)
class Event:
    """
    事件流中的事件（不可变）。

    所有 agent 行为都通过事件记录，支持确定性重放。
    参考 OpenHands 的事件溯源架构。
    """

    id: str
    type: EventType
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def create(cls, event_type: EventType, **data) -> Event:
        return cls(
            id=str(uuid.uuid4()),
            type=event_type,
            data=data,
        )


class ToolDefinition(BaseModel):
    """
    工具定义（JSON Schema 驱动）。

    参考 OpenHands 的 Action/Observation 模式和 Claude Code 的 buildTool() 契约。
    每个工具通过 Pydantic 模型自动生成 JSON Schema 供 LLM 工具调用。
    """

    name: str = Field(description="工具名称（唯一标识符）")
    description: str = Field(description="工具描述，供 LLM 理解何时使用")
    parameters_schema: dict[str, Any] = Field(
        description="JSON Schema 格式的参数定义"
    )
    permission_level: PermissionLevel = Field(
        default=PermissionLevel.REQUIRE_CONFIRM,
        description="工具权限层级",
    )
    is_read_only: bool = Field(default=False, description="是否只读操作")
    is_destructive: bool = Field(default=False, description="是否破坏性操作")
    is_concurrency_safe: bool = Field(
        default=False, description="是否并发安全（只读工具通常为 True）"
    )

    def to_openai_schema(self) -> dict[str, Any]:
        """转换为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class ConversationState:
    """
    对话状态（唯一可变实体）。

    参考 OpenHands V1 的 Conversation 组件：
        - 管理整个对话生命周期和状态
        - 支持序列化/反序列化（保存到磁盘/数据库并恢复）
        - 支持 undo/redo、时间旅行调试

    设计为可变但受控的容器，所有修改通过 append_message 等方法进行，
    自动记录到 EventStream。
    """

    def __init__(self, messages: list[Message] | None = None):
        self._messages: list[Message] = list(messages) if messages else []
        self._turn_count: int = 0
        self._compaction_count: int = 0
        self._created_at: float = time.time()

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def compaction_count(self) -> int:
        return self._compaction_count

    @property
    def created_at(self) -> float:
        return self._created_at

    def append(self, message: Message) -> None:
        """追加消息到对话。"""
        self._messages.append(message)
        if message.role == "assistant":
            self._turn_count += 1

    def extend(self, messages: list[Message]) -> None:
        """批量追加消息。"""
        for m in messages:
            self.append(m)

    def replace_messages(self, messages: list[Message]) -> None:
        """
        替换所有消息（用于压缩后恢复）。

        记录压缩次数，用于追踪上下文管理历史。
        """
        self._messages = list(messages)
        self._compaction_count += 1

    def get_user_messages(self) -> list[Message]:
        """获取所有用户消息。"""
        return [m for m in self._messages if m.role == "user"]

    def get_last_user_message(self) -> Message | None:
        """获取最后一条用户消息。"""
        for m in reversed(self._messages):
            if m.role == "user":
                return m
        return None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（可保存到磁盘）。"""
        return {
            "messages": [m.to_dict() for m in self._messages],
            "turn_count": self._turn_count,
            "compaction_count": self._compaction_count,
            "created_at": self._created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ConversationState:
        """从字典反序列化。"""
        state = cls.__new__(cls)
        state._messages = [Message.from_dict(m) for m in d.get("messages", [])]
        state._turn_count = d.get("turn_count", 0)
        state._compaction_count = d.get("compaction_count", 0)
        state._created_at = d.get("created_at", time.time())
        return state

    def estimate_tokens(self) -> int:
        """
        粗略估算当前对话的 token 数量。

        使用 4 字符 ≈ 1 token 的近似值。
        """
        total_chars = sum(len(m.content) for m in self._messages)
        return total_chars // 4


def _json_dumps(obj: Any) -> str:
    """安全 JSON 序列化。"""
    import json

    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(obj)


def _json_loads(s: str) -> dict[str, Any]:
    """安全 JSON 反序列化。"""
    import json

    try:
        return json.loads(s) if isinstance(s, str) else dict(s)
    except (json.JSONDecodeError, TypeError):
        return {}
