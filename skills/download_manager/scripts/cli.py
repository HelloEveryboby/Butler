#!/usr/bin/env python3
"""
下载管理器 — CLI 入口
"""

import os
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from aria2_manager import start_aria2, stop_aria2, is_running, get_status
from download_manager import DownloadManager


def main():
    parser = argparse.ArgumentParser(description="Butler 下载管理器")
    sub = parser.add_subparsers(dest="command", help="命令")

    # start
    sub.add_parser("start", help="启动 Aria2")

    # stop
    sub.add_parser("stop", help="停止 Aria2")

    # status
    sub.add_parser("status", help="查看状态")

    # download
    dl = sub.add_parser("download", aliases=["dl"], help="添加下载")
    dl.add_argument("url", help="下载链接 / 磁力链接 / 种子文件路径")
    dl.add_argument("--dir", "-d", help="下载目录")
    dl.add_argument("--name", "-n", help="保存文件名")

    # list
    sub.add_parser("list", aliases=["ls"], help="查看下载列表")

    # speed
    sub.add_parser("speed", help="查看当前速度")

    # pause / resume / remove
    op = sub.add_parser("pause", help="暂停任务")
    op.add_argument("gid", help="任务 GID")
    op = sub.add_parser("resume", help="恢复任务")
    op.add_argument("gid", help="任务 GID")
    op = sub.add_parser("remove", aliases=["rm"], help="删除任务")
    op.add_argument("gid", help="任务 GID")

    # limit
    lim = sub.add_parser("limit", help="设置限速")
    lim.add_argument("--download", "-d", default="0", help="下载限速 (如 1M, 500K, 0=无限制)")
    lim.add_argument("--upload", "-u", default="0", help="上传限速")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    dm = DownloadManager()

    if args.command == "start":
        result = dm.start()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "stop":
        result = dm.stop()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "status":
        print(json.dumps(get_status(), ensure_ascii=False, indent=2))

    elif args.command in ("download", "dl"):
        dm.ensure_running()
        url = args.url
        if url.endswith(".torrent") and os.path.exists(url):
            result = dm.add_torrent(url, args.dir)
        elif url.startswith("magnet:"):
            result = dm.add_magnet(url, args.dir)
        else:
            result = dm.add_url(url, args.name, args.dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command in ("list", "ls"):
        tasks = dm.get_all_tasks()
        speed = dm.get_speed()

        print(f"\n📥 下载速度: {_human(speed['download_speed'])}/s  "
              f"上传: {_human(speed['upload_speed'])}/s\n")

        if tasks["active"]:
            print("▶ 正在下载:")
            for t in tasks["active"]:
                print(f"  [{t['progress']:.1f}%] {t['filename']}")
                print(f"    {_human(t['completed_length'])}/{t['total_human']}  "
                      f"{t['speed_human']}  剩余 {t['remaining_human']}")
        if tasks["waiting"]:
            print("\n⏳ 等待中:")
            for t in tasks["waiting"]:
                print(f"  {t['filename'] or t['gid']}  {t['total_human']}")
        if tasks["stopped"]:
            print("\n✅ 已完成:")
            for t in tasks["stopped"][:10]:
                status = "✓" if t["status"] == "complete" else "✗"
                print(f"  {status} {t['filename']}  {t['total_human']}")
        if not any(tasks.values()):
            print("  暂无任务")

    elif args.command == "speed":
        speed = dm.get_speed()
        print(f"下载: {_human(speed['download_speed'])}/s")
        print(f"上传: {_human(speed['upload_speed'])}/s")
        print(f"活跃: {speed['num_active']}  等待: {speed['num_waiting']}  已完成: {speed['num_stopped']}")

    elif args.command == "pause":
        print("已暂停" if dm.pause(args.gid) else "暂停失败")

    elif args.command == "resume":
        print("已恢复" if dm.resume(args.gid) else "恢复失败")

    elif args.command in ("remove", "rm"):
        print("已删除" if dm.remove(args.gid, force=True) else "删除失败")

    elif args.command == "limit":
        dm.set_speed_limit(args.download, args.upload)
        print(f"限速已设置: 下载 {args.download} 上传 {args.upload}")


def _human(size: int) -> str:
    if size <= 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


if __name__ == "__main__":
    main()
