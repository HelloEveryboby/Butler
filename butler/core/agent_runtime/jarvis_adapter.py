"""
Jarvis 适配层 — 将旧版 Jarvis._autonomous_agent_loop 迁移到新 AgentRuntime 架构。

设计原则：
    1. 渐进式迁移：不破坏现有 Jarvis 功能，提供新旧两套路径
    2. 透明桥接：将 Jarvis 的 NLUService、SkillManager 等适配为 AgentRuntime 组件
    3. 双模式运行：可在传统模式和新架构模式间切换

使用方式::

    # 在 Jarvis.__init__ 中启用新架构
    self.agent_bridge = JarvisAgentBridge(self)

    # 替代 _autonomous_agent_loop
    def _autonomous_agent_loop(self, command):
        if self.agent_bridge and self.agent_bridge.enabled:
            return self.agent_bridge.run(command)
        # ... 旧版逻辑 ...
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from .agent_runtime import AgentConfig, AgentRuntime
from .builtin_tools import register_builtin_tools
from .context_manager import ContextManager
from .event_stream import EventStream
from .permission import PermissionMode, PermissionSystem
from .subagent_manager import SubagentDefinition, SubagentManager
from .tool_registry import ToolRegistry
from .types import Event, EventType, Message, PermissionLevel, StopReason

logger = logging.getLogger(__name__)


class JarvisAgentBridge:
    """
    Jarvis 到 AgentRuntime 的适配层。

    将 Jarvis 现有的服务（NLUService、SkillManager、IntentRegistry 等）
    适配为 AgentRuntime 所需的组件，实现渐进式迁移。

    核心适配：
        1. NLUService → llm_call_handler（带工具调用支持的 LLM 回调）
        2. IntentRegistry → ToolRegistry（将意图处理器转换为标准工具）
        3. Jarvis._autonomous_agent_loop → AgentRuntime.run
        4. Jarvis.ui_print → EventStream 订阅
        5. Jarvis 权限确认 → auto_confirm_handler
    """

    def __init__(self, jarvis: Any, enabled: bool = False):
        """
        初始化适配层。

        参数:
            jarvis: Jarvis 实例
            enabled: 是否启用新架构（默认 False，渐进式启用）
        """
        self.jarvis = jarvis
        self.enabled = enabled
        self._runtime: AgentRuntime | None = None
        self._subagent_manager: SubagentManager | None = None

        # 事件订阅：将 Agent 事件桥接到 Jarvis UI
        self._event_handlers: list[Callable] = []

    def create_runtime(self) -> AgentRuntime:
        """
        从 Jarvis 实例创建 AgentRuntime。

        将 Jarvis 的服务适配为 AgentRuntime 组件。
        """
        jarvis = self.jarvis

        # 1. 创建工具注册表
        # 从 Jarvis 实例推断项目根目录（优先使用实际工作目录）
        workspace_root = os.getcwd()
        if hasattr(jarvis, "config") and isinstance(jarvis.config, dict):
            workspace_root = jarvis.config.get(
                "workspace_root",
                jarvis.config.get("project_root", os.getcwd()),
            )
        registry = ToolRegistry()
        register_builtin_tools(
            registry,
            workspace_root=str(workspace_root),
        )

        # 2. 将 IntentRegistry 中的意图转换为工具
        self._register_intent_tools(registry)

        # 3. 创建权限系统
        permissions = PermissionSystem()
        permissions.set_mode(PermissionMode.DEFAULT)

        # 4. 创建上下文管理器（复用 Jarvis 的 NLUService 压缩能力）
        context = ContextManager(
            token_limit=120000,
            compaction_threshold=0.8,
            llm_summarize_handler=self._create_summarize_handler(),
        )

        # 5. 创建事件流
        events = EventStream()

        # 6. 订阅事件 → Jarvis UI 输出
        self._setup_event_bridge(events)

        # 7. 创建 LLM 调用回调
        llm_handler = self._create_llm_handler()

        # 8. 创建运行时配置
        config = AgentConfig(
            max_turns=10,
            system_prompt=self._build_system_prompt(),
            llm_call_handler=llm_handler,
            auto_confirm_handler=self._create_confirm_handler(),
            enable_self_healing=True,
        )

        self._runtime = AgentRuntime(
            config=config,
            tool_registry=registry,
            permission_system=permissions,
            context_manager=context,
            event_stream=events,
        )

        # 9. 初始化子代理管理器
        self._subagent_manager = SubagentManager()
        self._load_subagents()

        return self._runtime

    def run(self, command: str) -> dict[str, Any]:
        """
        使用新架构执行命令。

        参数:
            command: 用户命令

        返回:
            执行结果字典
        """
        if not self._runtime:
            self.create_runtime()

        assert self._runtime is not None

        # 获取对话历史
        history = self._get_conversation_history()

        # 转换为 Message 列表
        initial_messages = []
        for h in history:
            role = h.metadata.get("role", "user") if hasattr(h, "metadata") else "user"
            content = h.content if hasattr(h, "content") else str(h)
            initial_messages.append(Message(role=role, content=content))

        # 运行 Agent 循环
        result = self._runtime.run(
            user_input=command,
            initial_messages=initial_messages,
        )

        # 保存对话到长期记忆
        self._save_to_memory(command, result.get("response", ""))

        return result

    def _create_llm_handler(self) -> Callable[..., dict[str, Any]]:
        """
        创建 LLM 调用回调。

        将 Jarvis 的 NLUService.ask_llm 适配为 AgentRuntime 所需的
        (messages, tools, **kwargs) → dict 格式。
        """
        jarvis = self.jarvis

        def handler(messages: list[dict], tools: list[dict], **kwargs) -> dict[str, Any]:
            """调用 DeepSeek/OpenAI API with tool calling。"""
            try:
                import requests

                api_key = (
                    os.getenv("DEEPSEEK_API_KEY")
                    or jarvis.config.get("api", {}).get("deepseek", {}).get("key", "")
                )

                if not api_key or "YOUR_" in str(api_key):
                    logger.warning("No API key configured")
                    return {
                        "content": "AI service unavailable: API key not configured.",
                        "tool_calls": [],
                        "stop_reason": "end_turn",
                    }

                endpoint = (
                    jarvis.config.get("api", {})
                    .get("deepseek", {})
                    .get("endpoint", "https://api.deepseek.com/v1")
                )
                url = f"{endpoint}/chat/completions"

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                payload = {
                    "model": "deepseek-chat",
                    "messages": messages,
                    "tools": tools if tools else None,
                    "tool_choice": "auto" if tools else None,
                    "max_tokens": 4096,
                    "temperature": 0.2,
                }

                # 移除 None 值
                payload = {k: v for k, v in payload.items() if v is not None}

                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                stop_reason = choice.get("finish_reason", "end_turn")

                # 更新额度
                usage = data.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)
                if total_tokens > 0 and hasattr(jarvis, "nlu_service"):
                    try:
                        from package.core_utils.quota_manager import quota_manager
                        quota_manager.update_usage(total_tokens)
                    except Exception:
                        pass

                return {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls", []),
                    "stop_reason": stop_reason,
                }

            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                return {
                    "content": f"Error: {e}",
                    "tool_calls": [],
                    "stop_reason": "end_turn",
                }

        return handler

    def _create_summarize_handler(self) -> Callable[[str], str] | None:
        """创建上下文压缩的 LLM 摘要回调。"""
        jarvis = self.jarvis

        def summarize(text: str) -> str:
            try:
                return jarvis.nlu_service.ask_llm(
                    f"请简要总结以下对话上下文，保留关键任务状态和重要事实：\n\n{text}",
                    use_habit=False,
                )
            except Exception as e:
                logger.warning(f"Summarize failed: {e}")
                return f"[Summary failed: {e}]"

        return summarize

    def _create_confirm_handler(self) -> Callable[[str, dict], bool]:
        """
        创建权限确认回调。

        在 GUI 模式下弹出确认对话框，在 headless 模式下根据配置决定。
        只读工具（read/glob/grep/ls）自动放行，破坏性操作需确认。
        """
        jarvis = self.jarvis

        # 只读工具自动放行
        _READ_ONLY_TOOLS = {"read", "glob", "grep", "ls"}

        def handler(tool_name: str, arguments: dict) -> bool:
            # 只读工具自动允许
            if tool_name.lower() in _READ_ONLY_TOOLS:
                return True

            # headless 模式：检查配置是否允许自动确认
            if not hasattr(jarvis, "root") or jarvis.root is None:
                auto_confirm = False
                if hasattr(jarvis, "config") and isinstance(jarvis.config, dict):
                    auto_confirm = jarvis.config.get("auto_confirm_tools", False)
                if not auto_confirm:
                    logger.warning(
                        f"Permission denied for '{tool_name}' in headless mode "
                        f"(auto_confirm_tools=False). Set auto_confirm_tools=true "
                        f"in config to allow."
                    )
                return auto_confirm

            # GUI 模式：通过 event_bus 弹出确认对话框
            try:
                from butler.core.event_bus import event_bus
                import threading

                approved = {"result": None}
                event = threading.Event()

                def on_confirm_response(data):
                    if data.get("tool_name") == tool_name:
                        approved["result"] = data.get("approved", False)
                        event.set()

                event_bus.subscribe("permission_response", on_confirm_response)
                event_bus.publish("permission_request", {
                    "tool_name": tool_name,
                    "arguments": arguments,
                })

                # 等待用户响应（30 秒超时）
                event.wait(timeout=30)
                event_bus.unsubscribe("permission_response", on_confirm_response)

                if approved["result"] is None:
                    logger.warning(f"Permission request timed out for '{tool_name}'")
                    return False
                return approved["result"]
            except Exception as e:
                logger.warning(f"Permission confirmation failed: {e}, denying")
                return False

        return handler

    def _register_intent_tools(self, registry: ToolRegistry) -> None:
        """
        将 IntentRegistry 中的意图处理器转换为标准工具。

        每个 LLM 意图处理器注册为一个工具，使用意图名作为工具名。
        参数 schema 从意图处理器的类型标注自动推断。
        """
        try:
            from butler.core.intent_dispatcher import intent_registry
            import inspect

            for intent_name, entry in intent_registry._llm_handlers.items():
                handler_fn = entry["function"]
                docstring = entry.get("docstring") or f"Execute intent: {intent_name}"

                # 从函数签名自动推断参数 schema
                parameters = self._infer_schema_from_signature(handler_fn)

                # 包装意图处理器为工具格式
                def make_wrapper(fn, name):
                    def wrapper(arguments: dict, **ctx) -> dict:
                        try:
                            # 适配 IntentRegistry 的调用签名
                            result = fn(
                                container=getattr(self.jarvis, "container", None),
                                entities=arguments,
                                **ctx,
                            )
                            if isinstance(result, dict):
                                return result
                            return {
                                "success": True,
                                "content": str(result) if result else "Done",
                            }
                        except Exception as e:
                            return {"success": False, "error": str(e)}

                    return wrapper

                registry.register(
                    handler=make_wrapper(handler_fn, intent_name),
                    name=intent_name,
                    description=docstring,
                    parameters=parameters,
                    permission_level=PermissionLevel.REQUIRE_CONFIRM,
                )

            logger.info(f"Registered {len(intent_registry._llm_handlers)} intent tools")

        except Exception as e:
            logger.warning(f"Failed to register intent tools: {e}")

    @staticmethod
    def _infer_schema_from_signature(fn: Callable) -> dict[str, Any]:
        """从函数签名推断 JSON Schema 参数。"""
        try:
            sig = inspect.signature(fn)
            properties: dict[str, Any] = {}
            required: list[str] = []

            for param_name, param in sig.parameters.items():
                # 跳过 self/container/entities/ctx 等内部参数
                if param_name in ("self", "container", "entities", "ctx", "kwargs"):
                    continue

                # 推断类型
                annotation = param.annotation
                if annotation is inspect.Parameter.empty:
                    prop_type = "string"
                elif annotation in (str, "str"):
                    prop_type = "string"
                elif annotation in (int, "int"):
                    prop_type = "integer"
                elif annotation in (float, "float"):
                    prop_type = "number"
                elif annotation in (bool, "bool"):
                    prop_type = "boolean"
                elif annotation in (dict, "dict") or hasattr(annotation, "__origin__"):
                    prop_type = "object"
                else:
                    prop_type = "string"

                properties[param_name] = {
                    "type": prop_type,
                    "description": f"Parameter '{param_name}'",
                }

                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

            return {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        except Exception:
            return {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Natural language command to execute",
                    },
                },
                "required": ["command"],
            }

    def _build_system_prompt(self) -> str:
        """构建系统提示词，注入技能和运行节点信息。"""
        jarvis = self.jarvis
        parts = []

        # 基础提示
        parts.append(
            "You are Butler, a powerful AI assistant. "
            "Use the available tools to accomplish tasks. "
            "Be concise and specific."
        )

        # 技能扩展
        try:
            skill_extension = jarvis.skill_manager.get_system_prompt_extension()
            if skill_extension:
                parts.append(skill_extension)
        except Exception:
            pass

        # 运行节点环境
        try:
            runner_env = jarvis._get_runner_env_prompt_extension()
            if runner_env:
                parts.append(runner_env)
        except Exception:
            pass

        # 用户习惯
        try:
            from butler.core.habit_manager import habit_manager
            habit_summary = habit_manager.get_profile_summary()
            if habit_summary:
                parts.append(f"User preferences:\n{habit_summary}")
        except Exception:
            pass

        return "\n\n".join(parts)

    def _get_conversation_history(self) -> list:
        """从 Jarvis 的长期记忆获取对话历史。"""
        try:
            return self.jarvis.long_memory.get_recent_history(10)
        except Exception:
            return []

    def _save_to_memory(self, user_input: str, response: str) -> None:
        """保存对话到长期记忆。"""
        try:
            # 使用对话日志记录，而非污染事实记忆库
            if hasattr(self.jarvis, "long_memory"):
                lm = self.jarvis.long_memory
                # 使用 logs.add_daily_log 记录对话（不污染 fact_db）
                if hasattr(lm, "logs"):
                    lm.logs.add_daily_log(
                        f"User: {user_input}\nAssistant: {response}"
                    )
                # 如果有专用的对话历史接口，使用它
                if hasattr(lm, "save_conversation"):
                    lm.save_conversation(user_input, response)
        except Exception as e:
            logger.warning(f"Failed to save to memory: {e}")

    def _setup_event_bridge(self, events: EventStream) -> None:
        """将 Agent 事件桥接到 Jarvis UI 输出。"""

        def on_message(event: Event):
            data = event.data
            role = data.get("role", "")
            content = data.get("content", "")

            if role == "assistant" and content:
                self.jarvis.ui_print(content, tag="ai_response")

        def on_tool_call(event: Event):
            data = event.data
            tool_name = data.get("tool_name", "")
            self.jarvis.ui_print(f"执行工具: {tool_name}", tag="system_message")

        def on_tool_result(event: Event):
            data = event.data
            tool_name = data.get("tool_name", "")
            success = data.get("success", True)
            if not success:
                error = data.get("error", "")
                self.jarvis.ui_print(f"工具 {tool_name} 失败: {error}", tag="error")

        def on_error(event: Event):
            error = event.data.get("error", "")
            self.jarvis.ui_print(f"错误: {error}", tag="error")

        events.subscribe(EventType.MESSAGE, on_message)
        events.subscribe(EventType.TOOL_CALL, on_tool_call)
        events.subscribe(EventType.TOOL_ERROR, on_tool_result)
        events.subscribe(EventType.ERROR, on_error)

        self._event_handlers = [on_message, on_tool_call, on_tool_result, on_error]

    def _load_subagents(self) -> None:
        """加载子代理定义。"""
        if not self._subagent_manager:
            return

        # 从项目级目录加载
        project_agents = Path(".butler/agents")
        if project_agents.exists():
            self._subagent_manager.load_from_directory(project_agents)

        # 从用户级目录加载
        user_agents = Path.home() / ".butler" / "agents"
        if user_agents.exists():
            self._subagent_manager.load_from_directory(user_agents)

    @property
    def runtime(self) -> AgentRuntime | None:
        """获取当前 AgentRuntime 实例。"""
        return self._runtime

    @property
    def subagent_manager(self) -> SubagentManager | None:
        """获取子代理管理器。"""
        return self._subagent_manager

    def enable(self) -> None:
        """启用新架构。"""
        self.enabled = True
        if not self._runtime:
            self.create_runtime()
        logger.info("JarvisAgentBridge enabled — using new AgentRuntime architecture")

    def disable(self) -> None:
        """禁用新架构，回退到旧版逻辑。"""
        self.enabled = False
        logger.info("JarvisAgentBridge disabled — falling back to legacy loop")
