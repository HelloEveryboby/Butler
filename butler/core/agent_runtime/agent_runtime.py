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

import concurrent.futures
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .context_manager import CompactionStage, ContextManager
from .event_stream import EventStream
from .permission import PermissionDecision, PermissionSystem
from .tool_registry import ToolExecutor, ToolRegistry
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

# 上下文超限的常见报错特征（不同提供商的措辞不一样）
_CONTEXT_ERROR_MARKERS = (
    "context length",
    "context_length",
    "maximum context",
    "prompt is too long",
    "prompt too long",
    "too many tokens",
    "reduce the length",
    "request too large",
)


@dataclass
class AgentConfig:
    """
    Agent 运行时配置。

    参考 OpenHands V1 的不可变配置模型：
        所有配置在构造时验证，运行时不可变。
    """

    max_turns: int = 50
    """最大循环轮次（参考 Claude Code 默认 50）。"""

    max_parallel_tools: int = 4
    """同一轮内并发安全工具的最大并行度（写类工具始终串行）。"""

    max_context_retries: int = 2
    """上下文超限时先压缩再重试的最大次数（REACTIVE → COLLAPSE）。"""

    checkpoint_dir: str = ""
    """断点续跑目录；为空表示不落盘（避免默认污染工作区）。"""

    system_prompt: str = ""
    """系统提示词。"""

    context_token_limit: int = 120000
    """上下文 token 限制（保留字段，实际以 ContextManager 配置为准）。"""

    compaction_threshold: float = 0.8
    """触发自动压缩的 token 占比阈值（保留字段，实际以 ContextManager 配置为准）。"""

    tool_execution_timeout: int = 120
    """工具执行超时（秒，参考 Claude Code 默认 120）。"""

    enable_streaming_tools: bool = False
    """预留：流式工具输出。并行执行由 max_parallel_tools 控制。"""

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

    从 Butler._autonomous_agent_loop 抽取，与 UI/语音/硬件完全解耦。

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
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._cancel_event = threading.Event()
        self._session_id: str | None = None

    @property
    def state(self) -> ConversationState | None:
        return self._state

    @property
    def session_id(self) -> str | None:
        """当前会话 ID（启用 checkpoint 后自动生成）。"""
        return self._session_id

    def request_cancel(self) -> None:
        """请求中断当前循环（线程安全，可从 UI 回调或信号处理器调用）。"""
        self._cancel_event.set()

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def run(
        self,
        user_input: str,
        initial_messages: list[Message] | None = None,
        session_id: str | None = None,
        resume: bool = False,
        **llm_kwargs: Any,
    ) -> dict[str, Any]:
        """
        运行 Agent 循环。

        参数:
            user_input: 用户输入文本
            initial_messages: 初始对话历史（可选）
            session_id: 会话 ID；配合 checkpoint_dir 自动落盘
            resume: 从最近一次 checkpoint 恢复后继续
            **llm_kwargs: 传递给 LLM 调用的额外参数

        返回:
            dict: {
                "response": 最终回复文本,
                "stop_reason": 终止原因,
                "turns": 实际执行轮次,
                "session_id": 会话 ID（未启用 checkpoint 时为 None）,
                "events": 事件流,
            }
        """
        self._cancel_event.clear()
        self._state = None
        self._session_id = session_id

        resumed = bool(resume) and self._load_checkpoint(session_id)

        if self._state is None:
            self._state = ConversationState(messages=initial_messages)
            if self.config.system_prompt:
                self._state.append(
                    Message(role="system", content=self.config.system_prompt)
                )

        # 续跑时只追加新输入，避免把历史用户消息重复塞一遍
        if not resumed or user_input:
            self._state.append(Message(role="user", content=user_input))
            self.events.emit(
                Event.create(EventType.MESSAGE, role="user", content=user_input)
            )

        if self._session_id is None and self.config.checkpoint_dir:
            self._session_id = uuid.uuid4().hex[:12]

        workers = max(1, int(self.config.max_parallel_tools or 1))
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

        stop_reason = StopReason.END_TURN
        turns_used = 0

        try:
            for _turn in range(self.config.max_turns):
                if self._is_cancelled():
                    stop_reason = StopReason.USER_INTERRUPT
                    break

                self._check_compaction()

                try:
                    llm_response = self._call_llm_with_recovery(**llm_kwargs)
                except Exception as e:
                    logger.error(f"LLM call failed: {e}", exc_info=True)
                    self.events.emit(Event.create(EventType.ERROR, error=str(e)))
                    stop_reason = StopReason.ERROR
                    break

                turns_used += 1

                content = llm_response.get("content", "")
                tool_calls_raw = llm_response.get("tool_calls", [])
                stop_reason_str = llm_response.get("stop_reason", "end_turn")

                tool_calls = []
                for tc_raw in tool_calls_raw:
                    try:
                        tool_calls.append(ToolCall.from_dict(tc_raw))
                    except Exception as e:
                        logger.warning(f"Failed to parse tool call: {e}")

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
                self.events.emit(
                    Event.create(
                        EventType.TURN,
                        turn=turns_used,
                        tool_calls=len(tool_calls),
                        estimated_tokens=self._state.estimate_tokens(),
                    )
                )

                # 以「是否有工具调用」作为唯一终止依据：部分 OpenAI 兼容服务
                # 会返回 finish_reason="stop" 却仍带 tool_calls，不能据此短路。
                if not tool_calls:
                    stop_reason = self._map_stop_reason(stop_reason_str)
                    self._save_checkpoint_if_needed()
                    break

                results = self._execute_tool_calls(tool_calls)
                failures: list[tuple[str, str]] = []
                for tc, result in zip(tool_calls, results):
                    if result is None:
                        continue
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
                    if not result.success:
                        failures.append((tc.name, result.error or "unknown error"))

                # 自愈提示必须等整轮 tool 结果都回灌后再追加，否则会插入到
                # 多个 tool 消息之间，产生非法的消息序列。
                if failures and self.config.enable_self_healing:
                    detail = "；".join(f"{name}: {err}" for name, err in failures)
                    self._state.append(
                        Message(
                            role="user",
                            content=(
                                f"以下工具调用失败：{detail}。请阅读错误信息，"
                                f"换一种可行方式继续，不要重复同样的失败调用。"
                            ),
                        )
                    )

                self._save_checkpoint_if_needed()

                if self._is_cancelled():
                    stop_reason = StopReason.USER_INTERRUPT
                    break
            else:
                stop_reason = StopReason.MAX_TURNS

        finally:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None

        self.events.emit(
            Event.create(EventType.STOP, reason=stop_reason.value, turns=turns_used)
        )

        final_response = self._get_final_response()

        return {
            "response": final_response,
            "stop_reason": stop_reason.value,
            "turns": turns_used,
            "session_id": self._session_id,
            "events": self.events.events,
        }

    def _call_llm(self, **kwargs: Any) -> dict[str, Any]:
        """
        调用 LLM。

        使用 config.llm_call_handler 回调，如果不支持 tool calling
        则降级为意图抽取模式。
        """
        if self.config.llm_call_handler:
            assert self._state is not None
            messages = [m.to_dict() for m in self._state.messages]
            tools = self.tools.get_schemas()
            return self.config.llm_call_handler(
                messages=messages,
                tools=tools,
                **kwargs,
            )

        logger.warning("No LLM call handler configured, returning empty response")
        return {"content": "", "tool_calls": [], "stop_reason": "end_turn"}

    def _call_llm_with_recovery(self, **kwargs: Any) -> dict[str, Any]:
        """
        调用 LLM；遇到上下文超限时先压缩再重试。

        压缩策略与 ContextManager 的四阶段管道一致：
        第一次 REACTIVE（预算 50%），仍失败则 COLLAPSE（只留系统消息 + Context Card + 当前任务）。
        """
        retries = max(0, int(self.config.max_context_retries))
        stages = [CompactionStage.REACTIVE, CompactionStage.COLLAPSE]

        for attempt in range(retries + 1):
            try:
                response = self._call_llm(**kwargs)
                if response.get("error"):
                    raise RuntimeError(str(response["error"]))
                return response
            except Exception as e:
                if not self._is_context_error(e) or attempt >= retries:
                    raise
                stage = stages[min(attempt, len(stages) - 1)]
                logger.warning(
                    f"Context limit hit, compacting with {stage.value} and retrying"
                )
                assert self._state is not None
                result = self.context.compact(self._state, stage)
                self.events.emit(Event.create(EventType.COMPACTION, **result))

        raise RuntimeError("LLM call failed after context recovery")

    @staticmethod
    def _is_context_error(error: Any) -> bool:
        text = str(error).lower()
        return any(marker in text for marker in _CONTEXT_ERROR_MARKERS)

    @staticmethod
    def _map_stop_reason(raw: Any) -> StopReason:
        if str(raw or "").lower() in ("length", "max_tokens"):
            return StopReason.LENGTH
        return StopReason.END_TURN

    # ── 工具执行 ────────────────────────────────────────────────────

    def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """
        执行一轮内的全部工具调用。

        并发安全工具按连续批次并行执行，非安全工具（写文件、bash 等）串行；
        返回结果顺序与入参 tool_calls 一一对应，保证 tool_call_id 对齐。
        """
        results: list[ToolResult | None] = [None] * len(tool_calls)
        index = 0

        while index < len(tool_calls):
            if self._is_cancelled():
                for remaining in range(index, len(tool_calls)):
                    results[remaining] = self._cancelled_result(tool_calls[remaining])
                break

            if (
                self.config.max_parallel_tools <= 1
                or not self._is_concurrency_safe(tool_calls[index])
            ):
                results[index] = self._execute_tool_call(tool_calls[index])
                index += 1
                continue

            end = index
            while end < len(tool_calls) and self._is_concurrency_safe(tool_calls[end]):
                end += 1

            results[index:end] = self._execute_parallel(tool_calls[index:end])
            index = end

        return [
            result if result is not None else self._cancelled_result(tc)
            for result, tc in zip(results, tool_calls)
        ]

    def _is_concurrency_safe(self, tool_call: ToolCall) -> bool:
        executor = self.tools.get(tool_call.name)
        return bool(executor and executor.definition.is_concurrency_safe)

    def _execute_parallel(self, group: list[ToolCall]) -> list[ToolResult]:
        """并行执行一组并发安全工具；权限检查仍在主线程按序完成。"""
        assert self._executor is not None
        slots: list[ToolResult | None] = [None] * len(group)
        pending: list[tuple[int, ToolCall]] = []

        for i, tool_call in enumerate(group):
            executor, denial = self._authorize_tool_call(tool_call)
            if denial is not None:
                slots[i] = denial
            elif executor is not None:
                pending.append((i, tool_call))

        futures = [
            (i, tc, self._executor.submit(self.tools.execute, tc.name, tc.arguments))
            for i, tc in pending
        ]
        for i, tool_call, future in futures:
            slots[i] = self._await_tool(tool_call, future)

        return [
            slot if slot is not None else self._cancelled_result(tc)
            for slot, tc in zip(slots, group)
        ]

    @staticmethod
    def _cancelled_result(tool_call: ToolCall) -> ToolResult:
        return ToolResult(
            tool_call_id=tool_call.id,
            content="",
            success=False,
            error="Cancelled by user",
        )

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """串行执行单个工具调用。"""
        executor, denial = self._authorize_tool_call(tool_call)
        if denial is not None:
            return denial

        assert executor is not None and self._executor is not None
        future = self._executor.submit(self.tools.execute, tool_call.name, tool_call.arguments)
        return self._await_tool(tool_call, future)

    def _authorize_tool_call(
        self, tool_call: ToolCall
    ) -> tuple[ToolExecutor | None, ToolResult | None]:
        """
        查找工具并完成权限检查。

        返回 (executor, denial)：denial 非空表示被拒绝，调用方不应再执行。
        权限检查在调用线程内按序完成，避免并行批次里多个确认弹窗互相竞争。
        """
        executor = self.tools.get(tool_call.name)
        if not executor:
            return None, ToolResult(
                tool_call_id=tool_call.id,
                content="",
                success=False,
                error=f"Tool '{tool_call.name}' not found",
            )

        self.events.emit(
            Event.create(
                EventType.TOOL_CALL,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
            )
        )

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
            return executor, ToolResult(
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

            if self.config.auto_confirm_handler:
                approved = self.config.auto_confirm_handler(
                    tool_call.name, tool_call.arguments
                )
            else:
                approved = False

            if not approved:
                self.events.emit(
                    Event.create(
                        EventType.PERMISSION_RESPONSE,
                        tool_call_id=tool_call.id,
                        decision="user_denied",
                    )
                )
                return executor, ToolResult(
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

        return executor, None

    def _await_tool(
        self,
        tool_call: ToolCall,
        future: concurrent.futures.Future,
    ) -> ToolResult:
        """等待工具结果，并把超时/异常收敛成 ToolResult。"""
        try:
            result = future.result(timeout=self.config.tool_execution_timeout)
        except TimeoutError:
            future.cancel()
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

        return ToolResult(
            tool_call_id=tool_call.id,
            content=result.content,
            success=result.success,
            error=result.error,
            metadata=result.metadata,
        )

    def _check_compaction(self) -> None:
        """检查是否需要上下文压缩（阈值与实际裁剪统一交给 ContextManager）。"""
        if not self._state:
            return

        if not self.context.should_compact(self._state):
            return

        logger.info("Context approaching limit, triggering autocompaction")
        result = self.context.compact(self._state)
        self.events.emit(Event.create(EventType.COMPACTION, **result))

    def _get_final_response(self) -> str:
        """从对话状态中提取最终回复。"""
        if not self._state:
            return ""

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

    # ── 断点续跑 ────────────────────────────────────────────────────

    def _save_checkpoint_if_needed(self) -> None:
        """每轮结束后把对话状态与事件流写入 checkpoint 目录。"""
        if not self.config.checkpoint_dir or not self._session_id:
            return
        if not self._state:
            return

        try:
            directory = Path(self.config.checkpoint_dir) / self._session_id
            directory.mkdir(parents=True, exist_ok=True)
            self.save_state(str(directory / "state.json"))
            self.events.save_to_file(directory / "events.json")
        except Exception as e:
            logger.warning(f"Checkpoint save failed: {e}")

    def _load_checkpoint(self, session_id: str | None) -> bool:
        """从 checkpoint 恢复状态与历史事件；找不到时返回 False（走新会话）。"""
        directory = self._resolve_session_dir(session_id)
        if directory is None:
            return False

        state_file = directory / "state.json"
        if not state_file.exists():
            return False

        try:
            self.load_state(str(state_file))
        except Exception as e:
            logger.warning(f"Checkpoint load failed: {e}")
            self._state = None
            return False

        events_file = directory / "events.json"
        if events_file.exists():
            try:
                restored = EventStream.load_from_file(events_file)
                self.events.extend(restored.events)
            except Exception as e:
                logger.warning(f"Event history load failed: {e}")

        self._session_id = directory.name
        return True

    def _resolve_session_dir(self, session_id: str | None) -> Path | None:
        """定位会话目录；未指定 session_id 时取最近修改的一个。"""
        if not self.config.checkpoint_dir:
            return None

        root = Path(self.config.checkpoint_dir)
        if session_id:
            directory = root / session_id
            return directory if directory.exists() else None

        if not root.exists():
            return None

        candidates = sorted(
            root.glob("*/state.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0].parent if candidates else None