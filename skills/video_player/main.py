#!/usr/bin/env python3
"""
Butler Video Player — 独立启动入口

用法：
    # 直接播放视频文件
    python main.py ~/Videos/movie.mkv

    # 播放多个视频（自动加入播放列表）
    python main.py video1.mp4 video2.mkv video3.avi

    # 播放目录下所有视频
    python main.py ~/Videos/

    # 不传参数，打开媒体库界面
    python main.py

    # 指定配置文件
    python main.py --config ./my_config.json movie.mp4

    # 从指定时间开始播放（秒）
    python main.py --start 300 movie.mp4

    # 注册文件关联（首次使用时执行一次）
    python main.py --register

    # 取消文件关联
    python main.py --unregister
"""

import os
import sys
import json
import time
import signal
import asyncio
import logging
import argparse
import threading
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.video_player.player_adapter import PlayerState, create_player
from skills.video_player.db import VideoDatabase
from skills.video_player.library import MediaLibrary
from skills.video_player.controller import PlaybackController
from skills.video_player.scanner import VideoScanner
from skills.video_player.metadata import MetadataExtractor

# ── 日志 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("butler-player")


def load_config(config_path: str = None) -> dict:
    """加载配置"""
    default = {
        "player": {
            "preferred": "mpv",
            "fallback_chain": ["mpv", "vlc", "ffplay", "system"],
            "mpv": {
                "vo": "gpu",
                "hwdec": "auto",
                "gpu_api": "auto",
                "cache": "yes",
                "demuxer_max_bytes": "150M",
                "sub_auto": "fuzzy",
                "sub_font_size": 42,
                "audio_channels": "stereo",
                "cursor_autohide": 1000,
                "keep_open": "yes",
            },
        },
        "library": {
            "scan_dirs": ["~/Videos", "~/Movies", "~/Downloads"],
            "scan_recursive": True,
        },
        "playback": {
            "default_volume": 80,
            "default_speed": 1.0,
            "resume_enabled": True,
            "resume_save_interval_sec": 5,
            "auto_play_next": True,
            "preferred_audio_lang": "chi",
            "preferred_subtitle_lang": "chi",
            "auto_subtitle_if_missing": True,
            "screenshot_dir": "~/Pictures/ButlerScreenshots",
        },
        "cache": {
            "db_path": "~/.butler/data/video_library.db",
        },
    }

    # 尝试加载用户配置
    config_files = []
    if config_path:
        config_files.append(config_path)
    config_files.extend([
        os.path.expanduser("~/.butler/video_player.json"),
        os.path.join(os.path.dirname(__file__), "config.json"),
    ])

    for cf in config_files:
        if os.path.isfile(cf):
            try:
                with open(cf, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                _deep_merge(default, user_cfg)
                logger.info(f"已加载配置: {cf}")
                break
            except Exception as e:
                logger.warning(f"配置加载失败 [{cf}]: {e}")

    return default


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def collect_video_files(paths: list[str]) -> list[str]:
    """
    收集视频文件路径。
    支持：单文件、多文件、目录（递归扫描）。
    """
    scanner = VideoScanner()
    result = []

    for p in paths:
        p = os.path.expanduser(p)
        if os.path.isfile(p):
            if scanner._is_video_file(p):
                result.append(os.path.abspath(p))
            else:
                logger.warning(f"不是支持的视频文件: {p}")
        elif os.path.isdir(p):
            scanner.scan_dirs = [p]
            found = scanner.scan_all()
            result.extend(found)
            logger.info(f"目录 {p} 下发现 {len(found)} 个视频")
        else:
            logger.warning(f"路径不存在: {p}")

    return result


def register_file_associations():
    """注册文件关联"""
    from skills.video_player.register import register
    register()


def unregister_file_associations():
    """取消文件关联"""
    from skills.video_player.register import unregister
    unregister()


class StandalonePlayer:
    """
    独立播放器 — 无需 Butler 框架，直接运行。
    支持：
    - 命令行传入视频文件路径
    - 断点续播
    - 多文件自动播放列表
    - 媒体库管理
    - 内置 HTTP API（可选）
    """

    def __init__(self, config: dict):
        self.config = config
        self.running = True

        # 初始化数据库
        db_path = os.path.expanduser(config["cache"]["db_path"])
        self.db = VideoDatabase(db_path)

        # 初始化媒体库
        self.library = MediaLibrary(self.db, config)

        # 初始化播放控制器
        self.controller = PlaybackController(self.db, self.library, config)

        # 注册事件
        self.controller._ensure_player()
        self.controller._player.on_state_change(self._on_state)
        self.controller._player.on_end_reached(self._on_end)

    def _on_state(self, state: PlayerState):
        icons = {
            PlayerState.PLAYING: "▶",
            PlayerState.PAUSED: "⏸",
            PlayerState.BUFFERING: "⏳",
            PlayerState.ENDED: "⏹",
            PlayerState.ERROR: "❌",
        }
        icon = icons.get(state, "●")
        if state == PlayerState.PLAYING:
            pos = self.controller._player.get_position()
            dur = self.controller._player.get_duration()
            logger.info(f"{icon} 播放中 {format_time(pos)} / {format_time(dur)}")
        elif state == PlayerState.PAUSED:
            logger.info(f"{icon} 已暂停")

    def _on_end(self):
        logger.info("播放结束")

    def play_files(self, file_paths: list[str], start_time: float = 0):
        """
        播放文件列表。
        单文件直接播放，多文件自动构建播放列表。
        """
        if not file_paths:
            logger.error("没有可播放的视频文件")
            return

        # 确保文件已入库
        video_ids = []
        for fp in file_paths:
            existing = self.db.get_video_by_path(fp)
            if existing:
                video_ids.append(existing["id"])
            else:
                # 提取元数据并入库
                extractor = MetadataExtractor()
                meta = extractor.extract_sync(fp)
                if meta:
                    vid = self.db.insert_video(meta.to_dict())
                    video_ids.append(vid)
                    logger.info(f"入库: {meta.title} ({meta.container} {meta.video_codec})")
                else:
                    logger.warning(f"元数据提取失败: {fp}")

        if not video_ids:
            logger.error("没有有效的视频文件")
            return

        # 单文件：直接播放
        if len(video_ids) == 1:
            result = self.controller.play_video(video_ids[0], resume=(start_time == 0))
            if start_time > 0:
                self.controller.seek(start_time)
            self._print_play_info(result)
        else:
            # 多文件：构建播放列表并播放第一个
            playlist_id = self.db.create_playlist(
                f"临时播放列表 {time.strftime('%H:%M')}"
            )
            for vid in video_ids:
                self.db.add_to_playlist(playlist_id, vid)

            result = self.controller.play_playlist(playlist_id, start_index=0)
            if start_time > 0:
                self.controller.seek(start_time)
            self._print_play_info(result)
            logger.info(f"播放列表: {len(video_ids)} 个视频")

    def _print_play_info(self, result: dict):
        """打印播放信息"""
        if "error" in result:
            logger.error(f"播放失败: {result['error']}")
            return
        logger.info(f"正在播放: {result.get('title', '未知')}")
        logger.info(f"  格式: {result.get('container', '?').upper()} "
                     f"{result.get('video_codec', '?').upper()} + "
                     f"{result.get('audio_codec', '?').upper()}")
        logger.info(f"  分辨率: {result.get('resolution', '?')}")
        if result.get("resume_from", 0) > 0:
            logger.info(f"  续播: {format_time(result['resume_from'])}")

    def scan_library(self):
        """扫描媒体库"""
        logger.info("开始扫描媒体库...")
        result = asyncio.run(self.library.full_scan())
        logger.info(
            f"扫描完成: 共 {result['total']} 个文件, "
            f"新增 {result['added']}, 跳过 {result['skipped']}"
        )

    def show_library(self):
        """显示媒体库列表"""
        videos = self.db.get_all_videos(order_by="title ASC", limit=100)
        if not videos:
            print("\n媒体库为空，请先扫描: python main.py --scan\n")
            return

        stats = self.db.get_stats()
        print(f"\n{'='*70}")
        print(f"  Butler 媒体库  |  {stats['video_count']} 个视频  |  "
              f"{stats['total_size_gb']} GB  |  {stats['total_duration_hours']}h")
        print(f"{'='*70}")
        print(f"  {'#':<4} {'标题':<30} {'分辨率':<10} {'编码':<10} {'时长':<8} {'大小':<8}")
        print(f"  {'-'*4} {'-'*30} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")

        for i, v in enumerate(videos, 1):
            res = f"{v['height']}p" if v.get("height") else "-"
            codec = (v.get("video_codec") or "-").upper()
            dur = format_time(v.get("duration", 0))
            size = format_size(v.get("file_size", 0))
            fav = "❤️" if v.get("is_favorite") else "  "
            print(f"  {i:<4} {v['title'][:30]:<30} {res:<10} {codec:<10} {dur:<8} {size:<8} {fav}")

        print(f"\n  播放: python main.py <文件路径>")
        print(f"  扫描: python main.py --scan\n")

    def run_interactive(self):
        """交互模式（不传文件参数时）"""
        self.show_library()
        print("  输入视频编号播放，输入 q 退出，输入 s 扫描\n")

        while self.running:
            try:
                cmd = input("butler> ").strip()
                if not cmd:
                    continue
                if cmd in ("q", "quit", "exit"):
                    break
                if cmd in ("s", "scan"):
                    self.scan_library()
                    self.show_library()
                    continue
                if cmd in ("l", "list", "ls"):
                    self.show_library()
                    continue
                if cmd in ("h", "help"):
                    print_help()
                    continue

                # 尝试解析为数字（视频编号）
                try:
                    idx = int(cmd) - 1
                    videos = self.db.get_all_videos(order_by="title ASC", limit=1000)
                    if 0 <= idx < len(videos):
                        self.controller.play_video(videos[idx]["id"])
                    else:
                        print(f"  无效编号: {cmd}")
                    continue
                except ValueError:
                    pass

                # 尝试作为文件路径
                if os.path.isfile(os.path.expanduser(cmd)):
                    self.play_files([os.path.expanduser(cmd)])
                    continue

                # 尝试搜索
                results = self.db.search_videos(cmd)
                if results:
                    print(f"\n  搜索 \"{cmd}\" 的结果:")
                    for i, v in enumerate(results[:10], 1):
                        print(f"    {i}. {v['title']}")
                    print()
                else:
                    print(f"  未找到: {cmd}")

            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                break

        self.shutdown()

    def shutdown(self):
        """清理退出"""
        logger.info("正在退出...")
        self.controller.destroy()
        self.db.close()
        self.running = False


def format_time(seconds: float) -> str:
    if not seconds or seconds < 0:
        return "00:00"
    s = int(seconds)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def format_size(bytes_val: int) -> str:
    if not bytes_val or bytes_val <= 0:
        return "-"
    gb = bytes_val / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.1f}GB"
    return f"{bytes_val / (1024 ** 2):.0f}MB"


def print_help():
    print("""
  Butler Video Player — 独立播放器

  用法:
    python main.py <视频文件>              播放单个视频
    python main.py <文件1> <文件2> ...     播放多个视频（自动播放列表）
    python main.py <目录>                  播放目录下所有视频
    python main.py                         打开媒体库界面

  参数:
    --config <路径>       指定配置文件
    --start <秒>          从指定时间开始播放
    --scan                扫描媒体库
    --list / --ls         显示媒体库列表
    --register            注册文件关联（双击打开）
    --unregister          取消文件关联
    --no-resume           不使用断点续播（从头播放）
    -h / --help           显示帮助

  播放中快捷键:
    Space                 暂停/继续
    ← / →                 快退/快进 5 秒
    Shift+← / Shift+→     快退/快进 30 秒
    ↑ / ↓                 音量 +/-5%
    M                     静音
    N / P                 下一集 / 上一集
    [ / ]                 倍速 -0.25 / +0.25
    \\                     恢复 1.0x
    S                     截图
    C                     字幕开关
    Q                     退出
""")


def main():
    parser = argparse.ArgumentParser(
        description="Butler Video Player — 本地原生视频播放器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("files", nargs="*", help="视频文件或目录路径")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--start", type=float, default=0, help="起始播放时间（秒）")
    parser.add_argument("--scan", action="store_true", help="扫描媒体库")
    parser.add_argument("--list", "--ls", action="store_true", help="显示媒体库列表")
    parser.add_argument("--register", action="store_true", help="注册文件关联")
    parser.add_argument("--unregister", action="store_true", help="取消文件关联")
    parser.add_argument("--no-resume", action="store_true", help="不使用断点续播")
    parser.add_argument("-h", "--help", action="store_true", help="显示帮助")

    args = parser.parse_args()

    # 帮助
    if args.help:
        print_help()
        return

    # 文件关联注册
    if args.register:
        register_file_associations()
        return

    if args.unregister:
        unregister_file_associations()
        return

    # 加载配置
    config = load_config(args.config)

    if args.no_resume:
        config["playback"]["resume_enabled"] = False

    # 扫描模式
    if args.scan:
        player = StandalonePlayer(config)
        player.scan_library()
        player.db.close()
        return

    # 列表模式
    if args.list:
        player = StandalonePlayer(config)
        player.show_library()
        player.db.close()
        return

    # 收集视频文件
    if args.files:
        video_files = collect_video_files(args.files)
        if not video_files:
            logger.error("未找到可播放的视频文件")
            sys.exit(1)

        player = StandalonePlayer(config)

        # 信号处理：Ctrl+C 优雅退出
        def sig_handler(sig, frame):
            player.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, sig_handler)

        player.play_files(video_files, start_time=args.start)

        # 等待播放结束（mpv 事件循环在后台线程）
        try:
            while player.running:
                time.sleep(0.5)
                state = player.controller._player.get_state()
                if state in (PlayerState.IDLE, PlayerState.ENDED):
                    # 检查是否还有播放列表中的下一集
                    if player.controller._current_playlist:
                        continue
                    break
        except KeyboardInterrupt:
            pass

        player.shutdown()
    else:
        # 无参数：交互模式
        player = StandalonePlayer(config)

        def sig_handler(sig, frame):
            player.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, sig_handler)

        player.run_interactive()


if __name__ == "__main__":
    main()
