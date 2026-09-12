"""
媒体库管理 — 协调扫描器、元数据提取器和数据库。
提供媒体库的完整管理能力。
"""

import os
import time
import logging
import asyncio
from pathlib import Path
from typing import Optional

from .scanner import VideoScanner
from .metadata import MetadataExtractor, VideoMetadata
from .db import VideoDatabase

logger = logging.getLogger(__name__)


class MediaLibrary:
    """媒体库管理器"""

    def __init__(self, db: VideoDatabase, config: dict):
        self.db = db
        self.config = config
        self.metadata = MetadataExtractor(
            ffprobe_path=config.get("ffprobe_path", "ffprobe")
        )
        self.scanner = VideoScanner(
            scan_dirs=config.get("library", {}).get("scan_dirs", []),
            recursive=config.get("library", {}).get("scan_recursive", True),
            on_file_found=self._on_file_found,
        )
        self._scanning = False
        self._scan_callbacks = []

    def _on_file_found(self, file_path: str):
        """扫描发现新文件时的回调"""
        pass  # 实际入库逻辑在 full_scan / incremental_scan 中

    async def full_scan(self) -> dict:
        """
        全量扫描所有配置目录。
        跳过已入库的文件，只处理新增文件。
        """
        if self._scanning:
            return {"status": "already_scanning"}

        self._scanning = True
        start_time = time.time()
        stats = {"total": 0, "added": 0, "skipped": 0, "failed": 0, "duration_sec": 0}

        try:
            video_files = self.scanner.scan_all()
            stats["total"] = len(video_files)

            for file_path in video_files:
                stats["total"] += 1

                # 跳过已入库
                if self.db.exists(file_path):
                    stats["skipped"] += 1
                    continue

                # 提取元数据
                meta = await self.metadata.extract(file_path)
                if meta is None:
                    stats["failed"] += 1
                    continue

                # 入库
                try:
                    self.db.insert_video(meta.to_dict())
                    stats["added"] += 1
                    logger.debug(f"入库成功: {meta.title} ({meta.container} {meta.video_codec})")
                except Exception as e:
                    logger.error(f"入库失败 [{file_path}]: {e}")
                    stats["failed"] += 1

        except Exception as e:
            logger.error(f"全量扫描异常: {e}")
        finally:
            self._scanning = False
            stats["duration_sec"] = round(time.time() - start_time, 2)

        logger.info(
            f"扫描完成: 共 {stats['total']} 个文件, "
            f"新增 {stats['added']}, 跳过 {stats['skipped']}, "
            f"失败 {stats['failed']}, 耗时 {stats['duration_sec']}s"
        )
        return stats

    async def scan_single(self, file_path: str) -> Optional[str]:
        """
        扫描单个文件并入库。
        :return: video_id 或 None
        """
        if self.db.exists(file_path):
            existing = self.db.get_video_by_path(file_path)
            return existing["id"] if existing else None

        meta = await self.metadata.extract(file_path)
        if meta is None:
            return None

        return self.db.insert_video(meta.to_dict())

    async def rescan_video(self, video_id: str) -> Optional[dict]:
        """重新扫描单个视频的元数据（文件可能已更新）"""
        video = self.db.get_video(video_id)
        if not video:
            return None

        if not os.path.isfile(video["path"]):
            self.db.delete_video(video_id)
            return None

        meta = await self.metadata.extract(video["path"])
        if meta:
            self.db.update_video(video_id, meta.to_dict())
            return self.db.get_video(video_id)
        return None

    def start_auto_scan(self) -> None:
        """启动自动扫描（文件监听 + 定时扫描）"""
        # 启动文件监听
        self.scanner.start_watch(on_new_file=self._handle_new_file)
        logger.info("自动扫描已启动")

    def stop_auto_scan(self) -> None:
        """停止自动扫描"""
        self.scanner.stop_watch()

    def _handle_new_file(self, file_path: str):
        """处理新发现的文件（在监听线程中调用）"""
        asyncio.run_coroutine_threadsafe(
            self.scan_single(file_path),
            asyncio.get_event_loop()
        )

    def get_library_stats(self) -> dict:
        """获取媒体库统计信息"""
        return self.db.get_stats()

    def search(self, query: str) -> list[dict]:
        """搜索视频"""
        return self.db.search_videos(query)

    def get_video_info(self, video_id: str) -> Optional[dict]:
        """获取视频详情"""
        return self.db.get_video(video_id)

    def get_recently_added(self, limit: int = 20) -> list[dict]:
        """获取最近添加的视频"""
        return self.db.get_recent_videos(limit)

    def get_recently_played(self, limit: int = 20) -> list[dict]:
        """获取最近播放的视频"""
        return self.db.get_play_history(limit)

    def get_favorites(self) -> list[dict]:
        """获取收藏的视频"""
        return self.db.get_favorite_videos()

    def toggle_favorite(self, video_id: str) -> bool:
        """切换收藏状态"""
        return self.db.toggle_favorite(video_id)

    def delete_video(self, video_id: str) -> bool:
        """删除视频记录（不删除文件）"""
        video = self.db.get_video(video_id)
        if not video:
            return False
        self.db.delete_video(video_id)
        return True

    def update_scan_dirs(self, dirs: list[str]) -> None:
        """更新扫描目录"""
        self.scanner.scan_dirs = [os.path.expanduser(d) for d in dirs]
        self.config.setdefault("library", {})["scan_dirs"] = dirs
