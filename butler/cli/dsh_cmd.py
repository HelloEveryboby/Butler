"""butler dsh — dsh 插件市场适配（无需安装 dsh 官方软件）。"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_search(args: argparse.Namespace) -> int:
    from butler.core.dsh_adapter import search_market

    entries = search_market(args.keyword or "")
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0
    if not entries:
        print("未找到插件。")
        print("  可配置 config.yaml -> dsh.market_index_urls 指向插件市场索引，")
        print("  或直接安装: butler dsh install <git URL | zip | 本地目录 | npm 包名>")
        return 0
    for item in entries:
        print(f"{item.get('name', '?')}  {item.get('version', '')}")
        if item.get("description"):
            print(f"   {item['description']}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    from butler.core.dsh_adapter import install

    try:
        marker = install(args.source, name=args.name, force=args.force)
    except FileExistsError as exc:
        print(f"butler dsh: error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"butler dsh: error: 安装失败: {exc}", file=sys.stderr)
        return 1

    assets = marker.get("assets") or {}
    summary = " ".join(
        f"{kind}={len(assets.get(kind) or [])}"
        for kind in ("skills", "commands", "agents")
        if assets.get(kind)
    )
    print(f"installed: {marker.get('name')}  v{marker.get('version') or '?'}  [{marker.get('type')}]")
    print(f"  assets: {summary or '(无声明式资产)'}")
    print("  note: hooks / .mcp.json 仅登记不执行（dsh.allow_hooks=false）")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from butler.core.plugin_bundle import list_plugins

    plugins = list_plugins()
    if not plugins:
        print("（尚未安装任何插件）")
        return 0
    for plugin in plugins:
        state = "disabled" if plugin.get("enabled") is False else "enabled"
        print(
            f"{plugin.get('name'):<28} v{plugin.get('version') or '-':<8}"
            f" [{plugin.get('type') or 'skills'}] {state}"
        )
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    from butler.core.plugin_bundle import get_plugin

    plugin = get_plugin(args.name)
    if not plugin:
        print(f"butler dsh: error: 未找到插件: {args.name}", file=sys.stderr)
        return 1
    print(json.dumps(plugin, ensure_ascii=False, indent=2))
    return 0


def _toggle(args: argparse.Namespace, enabled: bool) -> int:
    from butler.core.dsh_adapter import set_enabled

    if not set_enabled(args.name, enabled):
        print(f"butler dsh: error: 未找到插件: {args.name}", file=sys.stderr)
        return 1
    action = "enable" if enabled else "disable"
    print(f"{action}: {args.name}（重载技能后生效）")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    return _toggle(args, True)


def cmd_disable(args: argparse.Namespace) -> int:
    return _toggle(args, False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler dsh",
        description="dsh 插件适配：搜索 / 安装 / 启停（不依赖 dsh 官方软件）",
        epilog=(
            "示例:\n"
            "  butler dsh search pdf -j\n"
            "  butler dsh install https://github.com/user/plugin -n myplugin\n"
            "  butler dsh install ./plugin.zip -f\n"
            "  butler dsh ls && butler dsh disable myplugin"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_search = sub.add_parser("search", add_help=False, aliases=["find"])
    p_search.add_argument("keyword", nargs="?", default="")
    p_search.add_argument("-j", "--json", action="store_true")
    p_search.add_argument("-h", "--help", action="store_true")
    p_search.set_defaults(func=cmd_search)

    p_install = sub.add_parser("install", add_help=False, aliases=["add"])
    p_install.add_argument("source", help="git URL / zip / 本地目录 / npm 包名")
    p_install.add_argument("-n", "--name", default=None, help="安装后的插件名")
    p_install.add_argument("-f", "--force", action="store_true", help="覆盖已存在插件")
    p_install.add_argument("-h", "--help", action="store_true")
    p_install.set_defaults(func=cmd_install)

    p_list = sub.add_parser("list", add_help=False, aliases=["ls"])
    p_list.add_argument("-h", "--help", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_info = sub.add_parser("info", add_help=False)
    p_info.add_argument("name")
    p_info.add_argument("-h", "--help", action="store_true")
    p_info.set_defaults(func=cmd_info)

    p_enable = sub.add_parser("enable", add_help=False)
    p_enable.add_argument("name")
    p_enable.add_argument("-h", "--help", action="store_true")
    p_enable.set_defaults(func=cmd_enable)

    p_disable = sub.add_parser("disable", add_help=False)
    p_disable.add_argument("name")
    p_disable.add_argument("-h", "--help", action="store_true")
    p_disable.set_defaults(func=cmd_disable)

    parser.set_defaults(func=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv and argv[0] in ("-h", "--help"):
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if getattr(args, "help", False) or not args.command:
        parser.print_help()
        return 0
    func = getattr(args, "func", None)
    return func(args) if func else 0


if __name__ == "__main__":
    sys.exit(main())
