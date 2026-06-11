import os
import json
import logging
from pathlib import Path

# Butler uses a project-relative path for music library
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MUSIC_LIBRARY_FILE = PROJECT_ROOT / "music_library.json"

logger = logging.getLogger(__name__)

def get_playlist(entities=None, butler_app=None, **kwargs):
    """获取播放列表。"""
    if not MUSIC_LIBRARY_FILE.exists():
        # Build initial library if missing
        build_library()

    try:
        with open(MUSIC_LIBRARY_FILE, "r", encoding='utf-8') as f:
            library = json.load(f)
            # Standardize for UI
            playlist = []
            for i, path in enumerate(library):
                playlist.append({
                    "id": i,
                    "name": os.path.basename(path),
                    "path": path,
                    "artist": "Unknown" # Placeholder
                })
            return playlist
    except Exception as e:
        logger.error(f"Failed to load music library: {e}")
        return []

def update_order(entities=None, butler_app=None, **kwargs):
    """更新并保存新的播放顺序。"""
    new_order = entities.get("new_id_list") if entities else kwargs.get("new_id_list")
    if not new_order:
        return {"success": False, "error": "Missing new_id_list"}

    try:
        # new_order is expected to be a list of paths or objects with paths
        # If it's objects, extract paths
        if new_order and isinstance(new_order[0], dict):
            new_paths = [item["path"] for item in new_order]
        else:
            new_paths = new_order

        with open(MUSIC_LIBRARY_FILE, "w", encoding='utf-8') as f:
            json.dump(new_paths, f, ensure_ascii=False, indent=2)

        logger.info("Music playlist order updated and persisted.")
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to update music order: {e}")
        return {"success": False, "error": str(e)}

def play(entities=None, butler_app=None, **kwargs):
    # Logic to interface with backend audio driver
    index = entities.get("index", 0) if entities else kwargs.get("index", 0)
    # Trigger audio driver here
    return {"status": "playing", "index": index}

def pause(entities=None, butler_app=None, **kwargs):
    return {"status": "paused"}

def build_library():
    """遍历常见目录寻找音乐文件。"""
    music_exts = ('.mp3', '.wav', '.ogg', '.flac')
    found = []
    # Just search in assets/music for now to be safe, or user home
    search_dirs = [PROJECT_ROOT / "assets" / "music", Path.home() / "Music"]

    for d in search_dirs:
        if d.exists():
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(music_exts):
                        found.append(str(Path(root) / f))

    with open(MUSIC_LIBRARY_FILE, "w", encoding='utf-8') as f:
        json.dump(found, f, ensure_ascii=False, indent=2)

def run(action, entities=None, butler_app=None, **kwargs):
    """Entry point for the skill."""
    if action == "get_playlist":
        return get_playlist(entities, butler_app, **kwargs)
    elif action == "update_order":
        return update_order(entities, butler_app, **kwargs)
    elif action == "play":
        return play(entities, butler_app, **kwargs)
    elif action == "pause":
        return pause(entities, butler_app, **kwargs)
    return {"error": f"Unknown action: {action}"}
