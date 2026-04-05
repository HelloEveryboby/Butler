import os
from typing import List, Dict

class MediaManagerSkill:
    def __init__(self, media_roots: List[str] = None):
        self.media_roots = media_roots or ["assets", "data/user_data/media"]

    def get_media_library(self) -> List[Dict[str, str]]:
        """Scans the media roots for MP3, WAV, and JPG files."""
        library = []
        extensions = {'.mp3': 'audio', '.wav': 'audio', '.jpg': 'image', '.jpeg': 'image'}

        for root_dir in self.media_roots:
            if not os.path.exists(root_dir):
                continue

            for root, _, files in os.walk(root_dir):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in extensions:
                        library.append({
                            "name": file,
                            "path": os.path.join(root, file).replace("\\", "/"),
                            "type": extensions[ext]
                        })
        return library

def run(action: str = "get_library", **kwargs):
    manager = MediaManagerSkill()
    if action == "get_library":
        return manager.get_media_library()
    return []
