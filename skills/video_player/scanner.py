"""
媒体库文件扫描器 — 扫描本地目录发现视频文件。
支持全量扫描和增量扫描（基于 watchdog 文件系统监听）。
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VideoScanner:
    """视频文件扫描器"""

    SUPPORTED_EXTENSIONS = {
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
        '.m4v', '.ts', '.m2ts', '.rmvb', '.rm', '.3gp', '.mpg',
        '.mpeg', '.vob', '.asf', '.ogv', '.f4v', '.mts', '.mxf',
        '.divx', '.ogm', '.wtv', '.m2v', '.m2t', '.tp', '.trp',
    }

    def __init__(self, scan_dirs: list[str] = None, recursive: bool = True,
                 on_file_found: Callable = None):
        """
        :param scan_dirs: 要扫描的目录列表
        :param recursive: 是否递归扫描子目录
        :param on_file_found: 发现新文件时的回调 callback(file_path: str)
        """
        self.scan_dirs = [os.path.expanduser(d) for d in (scan_dirs or [])]
        self.recursive = recursive
        self.on_file_found = on_file_found
        self._watcher = None
        self._watch_thread = None
        self._stop_event = threading.Event()

    def scan_all(self) -> list[str]:
        """
        全量扫描所有配置目录，返回发现的视频文件路径列表。
        """
        found = []
        for scan_dir in self.scan_dirs:
            if not os.path.isdir(scan_dir):
                logger.warning(f"扫描目录不存在: {scan_dir}")
                continue
            found.extend(self._scan_directory(scan_dir))

        logger.info(f"扫描完成，共发现 {len(found)} 个视频文件")
        return found

    def _scan_directory(self, directory: str) -> list[str]:
        """扫描单个目录"""
        found = []
        try:
            if self.recursive:
                for root, dirs, files in os.walk(directory):
                    # 跳过隐藏目录和系统目录
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                        'node_modules', '__pycache__', '.git', 'Thumbs'
                    }]
                    for f in files:
                        fp = os.path.join(root, f)
                        if self._is_video_file(fp):
                            found.append(fp)
                            if self.on_file_found:
                                self.on_file_found(fp)
            else:
                for item in os.listdir(directory):
                    fp = os.path.join(directory, item)
                    if os.path.isfile(fp) and self._is_video_file(fp):
                        found.append(fp)
                        if self.on_file_found:
                            self.on_file_found(fp)
        except PermissionError:
            logger.warning(f"无权限访问目录: {directory}")
        except Exception as e:
            logger.error(f"扫描目录失败 [{directory}]: {e}")

        return found

    def _is_video_file(self, file_path: str) -> bool:
        """判断文件是否为视频文件"""
        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return False
        # 跳过 0 字节文件
        try:
            if os.path.getsize(file_path) == 0:
                return False
        except OSError:
            return False
        return True

    def get_extension_info(self) -> dict:
        """获取支持的扩展名信息（用于 SKILL.md 描述）"""
        return {
            "extensions": sorted(self.SUPPORTED_EXTENSIONS),
            "count": len(self.SUPPORTED_EXTENSIONS),
        }

    # ══════════════════════════════════════════
    # 文件监听（watchdog，可选）
    # ══════════════════════════════════════════

    def start_watch(self, on_new_file: Callable = None) -> None:
        """
        启动文件系统监听，自动发现新增视频文件。
        需要安装 watchdog: pip install watchdog
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning("watchdog 未安装，文件监听功能不可用。pip install watchdog")
            return

        class VideoHandler(FileSystemEventHandler):
            def __init__(self, scanner):
                self.scanner = scanner
                self._callback = on_new_file

            def on_created(self, event):
                if event.is_directory:
                    return
                if self.scanner._is_video_file(event.src_path):
                    logger.info(f"发现新视频: {event.src_path}")
                    if self._callback:
                        self._callback(event.src_path)
                    if self.scanner.on_file_found:
                        self.scanner.on_file_found(event.src_path)

            def on_moved(self, event):
                if event.is_directory:
                    return
                if self.scanner._is_video_file(event.dest_path):
                    logger.info(f"视频文件移入: {event.dest_path}")
                    if self._callback:
                        self._callback(event.dest_path)

        handler = VideoHandler(self)
        self._watcher = Observer()
        for scan_dir in self.scan_dirs:
            if os.path.isdir(scan_dir):
                self._watcher.schedule(handler, scan_dir, recursive=self.recursive)
                logger.info(f"开始监听目录: {scan_dir}")

        self._watcher.start()
        logger.info("文件监听已启动")

    def stop_watch(self) -> None:
        """停止文件监听"""
        if self._watcher:
            self._watcher.stop()
            self._watcher.join(timeout=5)
            self._watcher = None
            logger.info("文件监听已停止")
