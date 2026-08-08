# -*- coding: utf-8 -*-
"""
Tool CLI — Linux 风格的辅助工具命令行。

用法:
    python butler_cli.py tool list          # 列出所有可用工具
    python butler_cli.py tool list -j       # JSON 格式输出
    python butler_cli.py tool run read --path foo.py
    python butler_cli.py tool run bash --command "ls -la"
    python butler_cli.py tool info read      # 查看工具详情
"""

import argparse
import json
import sys
import os
import shutil
from typing import Any, Dict, List

from butler.core.tool_bridge import (
    ToolContext,
    list_tools,
    execute_tool,
    get_registry,
)

IS_TTY = sys.stdout.isatty()
HAS_COLOR = IS_TTY and not os.environ.get("NO_COLOR")


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"


def _c(text: str, *codes: str) -> str:
    if not HAS_COLOR:
        return text
    return "".join(codes) + text + C.RESET


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def cmd_list(args) -> int:
    tools = list_tools()

    if getattr(args, 'json', False):
        print(json.dumps(tools, ensure_ascii=False, indent=2))
        return 0

    if not tools:
        print(_c("⚠️  没有可用的工具。", C.YELLOW))
        return 0

    # 按权限分类
    always = [t for t in tools if t['permission_level'] == 'always_allow']
    confirm = [t for t in tools if t['permission_level'] == 'require_confirm']

    print(_c("📦 Butler 辅助工具", C.BOLD, C.CYAN))
    print("═" * 50)

    if always:
        print(_c(f"\n  🔓 自动执行 (always_allow, {len(always)} 个):", C.GREEN))
        for t in always:
            ro = _c("👁", C.DIM) if t.get('is_read_only') else "  "
            ds = _c("💥", C.RED) if t.get('is_destructive') else "  "
            desc = _truncate(t['description'], 55)
            print(f"  {ro}{ds} {_c(t['name'], C.BOLD, C.GREEN):<20} {desc}")

    if confirm:
        print(_c(f"\n  🔐 需确认 (require_confirm, {len(confirm)} 个):", C.YELLOW))
        for t in confirm:
            ro = _c("👁", C.DIM) if t.get('is_read_only') else "  "
            ds = _c("💥", C.RED) if t.get('is_destructive') else "  "
            desc = _truncate(t['description'], 55)
            print(f"  {ro}{ds} {_c(t['name'], C.BOLD, C.YELLOW):<20} {desc}")

    total_readonly = len([t for t in tools if t.get('is_read_only')])
    total_destructive = len([t for t in tools if t.get('is_destructive')])
    print(f"\n  TOTAL {len(tools)} | 只读 {total_readonly} | 破坏性 {total_destructive}")
    print(_c("  tool run <name> [--key value ...]  执行工具", C.DIM))
    print(_c("  tool info <name>                      查看详情", C.DIM))
    return 0


def cmd_run(args) -> int:
    tool_name = args.tool_name
    ctx = ToolContext()

    info = ctx.info(tool_name)
    if info is None:
        print(_c(f"❌ 工具 '{tool_name}' 未找到", C.RED), file=sys.stderr)
        print(f"  可用工具: {', '.join(ctx.list())}", file=sys.stderr)
        return 1

    if getattr(args, 'json', False):
        args_dict = _parse_extra_args(getattr(args, 'extra_args', []))
        result = ctx.execute(tool_name, **args_dict)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    args_dict = _parse_extra_args(getattr(args, 'extra_args', []))

    # 显示即将执行的操作
    ro_icon = "👁" if info.get('is_read_only') else "✏️"
    ds_icon = _c("💥", C.RED) if info.get('is_destructive') else ""
    print(f"{ro_icon}{ds_icon} {_c('执行:', C.DIM)} {_c(tool_name, C.BOLD, C.CYAN)}")
    if args_dict:
        print(f"   参数: {_c(json.dumps(args_dict, ensure_ascii=False), C.DIM)}")
    print()

    # 权限检查
    if info['permission_level'] == 'never_allow':
        print(_c("⛔ 此工具被禁止执行", C.RED), file=sys.stderr)
        return 2

    # 执行
    result = ctx.execute(tool_name, **args_dict)

    if result.get('success'):
        content = result.get('content', '')
        if content:
            print(content)
        else:
            print(_c("✅ 执行成功", C.GREEN))
        if result.get('metadata'):
            meta = result['metadata']
            if 'elapsed_ms' in meta:
                print(_c(f"   ⏱ {meta['elapsed_ms']:.0f}ms", C.DIM))
    else:
        print(_c(f"❌ 执行失败: {result.get('error', 'Unknown error')}", C.RED), file=sys.stderr)
        return 1

    return 0


def cmd_info(args) -> int:
    tool_name = args.tool_name
    ctx = ToolContext()

    info = ctx.info(tool_name)
    if info is None:
        print(_c(f"❌ 工具 '{tool_name}' 未找到", C.RED), file=sys.stderr)
        return 1

    if getattr(args, 'json', False):
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    print(_c(f"📋 工具详情: {tool_name}", C.BOLD, C.CYAN))
    print("─" * 50)
    print(f"  名称:       {_c(info['name'], C.BOLD)}")
    print(f"  描述:       {info['description']}")
    print(f"  权限:       {_c(info['permission_level'], C.YELLOW)}")
    print(f"  只读:       {'是' if info['is_read_only'] else '否'}")
    print(f"  破坏性:     {'是' if info['is_destructive'] else '否'}")
    print(f"  并发安全:   {'是' if info['is_concurrency_safe'] else '否'}")

    schema = info.get('parameters_schema', {})
    if schema and schema.get('properties'):
        print(f"\n  参数定义:")
        required = schema.get('required', [])
        for param_name, param_def in schema['properties'].items():
            req = _c(" (必填)", C.RED) if param_name in required else ""
            ptype = param_def.get('type', 'string')
            desc = param_def.get('description', '')
            print(f"    {_c(param_name, C.BOLD, C.CYAN)} [{ptype}]{req}")
            if desc:
                print(f"      {desc}")

        print(f"\n  调用示例:")
        print(f"    python butler_cli.py tool run {tool_name} ", end="")
        example_args = []
        for param_name, param_def in schema['properties'].items():
            if param_name in required:
                example_args.append(f"--{param_name} <{param_def.get('type', 'value')}>")
        print(" ".join(example_args) if example_args else "(无参数)")

    return 0


def cmd_help(args) -> int:
    print(_c("📦 Butler 辅助工具系统", C.BOLD, C.CYAN))
    print()
    print("用法:")
    print("  python butler_cli.py tool list [-j]     列出所有工具")
    print("  python butler_cli.py tool run <name>     执行工具")
    print("  python butler_cli.py tool info <name>    查看工具详情")
    print()
    print("工具按权限分级:")
    print(f"  {_c('🔓 always_allow', C.GREEN)}   - 自动执行 (如 read, ls, glob)")
    print(f"  {_c('🔐 require_confirm', C.YELLOW)} - 需确认 (如 write, edit, bash)")
    print(f"  {_c('⛔ never_allow', C.RED)}    - 禁止执行")
    print()
    print("在技能中使用工具:")
    print("  from butler.core.tool_bridge import get_tools")
    print("  tools = get_tools()")
    print("  content = tools.read(path='file.py')")
    return 0


def _parse_extra_args(extra_args: List[str]) -> Dict[str, Any]:
    """解析 --key value 格式的额外参数。"""
    result = {}
    i = 0
    args = extra_args or []
    while i < len(args):
        arg = args[i]
        if arg.startswith('--'):
            key = arg[2:]
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                raw_val = args[i + 1]
                result[key] = _auto_convert(raw_val)
                i += 2
            else:
                result[key] = True
                i += 1
        elif arg.startswith('-'):
            key = arg[1:]
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                result[key] = _auto_convert(args[i + 1])
                i += 2
            else:
                result[key] = True
                i += 1
        else:
            i += 1
    return result


def _auto_convert(val: str) -> Any:
    """自动转换字符串类型 (int, float, bool)。"""
    if val == 'true':
        return True
    if val == 'false':
        return False
    if val == 'null':
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def build_parser() -> argparse.ArgumentParser:
    """构建工具 CLI 参数解析器 (Linux 风格)。"""
    parser = argparse.ArgumentParser(
        prog="tool",
        description="辅助工具系统 — 文件操作、命令执行等工具集合",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python butler_cli.py tool list
  python butler_cli.py tool list -j
  python butler_cli.py tool run read --path foo.py
  python butler_cli.py tool run bash --command "ls -la"
  python butler_cli.py tool info read
        """,
    )

    sub = parser.add_subparsers(dest='subcommand')

    # list
    p_ls = sub.add_parser('list', help='列出所有可用工具')
    p_ls.add_argument('-j', '--json', action='store_true', help='JSON 格式输出')
    p_ls.set_defaults(func=cmd_list)

    # run
    p_run = sub.add_parser('run', help='执行指定工具')
    p_run.add_argument('tool_name', help='工具名称 (如 read, write, bash)')
    p_run.add_argument('-j', '--json', action='store_true', help='JSON 格式输出')
    p_run.add_argument('extra_args', nargs=argparse.REMAINDER, help='工具参数 (--key value)')
    p_run.set_defaults(func=cmd_run)

    # info
    p_info = sub.add_parser('info', help='查看工具详细信息')
    p_info.add_argument('tool_name', help='工具名称')
    p_info.add_argument('-j', '--json', action='store_true', help='JSON 格式输出')
    p_info.set_defaults(func=cmd_info)

    # help
    p_help = sub.add_parser('help', help='显示工具系统帮助')
    p_help.set_defaults(func=cmd_help)

    parser.set_defaults(func=cmd_help)
    return parser
