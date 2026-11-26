"""butler scan — 文档扫描（拍照/图片 → PDF，保留彩色勾画，可 OCR 转文本）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _write_text(text: str, pdf_path: str, fmt: str) -> Path:
    base = Path(pdf_path).with_suffix("")
    if fmt in ("txt", "md"):
        target = base.with_suffix("." + fmt)
        target.write_text(text, encoding="utf-8")
        return target
    if fmt == "docx":
        from docx import Document

        doc = Document()
        for line in text.splitlines():
            doc.add_paragraph(line)
        target = base.with_suffix(".docx")
        doc.save(target)
        return target
    raise ValueError(f"不支持的文本输出格式: {fmt}")


def cmd_scan(args: argparse.Namespace) -> int:
    from package.document.scanner import scan_images

    output = args.out or "scan_output.pdf"
    try:
        result = scan_images(
            args.images,
            output,
            mode=args.mode,
            keep_ink=args.keep_ink,
            dpi=args.dpi,
            correct=not args.no_correct,
        )
    except Exception as exc:
        print(f"butler scan: error: 扫描失败: {exc}", file=sys.stderr)
        return 1

    print(f"output: {result['output']}（{result['pages']} 页，{result['size']} 字节）")
    if args.keep_ink and args.mode == "color":
        print("   已保留原图彩色笔迹（-K/--no-keep-ink 可关闭）")

    if args.ocr:
        from package.document.scanner import ocr_text

        text = ocr_text(args.images)
        if text.strip():
            target = _write_text(text, output, args.to or "txt")
            print(f"ocr: {target}（{len(text)} 字符）")
            print("   提示：手写识别准确率有限，安装 scan-ocr 可选依赖可提升效果")
        else:
            print("warning: OCR 未识别出文字（可尝试更清晰的原图）")
    return 0


def cmd_camera(args: argparse.Namespace) -> int:
    from package.document.scanner import scan_from_camera

    output = args.out or "scan_camera.pdf"
    try:
        result = scan_from_camera(
            output,
            index=args.camera,
            mode=args.mode,
            keep_ink=args.keep_ink,
            dpi=args.dpi,
        )
    except Exception as exc:
        print(f"butler scan: error: 拍照失败: {exc}", file=sys.stderr)
        return 1
    print(f"output: {result['output']}（{result['pages']} 页）")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    from package.document.file_converter import convert_file

    source = Path(args.file).expanduser().resolve()
    if not source.is_file():
        print(f"butler scan: error: 文件不存在: {source}", file=sys.stderr)
        return 1
    if args.out:
        target = Path(args.out).expanduser()
    else:
        target = source.with_suffix("." + args.to.lstrip("."))
    try:
        convert_file(str(source), str(target), str(target.parent))
    except Exception as exc:
        print(f"butler scan: error: 转换失败: {exc}", file=sys.stderr)
        return 1
    print(f"output: {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler scan",
        description="文档扫描：图片/拍照 → PDF，保留彩色勾画，支持铅笔/碳笔增强与 OCR",
        epilog=(
            "示例:\n"
            "  butler scan page1.jpg page2.jpg -o doc.pdf\n"
            "  butler scan photo.jpg -m pencil -k -o sketch.pdf\n"
            "  butler scan camera -o shot.pdf -i 0\n"
            "  butler scan doc.pdf -t md"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_scan = sub.add_parser("scan", add_help=False, aliases=["image"])
    p_scan.add_argument("images", nargs="+", help="一张或多张图片路径（'-' 表示标准输入不可用）")
    p_scan.add_argument("-o", "--out", default=None, help="输出 PDF 路径（默认 scan_output.pdf）")
    p_scan.add_argument("-m", "--mode", default="color",
                        choices=["color", "gray", "bw", "pencil", "charcoal"],
                        help="增强模式（默认 color）")
    p_scan.add_argument("-k", "--keep-ink", dest="keep_ink", action="store_true", default=True,
                        help="保留彩色笔迹（默认开启）")
    p_scan.add_argument("-K", "--no-keep-ink", dest="keep_ink", action="store_false",
                        help="不保留彩色笔迹")
    p_scan.add_argument("-d", "--dpi", type=int, default=200, help="输出 DPI（默认 200）")
    p_scan.add_argument("-C", "--no-correct", action="store_true", help="跳过透视矫正")
    p_scan.add_argument("-O", "--ocr", action="store_true", help="追加 OCR 文本")
    p_scan.add_argument("-t", "--to", default="txt", choices=["txt", "md", "docx"],
                        help="OCR 文本输出格式")
    p_scan.add_argument("-h", "--help", action="store_true")
    p_scan.set_defaults(func=cmd_scan)

    p_cam = sub.add_parser("camera", add_help=False)
    p_cam.add_argument("-o", "--out", default=None, help="输出 PDF 路径（默认 scan_camera.pdf）")
    p_cam.add_argument("-i", "--camera", type=int, default=0, help="摄像头索引（默认 0）")
    p_cam.add_argument("-m", "--mode", default="color",
                       choices=["color", "gray", "bw", "pencil", "charcoal"])
    p_cam.add_argument("-k", "--keep-ink", dest="keep_ink", action="store_true", default=True)
    p_cam.add_argument("-K", "--no-keep-ink", dest="keep_ink", action="store_false")
    p_cam.add_argument("-d", "--dpi", type=int, default=200)
    p_cam.add_argument("-h", "--help", action="store_true")
    p_cam.set_defaults(func=cmd_camera)

    p_conv = sub.add_parser("convert", add_help=False)
    p_conv.add_argument("file", help="待转换文件")
    p_conv.add_argument("-t", "--to", required=True, help="目标格式，如 md/docx/txt/pdf")
    p_conv.add_argument("-o", "--out", default=None, help="输出路径（默认同目录同名）")
    p_conv.add_argument("-h", "--help", action="store_true")
    p_conv.set_defaults(func=cmd_convert)

    parser.set_defaults(func=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    known = {"scan", "image", "camera", "convert"}
    if argv and argv[0] not in known and argv[0] not in ("-h", "--help"):
        argv = ["scan", *argv]
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
