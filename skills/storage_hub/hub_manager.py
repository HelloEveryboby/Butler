import logging
from typing import Dict, List, Any
from butler.core.skill_sdk import SkillSDK
from .adapters.base_adapter import BaseDriveAdapter
from .adapters.onedrive import OneDriveAdapter
from .bridge_client import storage_bridge
from .cache_manager import MetaCache
from pathlib import Path

logger = logging.getLogger("StorageHub")

class HubManager:
    def __init__(self):
        self.adapters: Dict[str, BaseDriveAdapter] = {}
        self.config = {}
        # Ensure path is relative to the skill folder
        skill_root = Path(__file__).parent
        self.cache = MetaCache(str(skill_root / "cache" / "meta_cache.db"))

    def register_adapter(self, name: str, adapter: BaseDriveAdapter):
        self.adapters[name] = adapter

    def _init_from_config(self, config: Dict[str, Any]):
        self.config = config
        drives = config.get("drives", [])
        for drive in drives:
            drive_type = drive.get("type")
            drive_id = drive.get("id")
            if drive_type == "onedrive":
                adapter = OneDriveAdapter(
                    drive_id=drive_id,
                    client_id=drive.get("client_id"),
                    client_secret=drive.get("client_secret"),
                    redirect_uri=drive.get("redirect_uri", "http://localhost:8421/oauth/callback")
                )
                self.register_adapter(drive_id, adapter)

    def handle_request(self, action: str, **kwargs):
        if action == "init":
            self._init_from_config(kwargs.get("config", {}))
            return {"status": "ok"}
        if action == "list_drives":
            return list(self.adapters.keys())

        if action in ["list_files", "get_quota"]:
            drive_name = kwargs.get("drive")
            if not drive_name or drive_name not in self.adapters:
                return {"error": f"Drive {drive_name} not found"}
            adapter = self.adapters[drive_name]

            if action == "list_files":
                path = kwargs.get("path", "/")
                # 1. Try cache first for "millisecond response"
                cached = self.cache.get_files(drive_name, path)

                # 2. In background (or after returning), refresh cache
                # For now, we fetch and update cache synchronously if no cache,
                # but return cache if exists.
                if cached:
                    # TODO: Trigger async refresh
                    return cached

                files = adapter.list_files(path)
                self.cache.set_files(drive_name, path, files)
                return files

            if action == "get_quota":
                return adapter.get_quota()

        if action == "start_auth":
            # This would involve calling bridge to start listener and returning auth URL
            # For brevity in this step, we just show the bridge usage
            import asyncio
            success, code = asyncio.run(storage_bridge.start_oauth_listen())
            return {"status": "ok" if success else "error", "code": code}

        if action == "transfer":
            SkillSDK.ui_print("🚀 Starting cross-drive transfer...")
            src_drive = kwargs.get("src_drive")
            dst_drive = kwargs.get("dst_drive")
            file_id = kwargs.get("file_id")
            dst_path = kwargs.get("dst_path")

            src_adapter = self.adapters.get(src_drive)
            dst_adapter = self.adapters.get(dst_drive)

            if not src_adapter or not dst_adapter:
                return {"error": "Source or destination drive not found"}

            src_url = src_adapter.get_download_link(file_id)
            dst_params = dst_adapter.get_upload_params(dst_path)

            import asyncio
            success, msg = asyncio.run(storage_bridge.transfer(
                src_url=src_url,
                dst_url=dst_params["url"],
                method=dst_params["method"],
                dst_headers=dst_params["headers"]
            ))
            return {"status": "ok" if success else "error", "message": msg}

        return {"error": f"Unknown action {action}"}

hub_manager = HubManager()

def handle_request(action: str, **kwargs):
    return hub_manager.handle_request(action, **kwargs)
