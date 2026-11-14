"""butler skill 命令 —— dsh 插件市场搬运的用户唯一入口。

Butler 侧可直接把 `butler skill ...` 映射到本 CLI：
    python3 -m butler_dsh skill install doc-reader

命令：
  skill install <spec>       安装插件（spec: 名称 | github:o/r | npm:pkg | 本地路径）
  skill uninstall <name>     卸载
  skill disable <name>       保留安装但停用（LLM 不可见）
  skill enable <name>        重新启用
  skill list                 已安装清单
  skill search <query>       市场搜索
  skill status               连接器能力表 + 本地安装清单（doctor 式总览）

通用选项：
  --plugins-dir <dir>   插件目录（默认 ./lib_external/dsh-plugins）
  --allow-ui            放行 UI/皮肤类插件（默认拒绝）
  --allow-source <glob> 来源白名单（可多次；未指定=不限制）
  --market-base <url>   市场索引基址（默认内置 / DSH_MARKET_BASE）
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .plugin_market import MarketError, PluginMarket
from .skill_registry import SkillRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler skill",
        description="DSH 插件市场搬运：下载、体检、启停、查看",
    )
    parser.add_argument("--plugins-dir", default=os.environ.get("DSH_PLUGINS_DIR", "lib_external/dsh-plugins"))
    parser.add_argument("--allow-ui", action="store_true", help="放行 UI/皮肤类插件")
    parser.add_argument("--allow-source", action="append", default=[], metavar="GLOB", help="来源白名单，可多次")
    parser.add_argument("--market-base", default="", help="市场索引基址")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("install", help="安装插件")
    p.add_argument("spec", help="名称 | github:owner/repo | npm:package | 本地路径")

    for name, help_text in [("uninstall", "卸载插件"), ("disable", "停用插件"), ("enable", "启用插件")]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("name")

    sub.add_parser("list", help="已安装清单")

    p = sub.add_parser("search", help="市场搜索")
    p.add_argument("query")

    sub.add_parser("status", help="连接器能力表 + 安装清单总览")
    return parser


def make_market(args: argparse.Namespace) -> PluginMarket:
    return PluginMarket(
        args.plugins_dir,
        market_base=args.market_base,
        allowed_sources=args.allow_source,
        allow_ui=args.allow_ui,
    )


def cmd_install(market: PluginMarket, spec: str) -> int:
    print(f"→ 安装 {spec}")
    info = market.install(spec)
    print(f"✅ {info.summary()}")
    for w in info.warnings:
        print(f"   ⚠️  {w}")
    if info.risk_hints:
        print(f"   📎 风险提示: {'；'.join(info.risk_hints)}（执行时由权限代理把关）")
    return 0


def cmd_list(market: PluginMarket) -> int:
    installed = market.list_installed()
    if not installed:
        print("（空）尚未安装任何插件。用: butler skill install <名称|github:o/r|npm:pkg>")
        return 0
    for e in installed:
        state = "启用" if e.get("enabled", True) else "停用"
        print(f"  [{state}] {e['name']} [{e.get('kind', 'tool')}] ver={e.get('version')} src={e['source']}")
    return 0


def cmd_status(market: PluginMarket) -> int:
    print("== 已安装插件 ==")
    cmd_list(market)
    print("\n== 连接器能力表（Butler LLM 可见的工具） ==")
    try:
        from .client import ConnectorClient

        addr = os.environ.get("BUTLER_DSH_SOCK", "")
        client = ConnectorClient(addr or None)
        client.start()
        client.wait_ready(timeout=5)
        registry = SkillRegistry()
        registry.sync(client.capabilities())
        client.close()
        for t in registry.tools_for_llm():
            fn = t["function"]
            print(f"  🔧 {fn['name']}: {fn['description'][:60]}")
        print(f"\n风险分布: {registry.risk_summary()}")
    except (OSError, TimeoutError, Exception) as exc:  # noqa: BLE001 状态命令尽量不崩
        print(f"  （连接器未运行或不可达: {exc}）")
        print("  启动: bash deploy/start-dsh-adapter.sh -config <connector.json>")
    return 0


COMMANDS = {"install", "uninstall", "disable", "enable", "list", "search", "status"}


def _strip_skill_token(argv: list[str]) -> list[str]:
    """兼容 butler skill install 的映射：剥离子命令前的字面量 "skill"。

    只处理第一个子命令之前的部分 —— `uninstall skill`（插件名叫 skill）
    这类命令参数绝不触碰。
    """
    try:
        cmd_idx = next(i for i, tok in enumerate(argv) if tok in COMMANDS)
    except StopIteration:
        return argv
    head = [tok for tok in argv[:cmd_idx] if tok != "skill"]
    return head + argv[cmd_idx:]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = _strip_skill_token(argv)
    args = build_parser().parse_args(argv)
    market = make_market(args)
    try:
        if args.command == "install":
            return cmd_install(market, args.spec)
        if args.command == "uninstall":
            ok = market.uninstall(args.name)
            print(f"{'✅ 已卸载' if ok else '❌ 未找到'}: {args.name}")
            return 0 if ok else 1
        if args.command in ("disable", "enable"):
            ok = market.set_enabled(args.name, args.command == "enable")
            print(f"{'✅' if ok else '❌'} {args.name} → {args.command}")
            return 0 if ok else 1
        if args.command == "list":
            return cmd_list(market)
        if args.command == "search":
            for info in market.search(args.query):
                print(f"  {info.name} ver={info.version}  {info.description[:60]}")
            return 0
        if args.command == "status":
            return cmd_status(market)
    except MarketError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
