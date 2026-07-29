"""
Headless CLI — 纯命令行入口，不初始化 GUI/语音。

参考架构：
    - OpenHands CLI: 纯命令行入口，headless 友好
    - Claude Code: CLI 优先设计

使用方式::

    # 单次命令
    python -m butler.core.agent_runtime.cli "list all Python files"

    # 交互模式
    python -m butler.core.agent_runtime.cli --interactive

    # 指定权限模式
    python -m butler.core.agent_runtime.cli --mode auto "run tests"

    # 从文件读取输入
    cat requirements.txt | python -m butler.core.agent_runtime.cli "analyze dependencies"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .agent_runtime import AgentConfig, AgentRuntime
from .builtin_tools import register_builtin_tools
from .context_manager import ContextManager
from .event_stream import EventStream
from .permission import PermissionMode, PermissionSystem
from .subagent_manager import SubagentManager
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

# 默认系统提示
_DEFAULT_SYSTEM_PROMPT = """\
You are Butler, a powerful AI coding assistant. You can read, write, and edit files,
execute bash commands, search code, and delegate tasks to subagents.

Always use the available tools to accomplish tasks. Be concise and specific in your responses.
When a task is complete, provide a brief summary of what was done.
"""


def create_runtime(
    workspace_root: str | None = None,
    permission_mode: str = "default",
    system_prompt: str | None = None,
    max_turns: int = 50,
    llm_call_handler: Any = None,
    auto_confirm: bool = False,
) -> AgentRuntime:
    """
    创建配置好的 AgentRuntime 实例。

    参数:
        workspace_root: 工作区根目录
        permission_mode: 权限模式
        system_prompt: 系统提示词
        max_turns: 最大循环轮次
        llm_call_handler: LLM 调用回调
        auto_confirm: 是否自动确认所有权限请求

    返回:
        AgentRuntime: 配置好的运行时实例
    """
    ws_root = workspace_root or os.getcwd()

    # 创建工具注册表并注册内置工具
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace_root=ws_root)

    # 创建权限系统
    perm_config = PermissionMode(permission_mode) if permission_mode else PermissionMode.DEFAULT
    permissions = PermissionSystem()
    permissions.set_mode(perm_config)

    # 创建上下文管理器
    context = ContextManager()

    # 创建事件流
    events = EventStream()

    # 创建运行时配置
    config = AgentConfig(
        max_turns=max_turns,
        system_prompt=system_prompt or _DEFAULT_SYSTEM_PROMPT,
        llm_call_handler=llm_call_handler,
        auto_confirm_handler=(lambda name, args: True) if auto_confirm else None,
    )

    return AgentRuntime(
        config=config,
        tool_registry=registry,
        permission_system=permissions,
        context_manager=context,
        event_stream=events,
    )


def run_single_command(
    command: str,
    workspace_root: str | None = None,
    permission_mode: str = "default",
    auto_confirm: bool = False,
    llm_call_handler: Any = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    执行单条命令。

    参数:
        command: 用户命令
        workspace_root: 工作区根目录
        permission_mode: 权限模式
        auto_confirm: 是否自动确认
        llm_call_handler: LLM 调用回调
        verbose: 是否输出详细事件

    返回:
        执行结果字典
    """
    runtime = create_runtime(
        workspace_root=workspace_root,
        permission_mode=permission_mode,
        llm_call_handler=llm_call_handler,
        auto_confirm=auto_confirm,
    )

    if verbose:
        # 订阅事件输出
        def print_event(event):
            if event.type.value == "tool_call":
                print(f"  [tool_call] {event.data.get('tool_name')}", file=sys.stderr)
            elif event.type.value == "tool_result":
                success = event.data.get("success", True)
                marker = "✓" if success else "✗"
                print(f"  [{marker}] {event.data.get('tool_name', '')}", file=sys.stderr)
            elif event.type.value == "tool_error":
                print(f"  [ERROR] {event.data.get('error', '')}", file=sys.stderr)

        runtime.events.subscribe_all(print_event)

    result = runtime.run(command)
    return result


def run_interactive(
    workspace_root: str | None = None,
    permission_mode: str = "default",
    auto_confirm: bool = False,
    llm_call_handler: Any = None,
) -> None:
    """
    交互模式。

    参考 Claude Code 的交互式 CLI：
        - 持续接收用户输入
        - 支持特殊命令（/exit, /mode, /tools 等）
        - 显示事件流
    """
    runtime = create_runtime(
        workspace_root=workspace_root,
        permission_mode=permission_mode,
        llm_call_handler=llm_call_handler,
        auto_confirm=auto_confirm,
    )

    ws = workspace_root or os.getcwd()
    print(f"Butler Agent Runtime (headless)")
    print(f"Workspace: {ws}")
    print(f"Tools: {', '.join(runtime.tools.list_names())}")
    print(f"Permission mode: {runtime.permissions.mode.value}")
    print(f"Type /help for commands, /exit to quit.\n")

    # 事件打印回调（只订阅一次，避免内存泄漏）
    _printed_events: set[int] = set()

    def print_event(event):
        etype = event.type.value
        if etype == "tool_call":
            print(f"  → {event.data.get('tool_name', '')}", file=sys.stderr)
        elif etype == "tool_result":
            success = event.data.get("success", True)
            marker = "✓" if success else "✗"
            name = event.data.get("tool_name", "")
            print(f"  {marker} {name}", file=sys.stderr)
        elif etype == "permission_request":
            print(f"  ? Permission requested: {event.data.get('tool_name', '')}", file=sys.stderr)
        elif etype == "error":
            print(f"  ✗ Error: {event.data.get('error', '')}", file=sys.stderr)

    runtime.events.subscribe_all(print_event)

    while True:
        try:
            user_input = input("butler> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # 特殊命令
        if user_input.startswith("/"):
            cmd = user_input.lower()

            if cmd in ("/exit", "/quit", "/q"):
                print("Goodbye!")
                break

            if cmd == "/help":
                print("Commands:")
                print("  /exit        Exit the session")
                print("  /tools       List available tools")
                print("  /mode <mode> Change permission mode")
                print("  /events      Show event stream summary")
                print("  /save <path> Save conversation state")
                print("  /load <path> Load conversation state")
                continue

            if cmd == "/tools":
                print("Available tools:")
                for name in runtime.tools.list_names():
                    executor = runtime.tools.get(name)
                    desc = executor.definition.description[:80]
                    print(f"  {name}: {desc}")
                continue

            if cmd.startswith("/mode "):
                new_mode = cmd[6:].strip()
                try:
                    mode = PermissionMode(new_mode)
                    runtime.permissions.set_mode(mode)
                    print(f"Permission mode changed to: {mode.value}")
                except ValueError:
                    print(f"Invalid mode. Valid: {', '.join(m.value for m in PermissionMode)}")
                continue

            if cmd == "/events":
                summary = runtime.events.get_summary()
                if summary:
                    print("Event stream summary:")
                    for event_type, count in sorted(summary.items()):
                        print(f"  {event_type}: {count}")
                else:
                    print("No events recorded.")
                continue

            if cmd.startswith("/save "):
                path = cmd[6:].strip()
                try:
                    runtime.save_state(path)
                    runtime.events.save_to_file(path + ".events.json")
                    print(f"State saved to {path}")
                except Exception as e:
                    print(f"Save failed: {e}")
                continue

            if cmd.startswith("/load "):
                path = cmd[6:].strip()
                try:
                    runtime.load_state(path)
                    print(f"State loaded from {path}")
                except Exception as e:
                    print(f"Load failed: {e}")
                continue

            print(f"Unknown command: {user_input}")
            continue

        # 执行命令
        print(f"Running: {user_input}\n")

        result = runtime.run(user_input)

        print(f"\n{result['response']}")
        print(f"\n[turns: {result['turns']}, stop: {result['stop_reason']}]\n")


def main():
    """CLI 入口点。"""
    parser = argparse.ArgumentParser(
        description="Butler Agent Runtime — Headless CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "command",
        nargs="?",
        help="Command to execute (omit for interactive mode)",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Start interactive mode",
    )
    parser.add_argument(
        "-w", "--workspace",
        default=None,
        help="Workspace root directory (default: current directory)",
    )
    parser.add_argument(
        "-m", "--mode",
        default="default",
        choices=[m.value for m in PermissionMode],
        help="Permission mode (default: default)",
    )
    parser.add_argument(
        "-y", "--auto-confirm",
        action="store_true",
        help="Automatically confirm all permission requests",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output (show events)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=50,
        help="Maximum agent turns (default: 50)",
    )

    args = parser.parse_args()

    # 设置日志
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # LLM 调用回调（需要实际接入 LLM API）
    llm_handler = _create_llm_handler()

    if args.interactive or (not args.command and not sys.stdin.isatty()):
        # 交互模式或管道输入
        if not sys.stdin.isatty() and not args.command:
            # 管道输入
            piped_input = sys.stdin.read().strip()
            if piped_input:
                result = run_single_command(
                    command=piped_input,
                    workspace_root=args.workspace,
                    permission_mode=args.mode,
                    auto_confirm=args.auto_confirm,
                    llm_call_handler=llm_handler,
                    verbose=args.verbose,
                )
                print(result.get("response", ""))
                return

        run_interactive(
            workspace_root=args.workspace,
            permission_mode=args.mode,
            auto_confirm=args.auto_confirm,
            llm_call_handler=llm_handler,
        )
    elif args.command:
        # 单次命令
        result = run_single_command(
            command=args.command,
            workspace_root=args.workspace,
            permission_mode=args.mode,
            auto_confirm=args.auto_confirm,
            llm_call_handler=llm_handler,
            verbose=args.verbose,
        )
        print(result.get("response", ""))
    else:
        parser.print_help()


def _create_llm_handler():
    """
    创建 LLM 调用回调。

    尝试使用 Butler 现有的 NLUService 或直接调用 DeepSeek/OpenAI API。
    """
    try:
        from package.core_utils.config_loader import config_loader

        api_key = os.getenv("DEEPSEEK_API_KEY") or config_loader.get("api.deepseek.key")
        if not api_key or "YOUR_" in str(api_key):
            logger.warning("No API key configured, LLM calls will return empty")
            return None

        endpoint = (
            config_loader.get("api.deepseek.endpoint")
            or "https://api.deepseek.com/v1"
        )
        model = config_loader.get("api.deepseek.model") or "deepseek-chat"

        def llm_call_handler(messages, tools, **kwargs):
            """调用 DeepSeek API with tool calling。"""
            import requests

            url = f"{endpoint}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "messages": messages,
                "tools": tools if tools else None,
                "tool_choice": "auto" if tools else None,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.2),
            }

            # 移除 None 值
            payload = {k: v for k, v in payload.items() if v is not None}

            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            stop_reason = choice.get("finish_reason", "end_turn")

            return {
                "content": message.get("content", ""),
                "tool_calls": message.get("tool_calls", []),
                "stop_reason": stop_reason,
            }

        return llm_call_handler

    except Exception as e:
        logger.warning(f"Failed to create LLM handler: {e}")
        return None


if __name__ == "__main__":
    main()
