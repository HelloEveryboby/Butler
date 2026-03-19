import os
import shutil
import zipfile
import hashlib
import time
import json
from typing import Dict, List, Optional
from plugin.plugin_interface import AbstractPlugin, PluginResult
from butler.core.event_bus import event_bus

class ArchiveManagerPlugin(AbstractPlugin):
    def __init__(self):
        super().__init__()
        self.cache_dir = os.path.join(self.get_root_dir(), "data", "archive_cache")
        self.tracked_files: Dict[str, Dict] = {}  # {extracted_path: {zip_path, file_in_zip, initial_hash}}

    def get_name(self) -> str:
        return "ArchiveManager"

    def get_chinese_name(self) -> str:
        return "压缩管理"

    def get_description(self) -> str:
        return "管理压缩包内容，支持文件改动监控与原子更新。"

    def get_commands(self) -> List[str]:
        return ["open_zip_file", "sync_zip_file", "list_zip_contents", "detect_changes"]

    def run(self, command: str, args: dict) -> PluginResult:
        if command == "open_zip_file":
            zip_path = args.get("zip_path")
            file_in_zip = args.get("file_in_zip")
            if not zip_path or not file_in_zip:
                return PluginResult.new(None, success=False, error_message="Missing zip_path or file_in_zip")
            return self.open_and_track(zip_path, file_in_zip)

        elif command == "sync_zip_file":
            extracted_path = args.get("extracted_path")
            action = args.get("action", "Y") # Y: Sync, N: Cancel, R: Rebuild
            if not extracted_path:
                return PluginResult.new(None, success=False, error_message="Missing extracted_path")
            return self.apply_sync(extracted_path, action)

        elif command == "detect_changes":
            extracted_path = args.get("extracted_path")
            if not extracted_path:
                return PluginResult.new(None, success=False, error_message="Missing extracted_path")
            return self.detect_changes(extracted_path)

        elif command == "list_zip_contents":
            zip_path = args.get("zip_path")
            if not zip_path:
                return PluginResult.new(None, success=False, error_message="Missing zip_path")
            return self.list_contents(zip_path)

        return PluginResult.new(None, success=False, error_message=f"Unknown command: {command}")

    def _get_file_hash(self, filepath: str) -> str:
        hasher = hashlib.md5()
        if not os.path.exists(filepath):
            return ""
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def list_contents(self, zip_path: str) -> PluginResult:
        if not os.path.exists(zip_path):
            return PluginResult.new(None, success=False, error_message="Zip file not found")
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                contents = z.namelist()
            return PluginResult.new(contents)
        except Exception as e:
            return PluginResult.new(None, success=False, error_message=str(e))

    def open_and_track(self, zip_path: str, file_in_zip: str) -> PluginResult:
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                zip_name_hash = hashlib.md5(zip_path.encode()).hexdigest()[:8]
                dest_subdir = os.path.join(self.cache_dir, zip_name_hash)
                os.makedirs(dest_subdir, exist_ok=True)

                z.extract(file_in_zip, dest_subdir)
                extracted_path = os.path.join(dest_subdir, file_in_zip)

            initial_hash = self._get_file_hash(extracted_path)
            self.tracked_files[extracted_path] = {
                "zip_path": zip_path,
                "file_in_zip": file_in_zip,
                "initial_hash": initial_hash
            }

            # Open with system default application
            import platform
            import subprocess
            if platform.system() == 'Windows':
                os.startfile(extracted_path)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', extracted_path])
            else:
                subprocess.run(['xdg-open', extracted_path])

            return PluginResult.new({"extracted_path": extracted_path}, status=f"Monitoring {file_in_zip}")
        except Exception as e:
            return PluginResult.new(None, success=False, error_message=str(e))

    def detect_changes(self, extracted_path: str) -> PluginResult:
        if extracted_path not in self.tracked_files:
            return PluginResult.new(False)

        info = self.tracked_files[extracted_path]
        initial_hash = info["initial_hash"]
        current_hash = self._get_file_hash(extracted_path)

        return PluginResult.new(current_hash != initial_hash)

    def apply_sync(self, extracted_path: str, action: str) -> PluginResult:
        if extracted_path not in self.tracked_files:
            return PluginResult.new(None, success=False, error_message="File not tracked")

        info = self.tracked_files[extracted_path]
        zip_path = info["zip_path"]
        file_in_zip = info["file_in_zip"]

        if action.upper() == 'Y':
            res = self._safe_replace_in_zip(zip_path, file_in_zip, extracted_path)
            self.cleanup_tracked_file(extracted_path)
            return res
        elif action.upper() == 'N':
            self.cleanup_tracked_file(extracted_path)
            return PluginResult.new(None, status="Sync cancelled")
        elif action.upper() == 'R':
            # Rebuild could mean full re-compression, but here we reuse safe_replace
            res = self._safe_replace_in_zip(zip_path, file_in_zip, extracted_path)
            self.cleanup_tracked_file(extracted_path)
            return res

        return PluginResult.new(None, success=False, error_message="Invalid action")

    def _safe_replace_in_zip(self, zip_path: str, file_in_zip: str, new_file_path: str) -> PluginResult:
        tmp_zip = zip_path + ".tmp"
        try:
            with zipfile.ZipFile(zip_path, 'r') as zin:
                with zipfile.ZipFile(tmp_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                    infolist = zin.infolist()
                    total = len(infolist)
                    for i, item in enumerate(infolist):
                        if item.filename != file_in_zip:
                            zout.writestr(item, zin.read(item.filename))

                        progress = int(((i + 1) / (total + 1)) * 100)
                        event_bus.emit("ui_output", json.dumps({"type": "progress", "value": progress}), "status_update", None)

                    zout.write(new_file_path, file_in_zip)
                    event_bus.emit("ui_output", json.dumps({"type": "progress", "value": 100}), "status_update", None)

            os.replace(tmp_zip, zip_path)
            return PluginResult.new(None, status="Successfully updated archive")
        except Exception as e:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
            return PluginResult.new(None, success=False, error_message=str(e))

    def cleanup_tracked_file(self, extracted_path: str):
        if extracted_path in self.tracked_files:
            del self.tracked_files[extracted_path]
            try:
                # os.remove(extracted_path) # Keeping it simple for now
                pass
            except:
                pass

    def on_shutdown(self):
        if os.path.exists(self.cache_dir):
            try:
                shutil.rmtree(self.cache_dir)
            except:
                pass
        super().on_shutdown()
