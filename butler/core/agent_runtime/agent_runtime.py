"""
AgentRuntime — 与 UI 解耦的纯 Agent 循环。

参考架构：
    - Claude Code: LLM + 循环 + 工具的极简模式
        while True:
            response = callClaude(system_prompt, messages, tools)
            if stop_reason == "end_turn": return
            if stop_reason == "tool_use": executeToolCalls(response)

    - OpenHands V1: 无状态 Agent，操作 Conversation 对象
        接收消息 → 加入上下文 → 咨询 LLM → 若返回工具调用则验证执行
        → 若返回观察则加入上下文继续循环 → 若返回响应则完成

核心特性：
    1. 与 UI 完全解耦：通过事件流和回调通知，不直接调用 UI 方法
    2. 可序列化：ConversationState 可保存/恢复
    3. 可测试：不依赖外部服务即可测试循环逻辑
    4. 支持 headless：不初始化 GUI/语音
    5. 工具执行超时：防止工具卡死阻塞循环
    6. 错误恢复：工具失败时将错误信息反馈给 LLM 重试
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .context_manager import ContextManager
from .event_stream import EventStream
from .permission import PermissionDecision, PermissionSystem
from .tool_registry import ToolRegistry
from .types import (
    ConversationState,
    Event,
    EventType,
    Message,
    PermissionLevel,
    StopReason,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """
    Agent 运行时配置。

    参考 OpenHands V1 的不可变配置模型：
        所有配置在构造时验证，运行时不可变。
    """

    max_turns: int = 50
    """最大循环轮次（参考 Claude Code 默认 50）。"""

    system_prompt: str = ""
    """系统提示词。"""

    context_token_limit: int = 120000
    """上下文 token 限制（接近时触发自动压缩）。"""

    compaction_threshold: float = 0.8
    """触发自动压缩的 token 占比阈值。"""

    tool_execution_timeout: int = 120
    """工具执行超时（秒，参考 Claude Code 默认 120）。"""

    enable_streaming_tools: bool = False
    """是否启用流式工具执行（预留功能，当前未实现并行工具执行）。"""

    enable_self_healing: bool = True
    """是否启用自愈（工具失败时触发自愈分析）。"""

    auto_confirm_handler: Callable[[str, dict[str, Any]], bool] | None = None
    """权限确认回调。返回 True 表示允许，False 表示拒绝。"""

    llm_call_handler: Callable[..., dict[str, Any]] | None = None
    """
    LLM 调用回调。

    签名: (messages: list[dict], tools: list[dict], **kwargs) -> dict
    返回: {"content": str, "tool_calls": list[dict], "stop_reason": str}
    """


class AgentRuntime:
    """
    纯 Agent 运行时循环。

    从 Jarvis._autonomous_agent_loop 抽取，与 UI/语音/硬件完全解耦。

    生命周期：
        1. 初始化 ConversationState + EventStream + ToolRegistry
        2. 接收用户输入 → 加入对话
        3. 循环：
            a. 上下文压缩检查
            b. 调用 LLM（带工具 schema）
            c. 如果 LLM 返回工具调用：
                - 权限检查
                - 执行工具
                - 结果加入对话
                - 继续循环
            d. 如果 LLM 返回最终回复：
                - 加入对话
                - 终止循环
        4. 返回最终回复

    使用方式::

        registry = ToolRegistry()
        # ... 注册工具 ...
        perm = PermissionSystem()
        ctx = ContextManager()
        stream = EventStream()

        runtime = AgentRuntime(
            config=AgentConfig(
                llm_call_handler=my_llm_call,
                system_prompt="You are a helpful assistant.",
            ),
            tool_registry=registry,
            permission_system=perm,
            context_manager=ctx,
            event_stream=stream,
        )

        result = runtime.run("Create a file called hello.py")
    """

    def __init__(
        self,
        config: AgentConfig,
        tool_registry: ToolRegistry,
        permission_system: PermissionSystem,
        context_manager: ContextManager,
        event_stream: EventStream,
    ):
        self.config = config
        self.tools = tool_registry
        self.permissions = permission_system
        self.context = context_manager
        self.events = event_stream
        self._state: ConversationState | None = None

    @property
    def state(self) -> ConversationState | None:
        return self._state

    def run(
        self,
        user_input: str,
        initial_messages: list[Message] | None = None,
        **llm_kwargs: Any,
    ) -> dict[str, Any]:
        """
        运行 Agent 循环。

        参数:
            user_input: 用户输入文本
            initial_messages: 初始对话历史（可选）
            **llm_kwargs: 传递给 LLM 调用的额外参数

        返回:
            dict: {
                "response": 最终回复文本,
                "stop_reason": 终止原因,
                "turns": 实际执行轮次,
                "events": 事件流,
            }
        """
        # 初始化对话状态
        self._state = ConversationState(messages=initial_messages)

        # 添加系统提示
        if self.config.system_prompt:
            self._state.append(Message(role="system", content=self.config.system_prompt))

        # 添加用户输入
        user_msg = Message(role="user", content=user_input)
        self._state.append(user_msg)
        self.events.emit(
            Event.create(EventType.MESSAGE, role="user", content=user_input)
        )

        stop_reason = StopReason.END_TURN
        turn = 0

        for turn in range(self.config.max_turns):
            # 1. 上下文压缩检查
            self._check_compaction()

            # 2. 调用 LLM
            try:
                llm_response = self._call_llm(**llm_kwargs)
            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                self.events.emit(
                    Event.create(EventType.ERROR, error=str(e))
                )
                stop_reason = StopReason.ERROR
                break

            # 3. 处理 LLM 响应
            content = llm_response.get("content", "")
            tool_calls_raw = llm_response.get("tool_calls", [])
            stop_reason_str = llm_response.get("stop_reason", "end_turn")

            # 解析工具调用
            tool_calls = []
            for tc_raw in tool_calls_raw:
                try:
                    tool_calls.append(ToolCall.from_dict(tc_raw))
                except Exception as e:
                    logger.warning(f"Failed to parse tool call: {e}")

            # 4. 追加 assistant 消息
            assistant_msg = Message(
                role="assistant",
                content=content,
                tool_calls=tool_calls,
            )
            self._state.append(assistant_msg)
            self.events.emit(
                Event.create(
                    EventType.MESSAGE,
                    role="assistant",
                    content=content,
                    tool_calls=[tc.to_dict() for tc in tool_calls],
                )
            )

            # 5. 如果没有工具调用，循环结束
            if not tool_calls or stop_reason_str == "end_turn":
                stop_reason = StopReason.END_TURN
                break

            # 6. 执行工具调用
            for tc in tool_calls:
                result = self._execute_tool_call(tc)
                self._state.append(result.to_message())
                self.events.emit(
                    Event.create(
                        EventType.TOOL_RESULT if result.success else EventType.TOOL_ERROR,
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        content=result.content,
                        success=result.success,
                        error=result.error,
                    )
                )

                # 7. 自愈逻辑（如果启用且工具失败）
                if (
                    not result.success
                    and self.config.enable_self_healing
                    and turn < self.config.max_turns - 1
                ):
                    # 将错误信息加入对话，让 LLM 在下一轮决定如何处理
                    self._state.append(
                        Message(
                            role="user",
                            content=(
                                f"Tool '{tc.name}' failed with error: {result.error}. "
                                f"Please try a different approach or fix the issue."
                            ),
                        )
                    )

            # 继续下一轮循环

        else:
            # 到达最大轮次
            stop_reason = StopReason.MAX_TURNS

        # 发出停止事件
        self.events.emit(
            Event.create(EventType.STOP, reason=stop_reason.value, turns=turn + 1)
        )

        # 获取最终回复
        final_response = self._get_final_response()

        return {
            "response": final_response,
            "stop_reason": stop_reason.value,
            "turns": turn + 1,
            "events": self.events.events,
        }

    def _call_llm(self, **kwargs: Any) -> dict[str, Any]:
        """
        调用 LLM。

        使用 config.llm_call_handler 回调，如果不支持 tool calling
        则降级为意图抽取模式。
        """
        if self.config.llm_call_handler:
            messages = [m.to_dict() for m in self._state.messages]
            tools = self.tools.get_schemas()
            return self.config.llm_call_handler(
                messages=messages,
                tools=tools,
                **kwargs,
            )

        # 降级：无 LLM 调用器时返回空响应
        logger.warning("No LLM call handler configured, returning empty response")
        return {"content": "", "tool_calls": [], "stop_reason": "end_turn"}

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        执行单个工具调用。

        流程：
            1. 查找工具定义
            2. 权限检查
            3. 执行工具
            4. 返回结果
        """
        executor = self.tools.get(tool_call.name)
        if not executor:
            return ToolResult(
                tool_call_id=tool_call.id,
                content="",
                success=False,
                error=f"Tool '{tool_call.name}' not found",
            )

        # 发出工具调用事件
        self.events.emit(
            Event.create(
                EventType.TOOL_CALL,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
            )
        )

        # 权限检查
        decision = self.permissions.check(
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
            tool_permission_level=executor.definition.permission_level,
        )

        if decision == PermissionDecision.DENY:
            self.events.emit(
                Event.create(
                    EventType.PERMISSION_RESPONSE,
                    tool_call_id=tool_call.id,
                    decision="deny",
                )
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content="",
                success=False,
                error=f"Permission denied for tool '{tool_call.name}'",
            )

        if decision == PermissionDecision.ASK:
            self.events.emit(
                Event.create(
                    EventType.PERMISSION_REQUEST,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                )
            )

            # 调用确认回调
            if self.config.auto_confirm_handler:
                approved = self.config.auto_confirm_handler(
                    tool_call.name, tool_call.arguments
                )
            else:
                approved = False  # 默认拒绝

            if not approved:
                self.events.emit(
                    Event.create(
                        EventType.PERMISSION_RESPONSE,
                        tool_call_id=tool_call.id,
                        decision="user_denied",
                    )
                )
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content="",
                    success=False,
                    error=f"User denied permission for tool '{tool_call.name}'",
                )

            self.events.emit(
                Event.create(
                    EventType.PERMISSION_RESPONSE,
                    tool_call_id=tool_call.id,
                    decision="user_approved",
                )
            )

        # 执行工具（带超时保护）
        import concurrent.futures

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.tools.execute,
                    tool_call.name,
                    tool_call.arguments,
                )
                result = future.result(timeout=self.config.tool_execution_timeout)
        except concurrent.futures.TimeoutExpired:
            logger.error(
                f"Tool '{tool_call.name}' timed out after "
                f"{self.config.tool_execution_timeout}s"
            )
            self.events.emit(
                Event.create(
                    EventType.TOOL_ERROR,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    error=f"Tool execution timed out after {self.config.tool_execution_timeout}s",
                )
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content="",
                success=False,
                error=f"Tool execution timed out after {self.config.tool_execution_timeout}s",
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return ToolResult(
                tool_call_id=tool_call.id,
                content="",
                success=False,
                error=f"Tool execution error: {e}",
            )

        # 设置 tool_call_id
        return ToolResult(
            tool_call_id=tool_call.id,
            content=result.content,
            success=result.success,
            error=result.error,
            metadata=result.metadata,
        )

    def _check_compaction(self) -> None:
        """检查是否需要上下文压缩。"""
        if not self._state:
            return

        estimated = self._state.estimate_tokens()
        threshold = int(self.config.context_token_limit * self.config.compaction_threshold)

        if estimated > threshold:
            logger.info(
                f"Context approaching limit ({estimated} > {threshold} tokens), "
                f"triggering autocompaction"
            )
            self.events.emit(
                Event.create(
                    EventType.COMPACTION,
                    stage="autocompaction",
                    estimated_tokens=estimated,
                    threshold=threshold,
                )
            )
            self.context.compact(self._state)

    def _get_final_response(self) -> str:
        """从对话状态中提取最终回复。"""
        if not self._state:
            return ""

        # 找最后一条 assistant 消息
        for msg in reversed(self._state.messages):
            if msg.role == "assistant" and msg.content:
                return msg.content

        return ""

    def save_state(self, path: str) -> None:
        """保存对话状态到文件。"""
        import json

        if not self._state:
            return

        data = self._state.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_state(self, path: str) -> None:
        """从文件恢复对话状态。"""
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self._state = ConversationState.from_dict(data)
