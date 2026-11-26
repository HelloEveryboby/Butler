"""``media`` 能力处理器：薄适配到 ``butler.core.media`` 下的各组实现。

所有重资源（播放器、数据库、ffmpeg、Pillow/mss）都在动作被调用时才惰性导入，
保证注册能力本身不产生副作用。
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

_VIDEO: dict[str, Any] | None = None

_CAPTURE_OPS = {
    "full_screenshot",
    "area_screenshot",
    "long_screenshot",
    "start_recording",
    "stop_recording",
}


def _video_config() -> dict:
    from butler.core.media.video_player import load_config

    return load_config()


def _video() -> dict[str, Any]:
    """惰性构建视频库 + 播放控制器。"""
    global _VIDEO
    if _VIDEO is None:
        from butler.core.media.video_player.controller import PlaybackController
        from butler.core.media.video_player.db import VideoDatabase
        from butler.core.media.video_player.library import MediaLibrary

        config = _video_config()
        db_path = os.path.expanduser(
            config.get("cache", {}).get("db_path", "~/.butler/data/video_library.db")
        )
        db = VideoDatabase(db_path)
        library = MediaLibrary(db, config)
        _VIDEO = {
            "db": db,
            "library": library,
            "controller": PlaybackController(db, library, config),
            "config": config,
        }
    return _VIDEO


def _kind(payload: dict[str, Any]) -> str:
    return str(payload.get("kind") or payload.get("type") or "video").lower()


def _video_play(payload: dict[str, Any]) -> dict[str, Any]:
    parts = _video()
    db, controller = parts["db"], parts["controller"]
    video_id = payload.get("id") or payload.get("video_id")
    if not video_id:
        path = payload.get("path") or payload.get("file")
        if not path:
            return {"error": "play 需要 id 或 path"}
        path = os.path.abspath(os.path.expanduser(str(path)))
        existing = db.get_video_by_path(path)
        if existing:
            video_id = existing["id"]
        else:
            from butler.core.media.video_player.metadata import MetadataExtractor

            meta = MetadataExtractor().extract_sync(path)
            if not meta:
                return {"error": f"无法识别媒体文件: {path}"}
            video_id = db.insert_video(meta.to_dict())

    result = controller.play_video(
        str(video_id), resume=bool(payload.get("resume", True))
    )
    start = payload.get("start")
    if start:
        controller.seek(float(start))
    return result


def _music(payload: dict[str, Any], action: str) -> dict[str, Any]:
    from butler.core.media import music_player

    if action == "play":
        index = int(payload.get("index", payload.get("id", 0)) or 0)
        return music_player.play({"index": index})
    if action == "pause":
        return music_player.pause({})
    if action == "list":
        return {"tracks": music_player.get_playlist()}
    if action == "scan":
        music_player.build_library()
        return {"tracks": music_player.get_playlist()}
    return {"kind": "music", "message": "音乐播放状态由前端维护"}


def _list(payload: dict[str, Any]) -> dict[str, Any]:
    kind = _kind(payload)
    if kind == "music":
        return _music(payload, "list")
    if kind == "media":
        from butler.core.media.media_manager import MediaManagerSkill

        return {"library": MediaManagerSkill().get_media_library()}

    db = _video()["db"]
    limit = int(payload.get("limit", 100))
    query = str(payload.get("query") or "")
    videos = db.search_videos(query) if query else db.get_all_videos(limit=limit)
    return {"total": len(videos), "videos": videos}


def _scan(payload: dict[str, Any]) -> dict[str, Any]:
    kind = _kind(payload)
    if kind == "music":
        return _music(payload, "scan")
    if kind == "media":
        from butler.core.media.media_manager import MediaManagerSkill

        return {"library": MediaManagerSkill().get_media_library()}

    parts = _video()
    library = parts["library"]
    dirs = payload.get("dirs") or payload.get("paths")
    if dirs:
        if isinstance(dirs, str):
            dirs = [dirs]
        library.update_scan_dirs([str(d) for d in dirs])
    return asyncio.run(library.full_scan())


def _compress(payload: dict[str, Any]) -> dict[str, Any]:
    from butler.core.media.media_compress import run_compress

    source = payload.get("path") or payload.get("input") or payload.get("file")
    if not source:
        return {"error": "compress 需要 path（文件或目录）"}
    text = run_compress(
        input_path=str(source),
        output=payload.get("output") or payload.get("out"),
        mode=str(payload.get("mode", "visual-lossless")),
        fmt=payload.get("format") or payload.get("fmt"),
        quality=payload.get("quality"),
        max_width=payload.get("max_width"),
        max_height=payload.get("max_height"),
        suffix=str(payload.get("suffix", "_compressed")),
        analyze_only=bool(payload.get("analyze", False)),
        json_output=True,
    )
    try:
        return {"result": json.loads(text)}
    except (TypeError, ValueError):
        return {"result": text}


def _capture(payload: dict[str, Any]) -> dict[str, Any]:
    from butler.core.media.screen_capture import execute

    op = str(payload.get("op") or payload.get("mode") or "full_screenshot")
    if op not in _CAPTURE_OPS:
        return {"error": f"未知截图/录制操作: {op}", "available": sorted(_CAPTURE_OPS)}
    kwargs: dict[str, Any] = {}
    if payload.get("save_path") or payload.get("path"):
        kwargs["save_path"] = payload.get("save_path") or payload.get("path")
    if op == "area_screenshot" and payload.get("rect"):
        kwargs["rect"] = payload["rect"]
    if op == "start_recording":
        kwargs["type"] = payload.get("type", "full")
        if payload.get("rect"):
            kwargs["rect"] = payload["rect"]
    return execute(op, **kwargs)


def handle_media(action: str, payload: dict[str, Any]) -> Any:
    kind = _kind(payload)

    if action == "play":
        return _music(payload, "play") if kind == "music" else _video_play(payload)
    if action == "pause":
        if kind == "music":
            return _music(payload, "pause")
        return _video()["controller"].pause()
    if action == "resume":
        return _video()["controller"].resume()
    if action == "stop":
        return _video()["controller"].stop()
    if action == "next":
        return _video()["controller"].play_next()
    if action == "prev":
        return _video()["controller"].play_prev()
    if action == "status":
        if kind == "music":
            return _music(payload, "status")
        if _VIDEO is None:
            return {"initialized": False, "playing": False}
        return _video()["controller"].get_status()
    if action == "list":
        return _list(payload)
    if action == "scan":
        return _scan(payload)
    if action == "compress":
        return _compress(payload)
    if action == "capture":
        return _capture(payload)
    return {"error": f"未知动作: {action}"}
