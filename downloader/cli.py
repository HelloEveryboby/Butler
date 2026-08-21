# -*- coding: utf-8 -*-
"""
Linux 风格 CLI / Rich TUI 终端下载器模块
支持命令：
  butler download <URL> [存放位置] [-o OUTPUT] [-d]
  下载 <URL> [存放位置]
"""

import sys
import os
import time
import argparse
import threading
import subprocess

# Ensure rich is available for premium TUI rendering
try:
    from rich.console import Console
    from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TaskProgressColumn
    from rich.panel import Panel
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from downloader import SegmentedDownloader, format_bytes, calculate_eta, load_tasks, save_tasks


def download_cli(url: str, output_dir: str = None, daemon: bool = False, category: str = "other"):
    """
    Linux 风格 CLI / TUI 资源下载处理入口函数。
    :param url: 资源下载链接 (HTTP/HTTPS/Magnet/Thunder)
    :param output_dir: 目标保存位置 (若未指定则默认为 ./download/)
    :param daemon: 是否以后台守护进程形式下载
    :param category: 任务分类
    """
    # 1. 路径自动补全与创建 (mkdir -p)
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), "download")
    else:
        output_dir = os.path.expanduser(output_dir)
        if not os.path.isabs(output_dir):
            output_dir = os.path.abspath(os.path.join(os.getcwd(), output_dir))

    # 无论默认路径还是自定义路径，目标目录不存在时自动执行 mkdir -p 递归创建
    os.makedirs(output_dir, exist_ok=True)

    # 提取文件名
    from urllib.parse import urlparse, unquote
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path) or "downloaded_file"
    filename = unquote(filename)

    file_path = os.path.join(output_dir, filename)
    task_id = f"dl_cli_{int(time.time() * 1000)}"

    # 将任务存入 tasks.json 以供 UI 与存储共享
    tasks = load_tasks()
    tasks[task_id] = {
        "id": task_id,
        "url": url,
        "name": filename,
        "status": "pending",
        "total_size": 0,
        "downloaded_size": 0,
        "progress": 0,
        "speed": "0 B/s",
        "eta": "开始中...",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "file_path": file_path,
        "category": category,
        "is_p2p": False,
        "scheduled_time": None,
        "speed_limited": False
    }
    save_tasks(tasks)

    # 2. 守护进程模式 (-d / --daemon)
    if daemon:
        # 在后台以独立子进程启动下载任务
        cmd = [sys.executable, "-m", "downloader.cli", url, "-o", output_dir]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        print(f"🚀 [后台守护进程] 任务已送入后台下载 (PID: {proc.pid})")
        print(f"📂 存放位置: {file_path}")
        return task_id

    # 3. 前台交互模式 (Rich TUI 动态进度)
    print("=" * 65)
    print(f"🚀 Butler 资源下载器 (Linux 风格 CLI / Rich TUI 模式)")
    print(f"🔗 资源 URL : {url}")
    print(f"📂 存放位置 : {file_path} (目录已自动建立)")
    print("=" * 65)

    downloader = SegmentedDownloader(
        task_id=task_id,
        url=url,
        file_path=file_path,
        max_workers=16
    )

    stop_flag = threading.Event()
    downloader.stop_event = stop_flag

    # 在单独线程启动下载引擎
    dl_thread = threading.Thread(target=downloader.run, daemon=True)
    dl_thread.start()

    # 4. Rich TUI 渲染主循环
    if HAS_RICH:
        console = Console()
        try:
            with Live(console=console, refresh_per_second=4) as live:
                while dl_thread.is_alive() and not stop_flag.is_set():
                    time.sleep(0.25)
                    progress = int((downloader.downloaded_size / downloader.total_size) * 100) if downloader.total_size > 0 else 0
                    speed_str = format_bytes(int(downloader.speed)) + "/s"
                    eta_str = calculate_eta(downloader.downloaded_size, downloader.total_size, downloader.speed)
                    downloaded_fmt = format_bytes(downloader.downloaded_size)
                    total_fmt = format_bytes(downloader.total_size) if downloader.total_size > 0 else "未知大小"

                    # 渲染多线程分片进度图块 (16个分片)
                    max_workers = downloader.max_workers
                    if downloader.supports_range and downloader.total_size > 0:
                        downloaded_ratio = downloader.downloaded_size / downloader.total_size
                        filled_blocks = int(downloaded_ratio * max_workers)
                        blocks = "█" * filled_blocks + "░" * (max_workers - filled_blocks)
                        chunk_str = f"[{blocks}] ({filled_blocks}/{max_workers} 分片已载入)"
                    else:
                        chunk_str = "[单线程顺序写入中]"

                    table = Table(show_header=False, expand=True, box=None)
                    table.add_column("Key", style="bold cyan", width=16)
                    table.add_column("Value", style="bold white")

                    table.add_row("文件名", filename)
                    table.add_row("整体进度", f"{progress}% [{downloaded_fmt} / {total_fmt}]")
                    table.add_row("分片图谱", chunk_str)
                    table.add_row("实时网速", f"[bold green]{speed_str}[/bold green]")
                    table.add_row("剩余时间 (ETA)", eta_str)

                    # 简易进度条
                    bar_width = 30
                    bar_filled = int((progress / 100) * bar_width)
                    progress_bar = f"[{'#' * bar_filled}{'-' * (bar_width - bar_filled)}]"
                    table.add_row("进度仪表盘", progress_bar)

                    panel = Panel(
                        table,
                        title="[bold blue]⚡ 多线程并发下载控制器[/bold blue]",
                        subtitle="[dim]按下 Ctrl+C 可停止任务[/dim]"
                    )
                    live.update(panel)

        except KeyboardInterrupt:
            stop_flag.set()
            print("\n⚠️ 下载已被用户中途中断。")
            return task_id
    else:
        # ANSI 控制台 Fallback 模式
        try:
            while dl_thread.is_alive() and not stop_flag.is_set():
                time.sleep(0.5)
                progress = int((downloader.downloaded_size / downloader.total_size) * 100) if downloader.total_size > 0 else 0
                speed_str = format_bytes(int(downloader.speed)) + "/s"
                eta_str = calculate_eta(downloader.downloaded_size, downloader.total_size, downloader.speed)
                downloaded_fmt = format_bytes(downloader.downloaded_size)
                total_fmt = format_bytes(downloader.total_size) if downloader.total_size > 0 else "未知"

                sys.stdout.write(f"\r⏬ 下载中: {progress}% [{downloaded_fmt}/{total_fmt}] | 网速: {speed_str} | ETA: {eta_str}   ")
                sys.stdout.flush()
            print()
        except KeyboardInterrupt:
            stop_flag.set()
            print("\n⚠️ 下载已被用户中途中断。")
            return task_id

    # 任务完成校验
    if downloader.error_message:
        print(f"\n❌ 下载失败: {downloader.error_message}")
    else:
        print(f"\n✅ [下载完成] 文件已成功存入: {file_path}")

    return task_id


def build_cli_parser():
    """构建 Linux 风格的下载命令行解析器."""
    parser = argparse.ArgumentParser(
        description="Butler Linux 风格命令行下载器",
        prog="butler download"
    )
    parser.add_argument("url", help="要下载的资源 URL 链接")
    parser.add_argument("pos_output", nargs="?", default=None, help="目标保存目录 (可选，默认为 ./download/)")
    parser.add_argument("-o", "--output", dest="flag_output", default=None, help="目标保存目录 (Linux 风格选项)")
    parser.add_argument("-d", "--daemon", action="store_true", help="是否在后台以守护进程模式运行下载")
    return parser


def main():
    parser = build_cli_parser()
    args = parser.parse_args()

    # 路径判定：优先使用 -o / --output，其次位置参数 pos_output
    target_out = args.flag_output or args.pos_output
    download_cli(args.url, output_dir=target_out, daemon=args.daemon)


if __name__ == "__main__":
    main()
