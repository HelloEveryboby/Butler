# -*- coding: utf-8 -*-
"""butler plugin - 插件包管理 (dsh / Claude Code 声明式资产导入)"""

import argparse
import json
import logging
import sys
from pathlib import Path

from butler.core.plugin_bundle import (
    detect_bundle,
    get_plugin,
    install_plugin,
    list_plugins,
    remove_plugin,
)

logger = logging.getLogger("PluginCLI")


def _print_assets(plugin: dict) -> str:
    assets = plugin.get("assets") or {}
    parts = []
    for kind in ("skills", "commands", "agents"):
        items = assets.get(kind) or []
        if items:
            parts.append(f"{kind}={len(items)}")
    return " ".join(parts) if parts else "(无声明式资产)"


def cmd_add(args) -> int:
    if not args.source:
        print("❌ 请提供插件来源 (本地目录 / zip / git / npm 包名)", file=sys.stderr)
        return 1
    try:
        marker = install_plugin(args.source, name=args.name, force=args.force)
    except FileExistsError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ 安装失败: {e}", file=sys.stderr)
        return 1

    print(f"✅ 插件已安装: {marker['name']}")
    print(f"   类型:   {marker.get('type') or 'skills'}")
    print(f"   版本:   {marker.get('version') or 'N/A'}")
    print(f"   资产:   {_print_assets(marker)}")
    print(f"   路径:   plugins/{marker['name']}")
    return 0


def cmd_list(args) -> int:
    plugins = list_plugins()
    if args.format:
        print(json.dumps(plugins, ensure_ascii=False, indent=2))
        return 0

    if not plugins:
        print("⚠ 尚未安装任何插件包。")
        print("  安装示例: python butler_cli.py plugin add ./path/to/plugin")
        return 0

    print("Butler 插件包 (声明式资产导入)")
    print("-" * 60)
    for plugin in plugins:
        name = plugin.get("name")
        ver = plugin.get("version") or "-"
        ptype = plugin.get("type") or "skills"
        print(f"  {name}  v{ver}  [{ptype}]  {_print_assets(plugin)}")
        desc = plugin.get("description")
        if desc:
            print(f"    {desc}")
    print("-" * 60)
    print(f"共 {len(plugins)} 个插件包")
    return 0


def cmd_info(args) -> int:
    plugin = get_plugin(args.name)
    if not plugin:
        print(f"❌ 插件 '{args.name}' 未找到", file=sys.stderr)
        return 1
    if args.format:
        print(json.dumps(plugin, ensure_ascii=False, indent=2))
        return 0

    print(f"插件详情: {plugin.get('name')}")
    rows = [
        ("名称", plugin.get("display_name") or plugin.get("name")),
        ("版本", plugin.get("version") or "N/A"),
        ("类型", plugin.get("type") or "skills"),
        ("包名", plugin.get("package_name") or "N/A"),
        ("来源", plugin.get("source") or "N/A"),
        ("安装时间", plugin.get("installed_at") or "N/A"),
        ("描述", plugin.get("description") or "无描述"),
    ]
    for label, value in rows:
        print(f"  {label:<8} {value}")

    assets = plugin.get("assets") or {}
    for kind in ("skills", "commands", "agents"):
        for rel in assets.get(kind) or []:
            print(f"  {kind:<8} {rel}")

    for key in ("dsh_patch", "hooks", "mcp"):
        if plugin.get(key):
            print(f"  {key:<8} {plugin[key]}")
    return 0


def cmd_remove(args) -> int:
    if not remove_plugin(args.name):
        print(f"❌ 插件 '{args.name}' 未找到", file=sys.stderr)
        return 1
    print(f"✅ 已移除插件: {args.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler plugin",
        description="Butler 插件包管理 (兼容 dsh / Claude Code 声明式资产)",
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_add = sub.add_parser("add", add_help=False, aliases=["install"])
    p_add.add_argument("source", nargs="?", default=None, help="本地目录 / zip / git URL / npm 包名")
    p_add.add_argument("-n", "--name", default=None, help="安装目录名 (默认取插件包名)")
    p_add.add_argument("-f", "--force", action="store_true", help="覆盖已存在的插件")
    p_add.add_argument("-h", "--help", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_ls = sub.add_parser("list", add_help=False, aliases=["ls"])
    p_ls.add_argument("-j", "--json", action="store_true", dest="format")
    p_ls.add_argument("-h", "--help", action="store_true")
    p_ls.set_defaults(func=cmd_list)

    p_info = sub.add_parser("info", add_help=False)
    p_info.add_argument("name")
    p_info.add_argument("-j", "--json", action="store_true", dest="format")
    p_info.add_argument("-h", "--help", action="store_true")
    p_info.set_defaults(func=cmd_info)

    p_rm = sub.add_parser("remove", add_help=False, aliases=["rm", "uninstall"])
    p_rm.add_argument("name")
    p_rm.add_argument("-h", "--help", action="store_true")
    p_rm.set_defaults(func=cmd_remove)

    parser.set_defaults(func=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "help", False) or not args.command:
        parser.print_help()
        return 0
    func = getattr(args, "func", None)
    return func(args) if func else 0


if __name__ == "__main__":
    sys.exit(main())
