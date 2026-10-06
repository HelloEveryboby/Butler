"""翻译系统 CLI。

用法：
    python -m package.document.translate_system.cli translate "text" --to zh-CN
    python -m package.document.translate_system.cli export in.pdf --to zh-CN -o out.pdf
    python -m package.document.translate_system.cli export in.epub --to zh-CN -o out.epub
    python -m package.document.translate_system.cli export in.srt --to zh-CN -o out.srt
    python -m package.document.translate_system.cli tm stats
    python -m package.document.translate_system.cli providers list|test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_system(args):
    from . import get_default_system
    system = get_default_system()
    if getattr(args, "offline", False):
        system.config.offline_mode = True
        system.reload_providers()
    if getattr(args, "preset", None):
        system.set_preset(args.preset)
    return system


def cmd_translate(args) -> int:
    system = _build_system(args)
    text = args.text
    if text == "-":
        text = sys.stdin.read()
    if getattr(args, "context", False):
        system.begin_document(text, to=args.to)
    result = system.translate(text, to=args.to, use_context=getattr(args, "context", False))
    print(result)
    return 0


def cmd_export(args) -> int:
    from .doc_export import export_bilingual
    system = _build_system(args)
    input_path = Path(args.input)
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(
            f"{input_path.stem}.bilingual{input_path.suffix}")

    def _progress(done: int, total: int) -> None:
        if total:
            sys.stderr.write(f"\r翻译进度: {done}/{total}")
            sys.stderr.flush()
            if done >= total:
                sys.stderr.write("\n")

    if getattr(args, "context", False):
        # 每篇文档一次 LLM 上下文调用，整篇共享
        try:
            system.begin_document(input_path.read_text(encoding="utf-8", errors="replace"),
                                  to=args.to)
        except Exception:  # noqa: BLE001
            pass

    out = export_bilingual(
        str(input_path), str(output_path), args.to,
        source_lang=args.source, engine=system,
        progress_cb=_progress, use_context=getattr(args, "context", False))
    print(f"已导出双语文件: {out}")
    return 0


def cmd_tm(args) -> int:
    system = _build_system(args)
    if args.tm_command == "stats":
        stats = system.tm.stats()
        print(f"翻译记忆库后端: {stats['backend']}")
        print(f"条目总数: {stats['entries']}")
        print(f"复用阈值: {stats['reuse_threshold']}  few-shot 阈值: {stats['fewshot_threshold']}")
        for lang, count in stats["by_lang"].items():
            print(f"  - {lang}: {count} 条")
        if stats["recent"]:
            print("最近条目：")
            for e in stats["recent"]:
                print(f"  [{e['to_lang']}] {e['source'][:40]!r} → {e['target'][:40]!r}")
        return 0
    return 1


def cmd_providers(args) -> int:
    from .providers import create_provider
    system = _build_system(args)

    if args.providers_command == "list":
        print("已配置翻译源：")
        for p in system.config.providers:
            mark = "*" if p.id in system.config.fallback_chain else " "
            state = "启用" if p.enabled else "禁用"
            local = " [本地]" if p.type == "local-llm" else ""
            print(f" {mark} {p.id} ({p.type}{local}, {state}) - {p.name}")
        print("（* 在降级链中）")
        if system.config.offline_mode:
            print("当前为离线模式：只允许本地源。")
        return 0

    if args.providers_command == "test":
        print("连通性测试：")
        probe = "hello"
        for p in system.config.providers:
            if not p.enabled:
                print(f"  - {p.id}: 跳过（禁用）")
                continue
            try:
                provider = create_provider(p)
                result = provider.translate(probe, "en", "zh-CN")
                print(f"  - {p.id}: OK → {result[:30]!r}")
            except Exception as e:  # noqa: BLE001
                print(f"  - {p.id}: 失败（{e}）")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="translate_system",
        description="Butler 翻译系统 CLI",
    )
    sub = parser.add_subparsers(dest="command")

    p_translate = sub.add_parser("translate", help="翻译一段文本")
    p_translate.add_argument("text", help="待译文本（- 表示从 stdin 读取）")
    p_translate.add_argument("--to", default=None, help="目标语言代码，如 zh-CN")
    p_translate.add_argument("--preset", default=None, help="专家预设 id，如 tech / legal")
    p_translate.add_argument("--context", action="store_true", help="启用 AI 上下文翻译")
    p_translate.add_argument("--offline", action="store_true", help="离线模式（只用本地源）")
    p_translate.set_defaults(func=cmd_translate)

    p_export = sub.add_parser("export", help="导出双语文件（pdf/epub/srt/vtt/md/txt/html）")
    p_export.add_argument("input", help="输入文件路径")
    p_export.add_argument("-o", "--output", default=None, help="输出文件路径")
    p_export.add_argument("--to", default="zh-CN", help="目标语言代码")
    p_export.add_argument("--source", default="auto", help="源语言代码，默认 auto")
    p_export.add_argument("--preset", default=None, help="专家预设 id")
    p_export.add_argument("--context", action="store_true", help="启用 AI 上下文翻译")
    p_export.add_argument("--offline", action="store_true", help="离线模式（只用本地源）")
    p_export.set_defaults(func=cmd_export)

    p_tm = sub.add_parser("tm", help="翻译记忆库")
    tm_sub = p_tm.add_subparsers(dest="tm_command")
    tm_sub.add_parser("stats", help="查看 TM 统计")
    p_tm.set_defaults(func=cmd_tm)

    p_providers = sub.add_parser("providers", help="翻译源管理")
    providers_sub = p_providers.add_subparsers(dest="providers_command")
    providers_sub.add_parser("list", help="列出翻译源")
    providers_sub.add_parser("test", help="测试翻译源连通性")
    p_providers.set_defaults(func=cmd_providers)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None) or not getattr(args, "func", None):
        parser.print_help()
        return 1
    if args.command == "tm" and not getattr(args, "tm_command", None):
        parser.parse_args(["tm", "--help"])
        return 1
    if args.command == "providers" and not getattr(args, "providers_command", None):
        parser.parse_args(["providers", "--help"])
        return 1

    # 统一错误出口：不要把 traceback 丢给用户，
    # 尤其是“没有可用翻译源”这种应该用人话说清楚的失败。
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"错误：{exc}", file=sys.stderr)
        hint = _troubleshoot_hint(str(exc))
        if hint:
            print(f"建议：{hint}", file=sys.stderr)
        return 2


def _troubleshoot_hint(message: str) -> str:
    """按错误特征给一条可操作的建议。"""
    text = message.lower()
    if "404" in text or "translate/auth" in text or "unreachable" in text:
        return "免费翻译源在当前网络不可达，请改用需要 Key 的源（如 DeepSeek）或开启 --offline 走本地 LLM。"
    if "api key" in text or "401" in text or "unauthorized" in text:
        return "请在配置里填写对应翻译源的 API Key。"
    if "connection" in text or "timeout" in text or "refused" in text:
        return "网络或本地服务未就绪；若使用本地 LLM，请先启动（例如 `ollama serve`）。"
    if "no enabled" in text or "no provider" in text:
        return "没有启用任何翻译源，请先用 `providers list` 查看并启用一个。"
    return ""


if __name__ == "__main__":
    sys.exit(main())
