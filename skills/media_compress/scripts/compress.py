#!/usr/bin/env python3
"""
图片视频压缩 — CLI 入口
Butler 调用接口，支持单文件/批量/分析
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Optional

# 添加当前目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from image_compress import (
    compress_image, analyze_image,
    IMAGE_EXTENSIONS, CompressMode, CompressResult
)
from video_compress import (
    compress_video, analyze_video, probe_video,
    VIDEO_EXTENSIONS
)
from report import print_single_report, print_batch_report, print_analyze_report

logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger("compress")


# ---------- 文件扫描 ----------
def scan_files(path: str, include_video: bool = True) -> List[str]:
    """扫描目录下的所有图片/视频文件"""
    path = os.path.abspath(path)
    all_ext = IMAGE_EXTENSIONS | (VIDEO_EXTENSIONS if include_video else set())

    if os.path.isfile(path):
        if Path(path).suffix.lower() in all_ext:
            return [path]
        return []

    files = []
    for root, dirs, filenames in os.walk(path):
        # 跳过隐藏目录
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in filenames:
            if Path(f).suffix.lower() in all_ext:
                files.append(os.path.join(root, f))

    return sorted(files)


def is_video(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


# ---------- 主逻辑 ----------
def run_compress(
    input_path: str,
    output: Optional[str] = None,
    mode: str = "visual-lossless",
    fmt: Optional[str] = None,
    quality: Optional[int] = None,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    suffix: str = "_compressed",
    analyze_only: bool = False,
    json_output: bool = False,
) -> str:
    """执行压缩或分析"""

    files = scan_files(input_path)
    if not files:
        return f"未找到可处理的文件: {input_path}"

    # 仅分析模式
    if analyze_only:
        results = []
        for f in files:
            if is_video(f):
                results.append(analyze_video(f))
            else:
                results.append(analyze_image(f))

        if json_output:
            return json.dumps(results, ensure_ascii=False, indent=2)

        lines = []
        for r in results:
            lines.append(print_analyze_report(r))
            lines.append("")
        return "\n".join(lines)

    # 压缩模式
    results = []

    for i, f in enumerate(files):
        logger.info(f"[{i+1}/{len(files)}] 处理: {os.path.basename(f)}")

        if is_video(f):
            # 视频：指定输出目录
            out_path = None
            if output:
                os.makedirs(output, exist_ok=True)
                p = Path(f)
                out_path = str(Path(output) / f"{p.stem}{suffix}{p.suffix}")

            result = compress_video(
                f, output_path=out_path, mode=mode, suffix=suffix,
            )
            results.append(result.to_dict())
        else:
            # 图片：只指定输出目录，格式由 image_compress 内部决定
            out_dir = output
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            result = compress_image(
                f, output_path=None, mode=mode,
                target_format=fmt, quality=quality,
                max_width=max_width, max_height=max_height,
                suffix=suffix,
            )

            # 如果指定了输出目录，移动文件
            if out_dir and result.success and result.output_path:
                import shutil
                src = result.output_path
                dst_name = Path(result.output_path).name
                dst = str(Path(out_dir) / dst_name)
                # 文件名冲突时加序号
                if os.path.exists(dst):
                    stem = Path(dst_name).stem
                    ext = Path(dst_name).suffix
                    counter = 1
                    while os.path.exists(dst):
                        dst = str(Path(out_dir) / f"{stem}_{counter}{ext}")
                        counter += 1
                shutil.move(src, dst)
                result.output_path = dst

            results.append(result.to_dict())

    if json_output:
        return json.dumps(results, ensure_ascii=False, indent=2)

    return print_batch_report(results)


# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(
        description="图片视频无损压缩",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s photo.png                           # 视觉无损压缩
  %(prog)s photo.png --mode lossless           # 无损压缩
  %(prog)s /path/to/photos --mode high         # 高压缩整个目录
  %(prog)s photo.png --format webp --quality 80  # 转 WebP 质量 80
  %(prog)s /path/to/photos --analyze           # 仅分析不压缩
  %(prog)s photo.png --max-width 1920          # 缩放 + 压缩
        """
    )

    parser.add_argument("input", help="输入文件或目录")
    parser.add_argument("--output", "-o", help="输出目录（默认：原目录）")
    parser.add_argument("--mode", "-m", default="visual-lossless",
                        choices=["lossless", "visual-lossless", "high"],
                        help="压缩模式（默认: visual-lossless）")
    parser.add_argument("--format", "-f", help="目标格式（png/jpg/webp，保持原格式则不指定）")
    parser.add_argument("--quality", "-q", type=int, help="质量 1-100（按模式自动）")
    parser.add_argument("--max-width", type=int, help="最大宽度（超出等比缩放）")
    parser.add_argument("--max-height", type=int, help="最大高度（超出等比缩放）")
    parser.add_argument("--suffix", "-s", default="_compressed", help="输出文件后缀（默认 _compressed）")
    parser.add_argument("--analyze", "-a", action="store_true", help="仅分析，不压缩")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--video", action="store_true", default=True, help="包含视频（默认开启）")
    parser.add_argument("--no-video", action="store_true", help="不处理视频")

    args = parser.parse_args()

    output = run_compress(
        input_path=args.input,
        output=args.output,
        mode=args.mode,
        fmt=args.format,
        quality=args.quality,
        max_width=args.max_width,
        max_height=args.max_height,
        suffix=args.suffix,
        analyze_only=args.analyze,
        json_output=args.json,
    )

    print(output)


if __name__ == "__main__":
    main()
