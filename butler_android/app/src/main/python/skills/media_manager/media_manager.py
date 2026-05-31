import os
import platform
import subprocess
from typing import List, Dict

class MediaManagerSkill:
    def __init__(self, media_roots: List[str] = None):
        # Default roots plus any custom ones
        self.media_roots = media_roots or ["assets", "data/user_data/media"]

    def _get_system_drives(self) -> List[str]:
        """Detects available storage drives/mount points on the system."""
        drives = []
        if platform.system() == "Windows":
            import string
            from ctypes import windll
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append(f"{letter}:/")
                bitmask >>= 1
        else:
            # Linux/macOS: Check common mount points
            common_mounts = ["/media", "/mnt", "/Volumes"]
            for mount in common_mounts:
                if os.path.exists(mount):
                    for item in os.listdir(mount):
                        full_path = os.path.join(mount, item)
                        if os.path.isdir(full_path):
                            drives.append(full_path)
            # Add user home as well
            drives.append(os.path.expanduser("~"))
        return drives

    def get_media_library(self) -> List[Dict[str, str]]:
        """Scans media roots and all detected system drives for MP3, WAV, and JPG files."""
        library = []
        extensions = {'.mp3': 'audio', '.wav': 'audio', '.jpg': 'image', '.jpeg': 'image'}

        # Combine default roots and detected drives
        search_paths = list(set(self.media_roots + self._get_system_drives()))

        for root_dir in search_paths:
            if not os.path.exists(root_dir):
                continue

            # Use os.walk with error handling to avoid permission issues
            try:
                for root, dirs, files in os.walk(root_dir):
                    # Skip hidden directories to speed up
                    dirs[:] = [d for d in dirs if not d.startswith('.')]

                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in extensions:
                            library.append({
                                "name": file,
                                "path": os.path.join(root, file).replace("\\", "/"),
                                "type": extensions[ext]
                            })

                    # Optimization: Limit depth for full drive scans to prevent hanging
                    if root.count(os.sep) - root_dir.count(os.sep) > 3:
                        del dirs[:] # Don't go deeper than 4 levels for performance

            except (PermissionError, OSError):
                continue

        return library

def run(action: str = "get_library", **kwargs):
    manager = MediaManagerSkill()
    if action == "get_library":
        return manager.get_media_library()
    return []
