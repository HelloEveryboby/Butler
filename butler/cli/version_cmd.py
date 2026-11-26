"""butler version — Git 式文件版本管理（快照 / 历史 / diff / 回滚）。"""

from __future__ import annotations

import argparse
import sys


def _store():
    from butler.core.version_store import version_store

    return version_store


def cmd_snapshot(args: argparse.Namespace) -> int:
    try:
        record = _store().snapshot(args.target, message=args.message or "")
    except Exception as exc:
        print(f"butler version: error: 建立版本点失败: {exc}", file=sys.stderr)
        return 1
    print(f"snapshot: {record['kind']} / {record['backend']} / {record['ref'][:12]}")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    rows = _store().list_versions(args.target)
    if not rows:
        print("（该文件暂无版本记录）")
        return 0
    for row in rows:
        print(
            f"#{row['id']:<4} {row['created_at']}  {row['kind']:<7} "
            f"{row['backend']:<8} {row['ref'][:12]}  {row['message']}"
        )
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    text = _store().diff(args.target, args.rev_a, args.rev_b)
    print(text or "（无差异或缺少可对比的版本）")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    try:
        _store().restore(args.target, args.rev)
    except Exception as exc:
        print(f"butler version: error: 回滚失败: {exc}", file=sys.stderr)
        return 1
    print(f"restored: {args.target} -> {args.rev}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    result = _store().prune(args.keep)
    print(
        f"prune: 删除 {result['deleted_records']} 条记录，"
        f"释放 {result['freed_bytes']} 字节"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler version",
        description="Git 式版本管理：文本走 Git，图片/视频走内容寻址快照",
        epilog=(
            "示例:\n"
            "  butler version snapshot report.docx -m '第二稿'\n"
            "  butler version log report.docx\n"
            "  butler version diff report.docx -f 3 -t 5\n"
            "  butler version restore report.docx -r 3\n"
            "  butler version prune -k 50"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_snap = sub.add_parser("snapshot", add_help=False, aliases=["save"])
    p_snap.add_argument("target")
    p_snap.add_argument("-m", "--message", default="", help="版本说明")
    p_snap.add_argument("-h", "--help", action="store_true")
    p_snap.set_defaults(func=cmd_snapshot)

    p_log = sub.add_parser("log", add_help=False, aliases=["history"])
    p_log.add_argument("target")
    p_log.add_argument("-h", "--help", action="store_true")
    p_log.set_defaults(func=cmd_log)

    p_diff = sub.add_parser("diff", add_help=False)
    p_diff.add_argument("target")
    p_diff.add_argument("-f", "--from", dest="rev_a", default=None, help="起始版本号")
    p_diff.add_argument("-t", "--to", dest="rev_b", default=None, help="结束版本号")
    p_diff.add_argument("-h", "--help", action="store_true")
    p_diff.set_defaults(func=cmd_diff)

    p_restore = sub.add_parser("restore", add_help=False)
    p_restore.add_argument("target")
    p_restore.add_argument("-r", "--rev", required=True, help="要回滚到的版本号")
    p_restore.add_argument("-h", "--help", action="store_true")
    p_restore.set_defaults(func=cmd_restore)

    p_prune = sub.add_parser("prune", add_help=False)
    p_prune.add_argument("-k", "--keep", type=int, default=None, help="每个目标保留的版本数")
    p_prune.add_argument("-h", "--help", action="store_true")
    p_prune.set_defaults(func=cmd_prune)

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
