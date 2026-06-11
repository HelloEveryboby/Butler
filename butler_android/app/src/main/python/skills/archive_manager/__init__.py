import os
import shutil
import zipfile
import hashlib
import time
import json
import platform
import subprocess
from typing import Dict, List, Optional, Any
from butler.core.event_bus import event_bus

class ArchiveManager:
    """
    Archive Manager Logic (Migrated from Plugin)
    """
    def __init__(self):
        # 获取项目根目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.cache_dir = os.path.join(self.project_root, "data", "archive_cache")
        # 由于 Skill 是无状态的加载模式，但我们需要追踪文件，
        # 这里可以使用一个简单的进程级单例或者持久化状态。
        # 考虑到 Butler 的长期运行，我们使用类变量。
        if not hasattr(ArchiveManager, '_tracked_files'):
            ArchiveManager._tracked_files: Dict[str, Dict] = {}

    def _get_file_hash(self, filepath: str) -> str:
        hasher = hashlib.md5()
        if not os.path.exists(filepath):
            return ""
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except:
            return ""

    def list_contents(self, zip_path: str) -> Dict[str, Any]:
        if not os.path.exists(zip_path):
            return {"success": False, "error": "Zip file not found"}
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                contents = z.namelist()
            return {"success": True, "result": contents}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_and_track(self, zip_path: str, file_in_zip: str) -> Dict[str, Any]:
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                zip_name_hash = hashlib.md5(zip_path.encode()).hexdigest()[:8]
                dest_subdir = os.path.join(self.cache_dir, zip_name_hash)
                os.makedirs(dest_subdir, exist_ok=True)

                z.extract(file_in_zip, dest_subdir)
                extracted_path = os.path.abspath(os.path.join(dest_subdir, file_in_zip))

            initial_hash = self._get_file_hash(extracted_path)
            ArchiveManager._tracked_files[extracted_path] = {
                "zip_path": zip_path,
                "file_in_zip": file_in_zip,
                "initial_hash": initial_hash
            }

            # Open with system default application
            if platform.system() == 'Windows':
                os.startfile(extracted_path)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', extracted_path])
            else:
                subprocess.run(['xdg-open', extracted_path])

            return {"success": True, "extracted_path": extracted_path, "status": f"Monitoring {file_in_zip}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_changes(self, extracted_path: str) -> bool:
        if extracted_path not in ArchiveManager._tracked_files:
            return False

        info = ArchiveManager._tracked_files[extracted_path]
        initial_hash = info["initial_hash"]
        current_hash = self._get_file_hash(extracted_path)

        return current_hash != initial_hash

    def apply_sync(self, extracted_path: str, action: str = "Y") -> Dict[str, Any]:
        if extracted_path not in ArchiveManager._tracked_files:
            return {"success": False, "error": "File not tracked"}

        info = ArchiveManager._tracked_files[extracted_path]
        zip_path = info["zip_path"]
        file_in_zip = info["file_in_zip"]

        if action.upper() == 'Y':
            res = self._safe_replace_in_zip(zip_path, file_in_zip, extracted_path)
            self.cleanup_tracked_file(extracted_path)
            return res
        else:
            self.cleanup_tracked_file(extracted_path)
            return {"success": True, "status": "Sync cancelled"}

    def _safe_replace_in_zip(self, zip_path: str, file_in_zip: str, new_file_path: str) -> Dict[str, Any]:
        tmp_zip = zip_path + ".tmp"
        try:
            with zipfile.ZipFile(zip_path, 'r') as zin:
                with zipfile.ZipFile(tmp_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                    infolist = zin.infolist()
                    total = len(infolist)
                    for i, item in enumerate(infolist):
                        if item.filename != file_in_zip:
                            zout.writestr(item, zin.read(item.filename))
                        # Progress emit if needed via event_bus
                    zout.write(new_file_path, file_in_zip)

            os.replace(tmp_zip, zip_path)
            return {"success": True, "status": "Successfully updated archive"}
        except Exception as e:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
            return {"success": False, "error": str(e)}

    def cleanup_tracked_file(self, extracted_path: str):
        if extracted_path in ArchiveManager._tracked_files:
            del ArchiveManager._tracked_files[extracted_path]

manager = ArchiveManager()

def handle_request(action: str, **kwargs):
    if action == "list_zip_contents":
        return manager.list_contents(kwargs.get("zip_path"))
    elif action == "open_zip_file":
        return manager.open_and_track(kwargs.get("zip_path"), kwargs.get("file_in_zip"))
    elif action == "detect_changes":
        return manager.detect_changes(kwargs.get("extracted_path"))
    elif action == "sync_zip_file":
        return manager.apply_sync(kwargs.get("extracted_path"), kwargs.get("action", "Y"))
    return {"error": f"Unknown action: {action}"}
