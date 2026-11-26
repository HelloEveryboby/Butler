"""butler cmd — 命令记录器（查询/登记/统计/补录/组合）。"""

from __future__ import annotations

import argparse
import json
import sys


def _recorder():
    from butler.core.command_recorder import command_recorder

    return command_recorder


def cmd_list(args: argparse.Namespace) -> int:
    rows = _recorder().list_by_category(args.category)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("（记录器为空，先运行: butler cmd sync）")
        return 0
    current = None
    for row in rows:
        if row["category"] != current:
            current = row["category"]
            print(f"\n[{current}]")
        print(f"  {row['name']:<18} {row['purpose']}")
    print(f"\n共 {len(rows)} 条命令")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    rows = _recorder().search(args.query, limit=args.limit)
    if not rows:
        print(f"未找到与 '{args.query}' 相关的命令")
        return 0
    for row in rows:
        print(f"{row['name']}  [{row['category']}]")
        print(f"  作用: {row['purpose']}")
        if row.get("usage"):
            print(f"  用法: {row['usage']}")
        if row.get("example"):
            print(f"  示例: {row['example']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    row = _recorder().get(args.name)
    if not row:
        print(f"butler cmd: error: 未登记命令: {args.name}", file=sys.stderr)
        return 1
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    from butler.core.command_recorder import CommandSpec

    _recorder().upsert(
        CommandSpec(
            name=args.name,
            category=args.category,
            purpose=args.purpose or "",
            usage=args.usage or "",
            example=args.example or "",
            aliases=list(args.alias or []),
            risk=args.risk,
            source=args.source,
        )
    )
    print(f"recorded: {args.name}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    print(json.dumps(_recorder().stats(), ensure_ascii=False, indent=2))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    count = _recorder().sync_from_catalog()
    print(f"sync: {count} 条命令（命令目录 + 插件命令）")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    count = _recorder().promote(args.min_count)
    print(f"promote: {count} 条高频命令")
    return 0


def cmd_combo(args: argparse.Namespace) -> int:
    recorder = _recorder()
    if args.combo_action == "add":
        recorder.add_combo(args.name, args.intent or args.name, args.steps or [])
        print(f"combo: {args.name}")
        return 0
    combos = recorder.list_combos()
    if not combos:
        print("（暂无命令组合）")
        return 0
    for combo in combos:
        print(f"{combo['name']}  <- {combo.get('intent', '')}")
        for step in combo.get("steps", []):
            print(f"    {step}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler cmd",
        description="命令记录器：登记标准命令、记录使用、自动补录高频命令",
        epilog=(
            "示例:\n"
            "  butler cmd sync\n"
            "  butler cmd search 朗读 -n 5\n"
            "  butler cmd list -c '🧰 技能'\n"
            "  butler cmd record scan -c 内容与文档 -u 'butler scan <img> -o out.pdf'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_list = sub.add_parser("list", add_help=False, aliases=["ls"])
    p_list.add_argument("-c", "--category", default=None, help="按分类过滤")
    p_list.add_argument("-j", "--json", action="store_true")
    p_list.add_argument("-h", "--help", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", add_help=False, aliases=["find"])
    p_search.add_argument("query")
    p_search.add_argument("-n", "--limit", type=int, default=10, help="最多返回条数")
    p_search.add_argument("-h", "--help", action="store_true")
    p_search.set_defaults(func=cmd_search)

    p_show = sub.add_parser("show", add_help=False)
    p_show.add_argument("name")
    p_show.add_argument("-h", "--help", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_record = sub.add_parser("record", add_help=False)
    p_record.add_argument("name")
    p_record.add_argument("-c", "--category", default="未分类")
    p_record.add_argument("-p", "--purpose", default="", help="命令作用")
    p_record.add_argument("-u", "--usage", default="", help="标准用法")
    p_record.add_argument("-e", "--example", default="", help="示例")
    p_record.add_argument("-a", "--alias", action="append", default=[])
    p_record.add_argument("-r", "--risk", default="safe", choices=["safe", "caution", "danger"])
    p_record.add_argument("-s", "--source", default="manual")
    p_record.add_argument("-h", "--help", action="store_true")
    p_record.set_defaults(func=cmd_record)

    p_stats = sub.add_parser("stats", add_help=False)
    p_stats.add_argument("-h", "--help", action="store_true")
    p_stats.set_defaults(func=cmd_stats)

    p_sync = sub.add_parser("sync", add_help=False)
    p_sync.add_argument("-h", "--help", action="store_true")
    p_sync.set_defaults(func=cmd_sync)

    p_promote = sub.add_parser("promote", add_help=False)
    p_promote.add_argument("-n", "--min-count", type=int, default=None, help="补录门槛")
    p_promote.add_argument("-h", "--help", action="store_true")
    p_promote.set_defaults(func=cmd_promote)

    p_combo = sub.add_parser("combo", add_help=False)
    p_combo.add_argument("combo_action", nargs="?", choices=["add", "list"], default="list")
    p_combo.add_argument("name", nargs="?", default="")
    p_combo.add_argument("-i", "--intent", default=None)
    p_combo.add_argument("-s", "--steps", nargs="*", default=[])
    p_combo.add_argument("-h", "--help", action="store_true")
    p_combo.set_defaults(func=cmd_combo)

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
