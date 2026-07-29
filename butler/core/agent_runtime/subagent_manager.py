"""
子代理管理器 — 隔离上下文子代理委托系统。

参考架构：Claude Code 的 Subagent 系统。

核心特性：
    1. 隔离上下文：每个 subagent 拥有全新的上下文窗口，不继承父对话历史
    2. 独立系统提示：每个 subagent 可定义自己的系统提示
    3. 工具隔离：通过 tools 字段限制 subagent 可用工具
    4. 嵌套执行：subagent 可生成自己的子代理（最大 5 层）
    5. 摘要返回：仅返回最终消息给父代理，中间工具调用留在子代理记录中

Subagent 定义格式（Markdown + YAML frontmatter）：

    ---
    name: code-reviewer
    description: Reviews code for bugs and suggests improvements
    tools: [read, grep, glob, ls]
    model: inherit
    max_turns: 20
    ---
    You are a code reviewer. Analyze code for bugs, security issues,
    and suggest improvements. Be concise and specific.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .types import Event, EventType, Message, StopReason

logger = logging.getLogger(__name__)

# 最大嵌套深度（参考 Claude Code 的 5 层限制）
_MAX_NESTING_DEPTH = 5


@dataclass
class SubagentDefinition:
    """
    子代理定义。

    参考 Claude Code 的 subagent frontmatter 字段：
        - name: 唯一标识符
        - description: 告诉 LLM 何时委托（最重要的编写决策）
        - tools: 工具允许列表
        - disallowed_tools: 工具拒绝列表（先于允许列表评估）
        - model: 模型选择
        - max_turns: 代理回合上限
        - system_prompt: 系统提示词
    """

    name: str
    description: str
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    """工具允许列表。空列表表示继承父会话所有工具。"""

    disallowed_tools: list[str] = field(default_factory=list)
    """工具拒绝列表（先于允许列表评估）。"""

    model: str = "inherit"
    """模型选择：sonnet/opus/haiku/inherit。"""

    max_turns: int = 30
    """代理回合上限。"""

    permission_mode: str = "inherit"
    """权限模式覆盖。"""

    @classmethod
    def from_markdown(cls, content: str) -> SubagentDefinition:
        """
        从 Markdown + YAML frontmatter 解析 subagent 定义。

        格式：
            ---
            name: code-reviewer
            description: Reviews code
            tools: [read, grep]
            ---
            System prompt here.
        """
        # 解析 frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                system_prompt = parts[2].strip()

                return cls(
                    name=frontmatter.get("name", ""),
                    description=frontmatter.get("description", ""),
                    system_prompt=system_prompt,
                    tools=frontmatter.get("tools", []),
                    disallowed_tools=frontmatter.get("disallowed_tools", []),
                    model=frontmatter.get("model", "inherit"),
                    max_turns=frontmatter.get("max_turns", 30),
                    permission_mode=frontmatter.get("permission_mode", "inherit"),
                )

        # 无 frontmatter：整个内容作为描述
        return cls(name="", description=content.strip())

    @classmethod
    def from_file(cls, path: str | Path) -> SubagentDefinition:
        """从文件加载 subagent 定义。"""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        definition = cls.from_markdown(content)
        if not definition.name:
            definition.name = path.stem
        return definition

    def to_markdown(self) -> str:
        """序列化为 Markdown + YAML frontmatter。"""
        frontmatter = {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "disallowed_tools": self.disallowed_tools,
            "model": self.model,
            "max_turns": self.max_turns,
            "permission_mode": self.permission_mode,
        }
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        return f"---\n{yaml_str}---\n{self.system_prompt}"


class SubagentManager:
    """
    子代理管理器。

    管理 subagent 的定义、发现和委托执行。

    生命周期四阶段（参考 Claude Code）：
        1. 触发：用户自然语言提示、@agent-name 显式调用，或 LLM 自动匹配
        2. 隔离：创建全新隔离的上下文窗口
        3. 执行：使用允许的工具独立工作
        4. 摘要返回：仅返回最终消息给父代理

    使用方式::

        manager = SubagentManager()

        # 从目录加载 subagent 定义
        manager.load_from_directory(".butler/agents/")

        # 列出可用 subagent
        agents = manager.list_agents()

        # 委托任务
        result = manager.delegate(
            agent_name="code-reviewer",
            task="Review auth.py for security issues",
            parent_runtime=runtime,
        )
    """

    def __init__(self):
        self._definitions: dict[str, SubagentDefinition] = {}
        self._depth: int = 0
        """当前嵌套深度。"""
        self._depth_lock = threading.Lock()
        """嵌套深度锁（线程安全）。"""

    @property
    def depth(self) -> int:
        return self._depth

    def register(self, definition: SubagentDefinition) -> None:
        """注册 subagent 定义。"""
        self._definitions[definition.name] = definition
        logger.info(f"Registered subagent: {definition.name}")

    def load_from_directory(self, dir_path: str | Path) -> int:
        """
        从目录加载所有 subagent 定义。

        参考 Claude Code 的存储优先级：
            .claude/agents/ (项目级) > ~/.claude/agents/ (用户级)

        返回加载的定义数量。
        """
        dir_path = Path(dir_path)
        if not dir_path.exists():
            return 0

        count = 0
        for file_path in dir_path.glob("*.md"):
            try:
                definition = SubagentDefinition.from_file(file_path)
                if definition.name:
                    self.register(definition)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to load subagent from {file_path}: {e}")

        logger.info(f"Loaded {count} subagent definitions from {dir_path}")
        return count

    def list_agents(self) -> list[SubagentDefinition]:
        """列出所有已注册的 subagent。"""
        return list(self._definitions.values())

    def get_agent(self, name: str) -> SubagentDefinition | None:
        """获取指定 subagent 定义。"""
        return self._definitions.get(name)

    def match_agent(self, task_description: str) -> str | None:
        """
        根据任务描述自动匹配 subagent。

        参考 Claude Code：LLM 根据 description 字段决定何时委托。
        这里使用简单的关键词匹配作为降级方案。
        """
        task_lower = task_description.lower()
        best_match = None
        best_score = 0

        for name, definition in self._definitions.items():
            desc_lower = definition.description.lower()
            # 计算关键词匹配分数
            desc_words = set(desc_lower.split())
            task_words = set(task_lower.split())
            overlap = len(desc_words & task_words)

            if overlap > best_score:
                best_score = overlap
                best_match = name

        return best_match if best_score > 0 else None

    def delegate(
        self,
        agent_name: str,
        task: str,
        parent_runtime: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        委托任务给子代理。

        参数:
            agent_name: subagent 名称
            task: 任务描述
            parent_runtime: 父 AgentRuntime 实例
            **kwargs: 传递给子代理的额外参数

        返回:
            dict: {
                "response": 子代理最终回复,
                "stop_reason": 终止原因,
                "turns": 执行轮次,
                "events": 子代理事件流,
            }

        异常:
            KeyError: subagent 未注册
            RuntimeError: 超过最大嵌套深度
        """
        definition = self._definitions.get(agent_name)
        if not definition:
            raise KeyError(f"Subagent '{agent_name}' not registered")

        with self._depth_lock:
            if self._depth >= _MAX_NESTING_DEPTH:
                raise RuntimeError(
                    f"Maximum nesting depth ({_MAX_NESTING_DEPTH}) exceeded"
                )
            current_depth = self._depth
            self._depth += 1

        # 发出 subagent spawn 事件
        parent_runtime.events.emit(
            Event.create(
                EventType.SUBAGENT_SPAWN,
                agent_name=agent_name,
                task=task,
                depth=current_depth + 1,
            )
        )

        logger.info(
            f"Spawning subagent '{agent_name}' (depth={current_depth + 1}) "
            f"for task: {task[:100]}"
        )

        # 创建隔离的工具注册表
        from .tool_registry import ToolRegistry

        child_tools = self._create_isolated_tools(
            parent_runtime.tools, definition
        )

        # 创建隔离的上下文管理器（不共享父代理的 ContextManager）
        from .context_manager import ContextManager

        child_context = ContextManager(
            token_limit=parent_runtime.config.context_token_limit,
            compaction_threshold=parent_runtime.config.compaction_threshold,
            llm_summarize_handler=parent_runtime.context._llm_summarize_handler
            if hasattr(parent_runtime.context, "_llm_summarize_handler")
            else None,
        )

        # 创建隔离的权限系统（子代理不应继承 BYPASS_PERMISSIONS）
        from .permission import PermissionMode, PermissionSystem

        child_permissions = PermissionSystem()
        if definition.permission_mode and definition.permission_mode != "inherit":
            child_permissions.set_mode(PermissionMode(definition.permission_mode))
        else:
            # 默认使用 DEFAULT 模式，即使父是 BYPASS_PERMISSIONS
            parent_mode = parent_runtime.permissions.mode
            if parent_mode == PermissionMode.BYPASS_PERMISSIONS:
                child_permissions.set_mode(PermissionMode.DEFAULT)
            else:
                child_permissions.set_mode(parent_mode)

        # 创建子 AgentRuntime（隔离上下文 + 隔离权限）
        from .agent_runtime import AgentConfig, AgentRuntime

        child_config = AgentConfig(
            max_turns=definition.max_turns,
            system_prompt=definition.system_prompt,
            llm_call_handler=parent_runtime.config.llm_call_handler,
            auto_confirm_handler=parent_runtime.config.auto_confirm_handler,
            context_token_limit=parent_runtime.config.context_token_limit,
            enable_self_healing=parent_runtime.config.enable_self_healing,
        )

        child_stream = type(parent_runtime.events)()
        child_runtime = AgentRuntime(
            config=child_config,
            tool_registry=child_tools,
            permission_system=child_permissions,
            context_manager=child_context,
            event_stream=child_stream,
        )

        try:
            result = child_runtime.run(task, **kwargs)
        except Exception as e:
            logger.error(f"Subagent '{agent_name}' failed: {e}", exc_info=True)
            result = {
                "response": f"Subagent error: {e}",
                "stop_reason": "error",
                "turns": 0,
                "events": [],
            }
        finally:
            with self._depth_lock:
                self._depth -= 1

        # 发出 subagent return 事件
        parent_runtime.events.emit(
            Event.create(
                EventType.SUBAGENT_RETURN,
                agent_name=agent_name,
                response=result.get("response", ""),
                turns=result.get("turns", 0),
                stop_reason=result.get("stop_reason", ""),
            )
        )

        logger.info(
            f"Subagent '{agent_name}' completed: "
            f"{result.get('turns', 0)} turns, "
            f"stop={result.get('stop_reason', '')}"
        )

        return result

    def _create_isolated_tools(
        self,
        parent_tools: Any,
        definition: SubagentDefinition,
    ) -> Any:
        """
        创建隔离的工具注册表。

        参考 Claude Code 的工具隔离机制：
            1. disallowed_tools 先评估（拒绝列表）
            2. tools 后评估（允许列表）
            3. 默认继承父会话所有工具
        """
        from .tool_registry import ToolRegistry

        child_registry = ToolRegistry()

        # 使用公开接口获取所有工具名
        tool_names = parent_tools.list_names()
        for name in tool_names:
            # 检查拒绝列表
            if name in definition.disallowed_tools:
                continue

            # 如果有允许列表，只保留允许的工具
            if definition.tools and name not in definition.tools:
                continue

            # 复制到子注册表（通过公开接口获取 executor）
            executor = parent_tools.get(name)
            child_registry._tools[name] = executor

        return child_registry
