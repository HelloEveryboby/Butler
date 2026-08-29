"""
下载任务管理 — 任务队列、进度轮询、完成通知
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from aria2_manager import start_aria2, stop_aria2, is_running, get_status, DEFAULT_RPC_PORT, DEFAULT_RPC_SECRET
from rpc_client import Aria2RPC


class DownloadManager:
    def __init__(self, rpc_port: int = DEFAULT_RPC_PORT, rpc_secret: str = DEFAULT_RPC_SECRET):
        self.rpc = Aria2RPC(port=rpc_port, secret=rpc_secret)
        self._poll_thread: Optional[threading.Thread] = None
        self._polling = False
        self._on_complete: Optional[Callable[[Dict], None]] = None
        self._on_error: Optional[Callable[[Dict], None]] = None
        self._on_progress: Optional[Callable[[Dict], None]] = None

    # ---------- 生命周期 ----------
    def start(self, download_dir: str = "", max_concurrent: int = 10, max_connection: int = 16) -> Dict[str, Any]:
        """启动 Aria2 并开始轮询"""
        result = start_aria2(
            download_dir=download_dir,
            max_concurrent=max_concurrent,
            max_connection=max_connection,
        )
        if result["success"]:
            self._start_polling()
        return result

    def stop(self) -> Dict[str, Any]:
        """停止轮询和 Aria2"""
        self._stop_polling()
        return stop_aria2()

    def ensure_running(self) -> bool:
        """确保 Aria2 在运行"""
        if not is_running():
            result = start_aria2()
            if result["success"]:
                self._start_polling()
            return result["success"]
        return True

    # ---------- 下载操作 ----------
    def add_url(self, url: str, filename: Optional[str] = None, dir: Optional[str] = None) -> Dict[str, Any]:
        """添加下载链接"""
        self.ensure_running()
        gid = self.rpc.download(url, filename, dir)
        return {"success": True, "gid": gid, "url": url}

    def add_urls(self, urls: List[str], dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """批量添加下载链接"""
        self.ensure_running()
        results = []
        for url in urls:
            try:
                gid = self.rpc.download(url, dir=dir)
                results.append({"success": True, "gid": gid, "url": url})
            except Exception as e:
                results.append({"success": False, "url": url, "error": str(e)})
        return results

    def add_magnet(self, magnet: str, dir: Optional[str] = None) -> Dict[str, Any]:
        """添加磁力链接"""
        self.ensure_running()
        gid = self.rpc.add_magnet(magnet, {"dir": dir} if dir else None)
        return {"success": True, "gid": gid, "type": "magnet"}

    def add_torrent(self, torrent_path: str, dir: Optional[str] = None) -> Dict[str, Any]:
        """添加种子文件"""
        self.ensure_running()
        gid = self.rpc.add_torrent(torrent_path, {"dir": dir} if dir else None)
        return {"success": True, "gid": gid, "type": "torrent", "file": torrent_path}

    def pause(self, gid: str) -> bool:
        try:
            self.rpc.pause(gid)
            return True
        except:
            return False

    def resume(self, gid: str) -> bool:
        try:
            self.rpc.resume(gid)
            return True
        except:
            return False

    def remove(self, gid: str, force: bool = False) -> bool:
        try:
            if force:
                self.rpc.force_remove(gid)
            else:
                self.rpc.remove(gid)
            return True
        except:
            return False

    def pause_all(self) -> bool:
        try:
            self.rpc.pause_all()
            return True
        except:
            return False

    def resume_all(self) -> bool:
        try:
            self.rpc.resume_all()
            return True
        except:
            return False

    # ---------- 状态查询 ----------
    def get_task(self, gid: str) -> Optional[Dict[str, Any]]:
        try:
            raw = self.rpc.get_status(gid)
            return self._format_task(raw)
        except:
            return None

    def get_all_tasks(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            raw = self.rpc.get_all_tasks()
            return {
                "active": [self._format_task(t) for t in raw.get("active", [])],
                "waiting": [self._format_task(t) for t in raw.get("waiting", [])],
                "stopped": [self._format_task(t) for t in raw.get("stopped", [])],
            }
        except:
            return {"active": [], "waiting": [], "stopped": []}

    def get_speed(self) -> Dict[str, int]:
        try:
            return self.rpc.get_speed()
        except:
            return {"download_speed": 0, "upload_speed": 0, "num_active": 0, "num_waiting": 0, "num_stopped": 0}

    # ---------- 限速 ----------
    def set_speed_limit(self, download: str = "0", upload: str = "0") -> None:
        self.rpc.set_global_speed_limit(download, upload)

    # ---------- 格式化 ----------
    def _format_task(self, raw: Dict) -> Dict[str, Any]:
        """将 Aria2 原始状态转为前端友好格式"""
        total = int(raw.get("totalLength", 0))
        completed = int(raw.get("completedLength", 0))
        speed = int(raw.get("downloadSpeed", 0))
        progress = (completed / total * 100) if total > 0 else 0

        # 文件名
        files = raw.get("files", [])
        filename = ""
        if files:
            filepath = files[0].get("path", "")
            filename = os.path.basename(filepath) if filepath else ""

        # 剩余时间
        remaining = (total - completed) / speed if speed > 0 else 0

        return {
            "gid": raw.get("gid", ""),
            "status": raw.get("status", ""),
            "filename": filename,
            "total_length": total,
            "completed_length": completed,
            "total_human": _human_size(total),
            "completed_human": _human_size(completed),
            "progress": round(progress, 1),
            "download_speed": speed,
            "speed_human": f"{_human_size(speed)}/s",
            "remaining_seconds": round(remaining),
            "remaining_human": _human_time(remaining),
            "connections": int(raw.get("connections", 0)),
            "dir": raw.get("dir", ""),
            "error_code": raw.get("errorCode"),
            "error_message": raw.get("errorMessage", ""),
            "bt": raw.get("bittorrent", {}),
        }

    # ---------- 轮询 ----------
    def _start_polling(self):
        if self._polling:
            return
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _stop_polling(self):
        self._polling = False

    def _poll_loop(self):
        while self._polling:
            try:
                tasks = self.get_all_tasks()
                # 活跃任务进度回调
                if self._on_progress:
                    for task in tasks.get("active", []):
                        self._on_progress(task)
                # 检查刚完成的任务
                for task in tasks.get("stopped", []):
                    if task.get("status") == "complete" and self._on_complete:
                        self._on_complete(task)
                    elif task.get("error_code") and self._on_error:
                        self._on_error(task)
            except:
                pass
            time.sleep(1)

    # ---------- 回调设置 ----------
    def on_complete(self, callback: Callable[[Dict], None]):
        self._on_complete = callback

    def on_error(self, callback: Callable[[Dict], None]):
        self._on_error = callback

    def on_progress(self, callback: Callable[[Dict], None]):
        self._on_progress = callback


# ---------- 工具 ----------
def _human_size(size: int) -> str:
    if size <= 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _human_time(seconds: float) -> str:
    if seconds <= 0:
        return "未知"
    if seconds < 60:
        return f"{int(seconds)}秒"
    if seconds < 3600:
        return f"{int(seconds//60)}分{int(seconds%60)}秒"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}小时{m}分"
