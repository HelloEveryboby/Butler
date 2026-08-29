"""
Aria2 JSON-RPC 客户端 — 与 Aria2 引擎通信
"""

import json
import urllib.request
from typing import Any, Dict, List, Optional


class Aria2RPC:
    def __init__(self, host: str = "127.0.0.1", port: int = 6800, secret: str = "butler_download"):
        self.url = f"http://{host}:{port}/jsonrpc"
        self.secret = secret
        self._id_counter = 0

    def _call(self, method: str, params: Optional[List] = None) -> Any:
        self._id_counter += 1
        # Aria2 RPC 格式：secret:token 前缀
        rpc_params = [f"token:{self.secret}"] + (params or [])
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": f"butler-{self._id_counter}",
            "method": method,
            "params": rpc_params,
        }).encode()

        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if "error" in data:
                raise Exception(f"Aria2 RPC error: {data['error']}")
            return data.get("result")

    # ---------- 任务操作 ----------
    def add_uri(self, uris: List[str], options: Optional[Dict] = None) -> str:
        """添加下载链接，返回 GID"""
        return self._call("aria2.addUri", [uris, options or {}])

    def add_torrent(self, torrent_path: str, options: Optional[Dict] = None) -> str:
        """添加种子文件"""
        import base64
        with open(torrent_path, "rb") as f:
            torrent_b64 = base64.b64encode(f.read()).decode()
        return self._call("aria2.addTorrent", [torrent_b64, [], options or {}])

    def add_magnet(self, magnet_uri: str, options: Optional[Dict] = None) -> str:
        """添加磁力链接"""
        return self.add_uri([magnet_uri], options)

    def remove(self, gid: str) -> str:
        return self._call("aria2.remove", [gid])

    def force_remove(self, gid: str) -> str:
        return self._call("aria2.forceRemove", [gid])

    def pause(self, gid: str) -> str:
        return self._call("aria2.pause", [gid])

    def pause_all(self) -> str:
        return self._call("aria2.pauseAll")

    def resume(self, gid: str) -> str:
        return self._call("aria2.resume", [gid])

    def resume_all(self) -> str:
        return self._call("aria2.resumeAll")

    def remove_all(self) -> str:
        return self._call("aria2.forcePauseAll")

    # ---------- 状态查询 ----------
    def get_status(self, gid: str) -> Dict[str, Any]:
        """获取单个任务状态"""
        return self._call("aria2.tellStatus", [gid])

    def get_active(self) -> List[Dict[str, Any]]:
        """获取正在下载的任务"""
        return self._call("aria2.tellActive")

    def get_waiting(self, offset: int = 0, num: int = 100) -> List[Dict[str, Any]]:
        """获取等待中的任务"""
        return self._call("aria2.tellWaiting", [offset, num])

    def get_stopped(self, offset: int = 0, num: int = 100) -> List[Dict[str, Any]]:
        """获取已完成/出错的任务"""
        return self._call("aria2.tellStopped", [offset, num])

    def get_global_stat(self) -> Dict[str, Any]:
        """获取全局统计（速度、任务数等）"""
        return self._call("aria2.getGlobalStat")

    def get_version(self) -> str:
        return self._call("aria2.getVersion")

    # ---------- 选项 ----------
    def change_option(self, gid: str, options: Dict[str, str]) -> str:
        return self._call("aria2.changeOption", [gid, options])

    def get_option(self, gid: str) -> Dict[str, str]:
        return self._call("aria2.getOption", [gid])

    def change_global_option(self, options: Dict[str, str]) -> str:
        return self._call("aria2.changeGlobalOption", [options])

    # ---------- 限速 ----------
    def set_global_speed_limit(self, download: str = "0", upload: str = "0") -> None:
        """设置全局限速，如 '1M', '500K', '0' (无限制)"""
        self.change_global_option({
            "max-overall-download-limit": download,
            "max-overall-upload-limit": upload,
        })

    def set_task_speed_limit(self, gid: str, download: str = "0") -> None:
        """设置单任务限速"""
        self.change_option(gid, {"max-download-limit": download})

    # ---------- 清理 ----------
    def purge_download_result(self) -> str:
        """清理已完成/出错的任务记录"""
        return self._call("aria2.purgeDownloadResult")

    def save_session(self) -> str:
        """保存当前会话"""
        return self._call("aria2.saveSession")

    # ---------- 便捷方法 ----------
    def download(self, url: str, filename: Optional[str] = None, dir: Optional[str] = None) -> str:
        """简单下载：添加链接并返回 GID"""
        options = {}
        if filename:
            options["out"] = filename
        if dir:
            options["dir"] = dir
        return self.add_uri([url], options)

    def get_all_tasks(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务（活跃 + 等待 + 已停止）"""
        return {
            "active": self.get_active() or [],
            "waiting": self.get_waiting() or [],
            "stopped": self.get_stopped() or [],
        }

    def get_speed(self) -> Dict[str, int]:
        """获取当前下载/上传速度 (bytes/s)"""
        stat = self.get_global_stat()
        return {
            "download_speed": int(stat.get("downloadSpeed", 0)),
            "upload_speed": int(stat.get("uploadSpeed", 0)),
            "num_active": int(stat.get("numActive", 0)),
            "num_waiting": int(stat.get("numWaiting", 0)),
            "num_stopped": int(stat.get("numStopped", 0)),
        }
