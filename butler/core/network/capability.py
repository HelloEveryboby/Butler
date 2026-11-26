"""``network`` 能力处理器：薄适配到 ``butler.core.network`` 下的各组实现。"""

from __future__ import annotations

import os
from typing import Any


def _manager():
    from butler.core.network.download_manager import DownloadManager

    return DownloadManager()


def _download(payload: dict[str, Any]) -> dict[str, Any]:
    url = payload.get("url") or payload.get("magnet") or payload.get("torrent")
    if not url:
        return {"error": "download 需要 url / magnet / torrent"}
    url = str(url)
    directory = payload.get("dir") or payload.get("save_dir")
    name = payload.get("name") or payload.get("filename")
    manager = _manager()
    if url.startswith("magnet:"):
        return manager.add_magnet(url, directory)
    if url.endswith(".torrent") and os.path.exists(url):
        return manager.add_torrent(url, directory)
    return manager.add_url(url, name, directory)


def handle_network(action: str, payload: dict[str, Any]) -> Any:
    if action == "download":
        return _download(payload)
    if action == "list":
        manager = _manager()
        return {"tasks": manager.get_all_tasks(), "speed": manager.get_speed()}
    if action in ("pause", "resume", "remove"):
        gid = str(payload.get("gid") or "")
        if not gid:
            return {"error": f"{action} 需要 gid"}
        manager = _manager()
        if action == "pause":
            return {"success": manager.pause(gid)}
        if action == "resume":
            return {"success": manager.resume(gid)}
        return {"success": manager.remove(gid, force=bool(payload.get("force", False)))}
    if action == "speed":
        return _manager().get_speed()
    if action == "status":
        from butler.core.network.download_manager import get_status

        return get_status()
    if action in ("mount", "unmount", "mount_status"):
        from butler.core.network.cloud_mount import mount_manager

        if action == "mount":
            return mount_manager.mount(
                payload.get("mount_point") or "",
                letter=payload.get("letter"),
                webdav_url=payload.get("webdav_url") or mount_manager.ALIST_WEBDAV_URL,
                username=payload.get("username") or "",
                password=payload.get("password") or "",
            )
        if action == "unmount":
            return mount_manager.unmount()
        return mount_manager.get_status()
    if action == "sniff":
        from butler.core.network import media_sniffer

        return media_sniffer.sniff()
    return {"error": f"未知动作: {action}"}
