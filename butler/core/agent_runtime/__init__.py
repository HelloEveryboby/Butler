"""
Butler Agent Runtime — 与 UI 解耦的纯 Agent 运行时。

灵感来源：OpenHands V1 SDK（无状态 Agent + 不可变 Conversation）和
Claude Code（LLM + 循环 + 工具极简模式）。

核心组件：
    - AgentRuntime: 纯 Agent 循环，接收 messages + tools，输出 events
    - ToolRegistry: JSON Schema 驱动的标准化工具注册
    - PermissionSystem: 三层权限 + glob 模式匹配
    - ContextManager: 四阶段上下文压缩管道
    - SubagentManager: 隔离上下文子代理委托
    - EventStream: 追加式事件日志 + 确定性重放
    - MCPClient: MCP 工具服务器集成
    - DockerSandbox: 容器级隔离执行环境
    - JarvisAgentBridge: 旧版 Jarvis 到新架构的适配层
"""

from .types import (
    Message,
    ToolCall,
    ToolResult,
    Event,
    EventType,
    ConversationState,
    ToolDefinition,
    PermissionLevel,
    StopReason,
)
from .tool_registry import ToolRegistry, ToolExecutor
from .permission import (
    PermissionSystem,
    PermissionDecision,
    PermissionMode,
    PermissionConfig,
    PermissionRule,
)
from .agent_runtime import AgentRuntime, AgentConfig
from .context_manager import ContextManager, CompactionStage
from .event_stream import EventStream
from .condenser import Condenser, BudgetCondenser, ImportanceScorer

try:
    from .subagent_manager import SubagentManager, SubagentDefinition
except ImportError:
    SubagentManager = None  # type: ignore
    SubagentDefinition = None  # type: ignore

try:
    from .mcp_client import MCPClient, MCPServerConfig
except ImportError:
    MCPClient = None  # type: ignore
    MCPServerConfig = None  # type: ignore

try:
    from .docker_sandbox import DockerSandbox
except ImportError:
    DockerSandbox = None  # type: ignore

try:
    from .jarvis_adapter import JarvisAgentBridge
except ImportError:
    JarvisAgentBridge = None  # type: ignore

__all__ = [
    # Types
    "Message",
    "ToolCall",
    "ToolResult",
    "Event",
    "EventType",
    "ConversationState",
    "ToolDefinition",
    "PermissionLevel",
    "StopReason",
    # Core
    "AgentRuntime",
    "AgentConfig",
    "ToolRegistry",
    "ToolExecutor",
    "PermissionSystem",
    "PermissionDecision",
    "PermissionMode",
    "PermissionConfig",
    "PermissionRule",
    "ContextManager",
    "CompactionStage",
    "SubagentManager",
    "SubagentDefinition",
    "EventStream",
    "Condenser",
    "BudgetCondenser",
    "ImportanceScorer",
    # Optional
    "MCPClient",
    "MCPServerConfig",
    "DockerSandbox",
    "JarvisAgentBridge",
]
