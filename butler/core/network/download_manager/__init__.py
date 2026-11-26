"""Aria2 下载管理器（原 ``download_manager``）。"""

from .aria2_manager import get_status, is_running, start_aria2, stop_aria2
from .download_manager import DownloadManager

__all__ = ["DownloadManager", "get_status", "is_running", "start_aria2", "stop_aria2"]
