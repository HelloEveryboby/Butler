import logging
import json
import os
import sys
import threading
import time
from typing import Dict, List, Any
from pathlib import Path
from butler.core.skill_sdk import SkillSDK
from .adapters.base_adapter import BaseDriveAdapter
from .adapters.onedrive import OneDriveAdapter
from .adapters.webdav import WebDAVAdapter
from .bridge_client import storage_bridge
from .cache_manager import MetaCache

logger = logging.getLogger("StorageHub")

# Global thread-safe transfer tasks storage
TRANSFER_TASKS: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()

class HubManager:
    def __init__(self):
        self.adapters: Dict[str, BaseDriveAdapter] = {}
        self.config = {}
        self.skill_root = Path(__file__).parent
        self.config_path = self.skill_root / "config.yaml"
        self.cache_path = self.skill_root / "cache" / "meta_cache.db"

        # Ensure cache directory exists
        os.makedirs(self.cache_path.parent, exist_ok=True)
        self.cache = MetaCache(str(self.cache_path))
        self.load_config()

    def register_adapter(self, name: str, adapter: BaseDriveAdapter):
        self.adapters[name] = adapter

    def load_config(self):
        """Loads configuration from config.yaml or falls back to JSON if pyyaml is unavailable."""
        if not self.config_path.exists():
            self.config = {"drives": []}
            return self.config

        try:
            import yaml
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {"drives": []}
        except ImportError:
            # Fallback to json if yaml is not installed
            json_path = self.config_path.with_suffix(".json")
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        self.config = json.load(f)
                except Exception:
                    self.config = {"drives": []}
            else:
                self.config = {"drives": []}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = {"drives": []}

        # Initialize adapters
        self.adapters.clear()
        self._init_from_config(self.config)
        return self.config

    def save_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves configuration persistent to config.yaml."""
        self.config = config_data
        try:
            import yaml
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f, default_flow_style=False, allow_unicode=True)
        except ImportError:
            # Fallback to json
            json_path = self.config_path.with_suffix(".json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return {"status": "error", "message": str(e)}

        # Re-initialize adapters
        self.adapters.clear()
        self._init_from_config(config_data)
        return {"status": "ok", "config": config_data}

    def _init_from_config(self, config: Dict[str, Any]):
        drives = config.get("drives", [])
        for drive in drives:
            drive_type = drive.get("type")
            drive_id = drive.get("id")
            if not drive_id:
                continue
            if drive_type == "onedrive":
                adapter = OneDriveAdapter(
                    drive_id=drive_id,
                    client_id=drive.get("client_id", ""),
                    client_secret=drive.get("client_secret", ""),
                    redirect_uri=drive.get("redirect_uri", "http://localhost:8421/oauth/callback")
                )
                self.register_adapter(drive_id, adapter)
            elif drive_type == "webdav":
                adapter = WebDAVAdapter(
                    drive_id=drive_id,
                    base_url=drive.get("base_url", ""),
                    username=drive.get("username", ""),
                    password=drive.get("password", "")
                )
                self.register_adapter(drive_id, adapter)

    def start_background_transfer(self, task_id: str, src_drive: str, dst_drive: str, file_name: str):
        """Simulates an asynchronous background transfer with RAM-Pipe streaming."""
        total_size = 100 * 1024 * 1024 # 100MB simulation
        chunk_size = 4 * 1024 * 1024   # 4MB per step
        transferred = 0
        start_time = time.time()

        while transferred < total_size:
            time.sleep(0.3) # Simulation speed
            transferred += chunk_size
            if transferred > total_size:
                transferred = total_size

            elapsed = time.time() - start_time
            speed = transferred / (elapsed if elapsed > 0 else 1) # Bytes/second
            speed_mb = speed / (1024 * 1024)

            with tasks_lock:
                if task_id not in TRANSFER_TASKS:
                    break # Task cancelled/cleared
                TRANSFER_TASKS[task_id].update({
                    "status": "transferring",
                    "progress": int((transferred / total_size) * 100),
                    "speed": f"{speed_mb:.1f} MB/s",
                    "transferred": f"{transferred / (1024*1024):.1f} MB",
                    "total": f"{total_size / (1024*1024):.1f} MB",
                    "pipe_mode": "RAM-Pipe 极速内存流管道"
                })

        with tasks_lock:
            if task_id in TRANSFER_TASKS:
                TRANSFER_TASKS[task_id].update({
                    "status": "completed",
                    "progress": 100,
                    "speed": "0.0 MB/s"
                })

    def handle_request(self, action: str, **kwargs) -> Dict[str, Any]:
        if action == "init":
            self._init_from_config(kwargs.get("config", {}))
            return {"status": "ok"}

        if action == "load_config":
            return {"status": "ok", "config": self.config}

        if action == "save_config":
            return self.save_config(kwargs.get("config", {}))

        if action == "list_drives":
            # For the UI dashboard, if config has no drives we return empty lists,
            # allowing fallback mock logic to trigger if they want to experience onboarding.
            drives_list = []
            for drive_id, adapter in self.adapters.items():
                # Extract drive info from config
                drv_conf = next((d for d in self.config.get("drives", []) if d.get("id") == drive_id), {})
                # Get dynamic quota info (mock or real)
                try:
                    quota = adapter.get_quota() or {"used": 0, "total": 1000}
                except Exception:
                    quota = {"used": 0, "total": 1000}

                drives_list.append({
                    "id": drive_id,
                    "name": drv_conf.get("name", drive_id),
                    "type": drv_conf.get("type", "webdav"),
                    "used": quota.get("used", 0),
                    "total": quota.get("total", 1000),
                    "icon": "☁️" if drv_conf.get("type") == "onedrive" else "🌐"
                })
            return {"status": "ok", "drives": drives_list}

        if action in ["list_files", "get_quota"]:
            drive_name = kwargs.get("drive")
            if not drive_name or drive_name not in self.adapters:
                return {"status": "error", "message": f"Drive {drive_name} not found"}
            adapter = self.adapters[drive_name]

            if action == "list_files":
                path = kwargs.get("path", "/")
                # Try cache first for millisecond browsing response
                cached = self.cache.get_files(drive_name, path)
                if cached:
                    return {"status": "ok", "files": cached}

                try:
                    files = adapter.list_files(path)
                    self.cache.set_files(drive_name, path, files)
                    return {"status": "ok", "files": files}
                except Exception as e:
                    return {"status": "error", "message": str(e)}

            if action == "get_quota":
                try:
                    quota = adapter.get_quota()
                    return {"status": "ok", "quota": quota}
                except Exception as e:
                    return {"status": "error", "message": str(e)}

        if action == "transfer":
            src_drive = kwargs.get("src_drive")
            dst_drive = kwargs.get("dst_drive")
            file_name = kwargs.get("file_name", "Unknown_File")

            # Create unique task id
            task_id = f"task_{int(time.time())}"
            with tasks_lock:
                TRANSFER_TASKS[task_id] = {
                    "status": "starting",
                    "progress": 0,
                    "speed": "0.0 MB/s",
                    "transferred": "0 MB",
                    "total": "0 MB",
                    "file_name": file_name,
                    "src_drive": src_drive,
                    "dst_drive": dst_drive
                }

            # Start simulated background thread transfer
            t = threading.Thread(
                target=self.start_background_transfer,
                args=(task_id, src_drive, dst_drive, file_name),
                daemon=True
            )
            t.start()
            return {"status": "ok", "task_id": task_id}

        if action == "check_transfer_status":
            task_id = kwargs.get("task_id")
            with tasks_lock:
                if not task_id or task_id not in TRANSFER_TASKS:
                    return {"status": "error", "message": "Task not found"}
                return {"status": "ok", "task": TRANSFER_TASKS[task_id]}

        return {"status": "error", "message": f"Unknown action: {action}"}

hub_manager = HubManager()

def handle_request(action: str, **kwargs) -> Dict[str, Any]:
    return hub_manager.handle_request(action, **kwargs)

def run():
    """CLI / Subprocess entry for JSON-RPC or direct execution."""
    import sys
    try:
        # Simple stdin line reader for interactive process bridging
        for line in sys.stdin:
            if not line.strip():
                continue
            req = json.loads(line)
            action = req.get("action")
            kwargs = req.get("kwargs", {})
            res = handle_request(action, **kwargs)
            print(json.dumps(res), flush=True)
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}), flush=True)

if __name__ == "__main__":
    run()
