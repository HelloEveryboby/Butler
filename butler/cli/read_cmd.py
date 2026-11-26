"""butler read — 通用朗读（文件/网页/剪贴板/管道，多音色、停顿、语速、续读）。"""

from __future__ import annotations

import argparse
import sys


def _resolve_input(args: argparse.Namespace) -> dict:
    """解析朗读来源：--text / --clipboard / 文件或 URL / 管道。"""
    from butler.core.reading.sources import read_clipboard

    if args.text:
        return {"text": args.text, "name": "命令行文本"}
    if args.clipboard:
        return {"text": read_clipboard(), "name": "剪贴板"}
    if args.file:
        return {"source": args.file}
    if not sys.stdin.isatty():
        return {"source": "-"}
    raise ValueError("请提供文件/网页 URL、--text 或 --clipboard")


def cmd_read(args: argparse.Namespace) -> int:
    from butler.core.reading import ReadingService

    service = ReadingService()
    try:
        spec = _resolve_input(args)
        if "text" in spec:
            info = service.open_text(
                spec["text"],
                name=spec["name"],
                role_map_path=args.role_map,
                default_rate=args.speed,
                ai=args.ai,
            )
        else:
            info = service.open(
                spec["source"],
                role_map_path=args.role_map,
                default_rate=args.speed,
                ai=args.ai,
            )
    except FileNotFoundError as exc:
        print(f"butler read: error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"butler read: error: 解析失败: {exc}", file=sys.stderr)
        return 1

    print(f"source: {info['path']}")
    print(f"segments: {info['segments']} 段  characters: {len(info['characters'])} 个")
    for name, voice in info["voices"].items():
        print(f"  - {name}: {voice}")
    if info.get("ai_tokens"):
        print(f"  llm_tokens: {info['ai_tokens']}")
    if info["resume_index"]:
        print(f"  resume: 上次读到第 {info['resume_index'] + 1} 段（--resume 继续）")

    if args.show_script:
        for segment in service.book["segments"]:
            print(f"   [{segment.index}] {segment.speaker} | {segment.kind}"
                  f" | 停顿 {segment.pause_before_ms}ms | x{segment.rate} | {segment.text}")

    export_only = args.dry_run or bool(args.out)
    if not (export_only or args.resume or args.start is not None or args.play):
        print("hint: 加 --play 播放，--resume 续读，--dry-run --out 导出音频。")
        return 0

    result = service.play_blocking(
        start=args.start,
        dry_run=export_only,
        out_path=args.out,
        resume=args.resume,
    )
    print(f"done: 已处理 {result['played']} 段；下次从第 {result['next_index'] + 1} 段继续")
    if result["output"]:
        import os

        size = os.path.getsize(result["output"])
        print(f"output: {result['output']} ({size} 字节，MP3 顺序拼接)")
        if size == 0:
            print("warning: 导出为空 — edge-tts 不可用或未联网（pip install edge-tts）")
    return 0


def cmd_voices(args: argparse.Namespace) -> int:
    from butler.core.reading.tts_edge import EdgeTTSEngine
    from butler.core.reading.voices import DEFAULT_FEMALE, DEFAULT_MALE

    engine = EdgeTTSEngine()
    voices = engine.list_voices()
    if voices:
        print("可用中文音色（edge-tts）：")
        for voice in voices:
            print(f"  {voice.get('ShortName')}  {voice.get('Gender')}  {voice.get('FriendlyName', '')}")
        return 0

    print("warning: edge-tts 不可用（未安装或离线），以下为配置中的本地音色池：")
    print("  女声: " + ", ".join(DEFAULT_FEMALE))
    print("  男声: " + ", ".join(DEFAULT_MALE))
    print("  安装: pip install edge-tts")
    return 0


def cmd_explain_tokens(args: argparse.Namespace) -> int:
    from butler.core.reading.sources import load_source
    from butler.core.reading.token_budget import explain_text, format_explain

    try:
        text, name = load_source(args.file)
        print(format_explain(explain_text(text, name)))
    except Exception as exc:
        print(f"butler read: error: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler read",
        description="通用朗读：多音色区分角色、自动停顿、按描述调速、断点续读",
        epilog=(
            "示例:\n"
            "  butler read novel.txt -p            # 播放本地文本\n"
            "  butler read 报告.docx -p            # Word\n"
            "  butler read 论文.pdf -p             # PDF（需有文字层）\n"
            "  butler read 书.epub -p              # EPUB\n"
            "  butler read 表.xlsx -p              # Excel\n"
            "  butler read 幻灯.pptx -p            # PowerPoint\n"
            "  butler read https://example.com -p  # 朗读网页正文\n"
            "  cat article.txt | butler read - -p  # 从标准输入朗读\n"
            "  butler read --clipboard -p          # 朗读剪贴板\n"
            "  butler read 报告.docx -r            # 从上次位置续读"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_read = sub.add_parser("read", add_help=False, aliases=["play"])
    p_read.add_argument("file", nargs="?", default=None,
                        help="文件路径（txt/md/docx/pdf/epub/xlsx/pptx 等）/ 网页 URL / '-'")
    p_read.add_argument("-t", "--text", default=None, help="直接朗读一段文本")
    p_read.add_argument("-c", "--clipboard", action="store_true", help="朗读剪贴板内容")
    p_read.add_argument("-r", "--resume", action="store_true", help="从上次位置继续")
    p_read.add_argument("-n", "--start", type=int, default=None, help="从第 N 段开始（0 基）")
    p_read.add_argument("-s", "--speed", type=float, default=None, help="全局语速倍率，默认 1.0")
    p_read.add_argument("-m", "--role-map", default=None, help="角色音色映射 JSON 文件")
    p_read.add_argument("-a", "--ai", action="store_true", help="用 LLM 推断角色性别（消耗 token）")
    p_read.add_argument("-p", "--play", action="store_true", help="立即播放（默认只解析）")
    p_read.add_argument("--dry-run", action="store_true", help="不播放，仅解析/统计")
    p_read.add_argument("-o", "--out", default=None, help="导出 MP3 路径（隐含不播放）")
    p_read.add_argument("-l", "--show-script", action="store_true", help="打印解析后的片段表")
    p_read.add_argument("-h", "--help", action="store_true")
    p_read.set_defaults(func=cmd_read)

    p_voices = sub.add_parser("voices", add_help=False)
    p_voices.add_argument("-h", "--help", action="store_true")
    p_voices.set_defaults(func=cmd_voices)

    p_tokens = sub.add_parser("explain-tokens", add_help=False)
    p_tokens.add_argument("file")
    p_tokens.add_argument("-h", "--help", action="store_true")
    p_tokens.set_defaults(func=cmd_explain_tokens)

    parser.set_defaults(func=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # 允许 `butler read 小说.txt` 或 `butler read -p 小说.txt` 直接使用
    known = {"read", "play", "voices", "explain-tokens"}
    if argv and argv[0] not in known and argv[0] not in ("-h", "--help"):
        argv = ["read", *argv]
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
