"""`butler hybrid` — 混合语言模块（BHL）的构建、状态与调用。"""

from __future__ import annotations

import argparse
import json
import sys

from butler.core.hybrid_hub import HybridHub
from butler.core.hybrid_scaffold import scaffold, supported_languages


def _hub() -> HybridHub:
    return HybridHub()


def _cmd_status(hub: HybridHub) -> int:
    rows = hub.status()
    if not rows:
        print("未发现 BHL 模块（programs/*/manifest.json）。")
        return 1

    print(f"{'模块':<26}{'语言':<8}{'已构建':<6}{'运行中':<6}方法")
    for row in rows:
        print(
            f"{row['name']:<26}{row['language']:<8}"
            f"{'是' if row['built'] else '否':<6}{'是' if row['running'] else '否':<6}"
            f"{', '.join(row['methods']) or '-'}"
        )
    built = [r for r in rows if r["built"]]
    langs = sorted({r["language"] for r in built})
    print(f"\n已构建 {len(built)}/{len(rows)} 个模块，语言: {', '.join(langs) or '无'}")
    return 0


def _cmd_build(hub: HybridHub, module: str | None, force: bool) -> int:
    results = hub.build(name=module, force=force)
    failed = 0
    for item in results:
        status = item["status"]
        print(f"[{status}] {item['module']}: {item.get('message', '')}")
        if status == "error":
            failed += 1
            detail = item.get("output")
            if detail:
                print("   " + detail.strip().splitlines()[-1])
    return 1 if failed else 0


def _cmd_call(hub: HybridHub, args) -> int:
    params = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as exc:
            print(f"params 不是合法 JSON: {exc}", file=sys.stderr)
            return 2

    envelope = hub.call(args.method, params, module=args.module, timeout=args.timeout)
    print(json.dumps(envelope, ensure_ascii=False, indent=2, default=str))
    return 0 if envelope.get("ok") else 1


def _cmd_new(args) -> int:
    try:
        result = scaffold(args.name, args.lang, programs_dir=args.dir)
    except ValueError as exc:
        print(f"创建失败: {exc}", file=sys.stderr)
        return 2

    print(f"已生成 {result['language']} 模块: {result['dir']}")
    print(f"  manifest: {result['manifest']}")
    print(f"  source:   {result['source']}")
    print("\n下一步:")
    print(f"  butler hybrid build {result['name']}")
    print(f"  butler hybrid call ping --module {result['name']}")
    return 0


def run_hybrid(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="butler hybrid", description="混合语言模块（BHL）工具")
    sub = parser.add_subparsers(dest="action")

    sub.add_parser("status", help="查看各语言模块的构建/运行状态")

    build_parser = sub.add_parser("build", help="按 manifest 构建模块")
    build_parser.add_argument("module", nargs="?", help="只构建指定模块")
    build_parser.add_argument("--force", action="store_true", help="已构建也强制重编")

    new_parser = sub.add_parser("new", help="生成一个新语言模块（manifest + 协议骨架）")
    new_parser.add_argument("name", help="模块名，如 image_ops")
    new_parser.add_argument("--lang", required=True, choices=supported_languages(), help="语言")
    new_parser.add_argument("--dir", help="生成目录（默认 programs/）")

    call_parser = sub.add_parser("call", help="调用一个 BHL 方法")
    call_parser.add_argument("method", help="方法名，如 get_system_info / factorize")
    call_parser.add_argument("--module", help="显式指定模块")
    call_parser.add_argument("--params", help="JSON 参数，如 '{\"number\": 97}'")
    call_parser.add_argument("--timeout", type=float, default=None)

    args = parser.parse_args(argv)
    if args.action == "new":
        return _cmd_new(args)
    hub = _hub()
    if args.action == "build":
        return _cmd_build(hub, args.module, args.force)
    if args.action == "call":
        return _cmd_call(hub, args)
    return _cmd_status(hub)
