import os
import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional
from PIL import Image
import psutil

try:
    from butler.core.event_bus import event_bus
    from butler.core.runner_server import runner_server
except ImportError:
    event_bus = None
    runner_server = None

class MusicSkill:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("MusicSkill")
        self.current_playlist = []
        self.current_index = -1
        self.active_runner = config.get("default_runner", "cpp_runner")
        self.focus_mode_active = False

        if event_bus:
            event_bus.subscribe("AMBIENT_NOISE_UPDATE", self._handle_ambient_noise)
            event_bus.subscribe("PROCESS_ACTIVITY_UPDATE", self._check_focus_mode)

    def handle_request(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "play":
            return self.play(params.get("path"), params.get("runner"))
        elif action == "pause":
            return self.pause()
        elif action == "volume":
            return self.set_volume(params.get("level", 50))
        elif action == "next":
            return self.next_song()
        elif action == "extract_color":
            return self.extract_album_color(params.get("image_path"))
        return {"status": "error", "message": f"Unknown action: {action}"}

    def play(self, path: str, runner_id: Optional[str] = None) -> Dict[str, Any]:
        target_runner = runner_id or self.active_runner
        if runner_server:
            success, msg = runner_server.send_command(target_runner, "music_play", path)
            if success:
                return {"status": "ok", "runner": target_runner, "path": path}
            return {"status": "error", "message": msg}
        return {"status": "error", "message": "Runner server not available"}

    def pause(self) -> Dict[str, Any]:
        if runner_server:
            success, msg = runner_server.send_command(self.active_runner, "music_pause", "")
            return {"status": "ok" if success else "error"}
        return {"status": "error"}

    def set_volume(self, level: int) -> Dict[str, Any]:
        if runner_server:
            runner_server.send_command(self.active_runner, "music_volume", str(level))
            return {"status": "ok", "level": level}
        return {"status": "error"}

    def next_song(self) -> Dict[str, Any]:
        # Placeholder for playlist logic
        return {"status": "ok", "message": "Next song triggered"}

    def extract_album_color(self, image_path: str) -> Dict[str, Any]:
        if not os.path.exists(image_path):
            return {"status": "error", "message": "Image not found"}

        try:
            img = Image.open(image_path)
            img = img.resize((50, 50))
            result = img.convert('P', palette=Image.ADAPTIVE, colors=1)
            result = result.convert('RGB')
            main_color = result.getpixel((0, 0))
            return {
                "status": "ok",
                "hex": '#{:02x}{:02x}{:02x}'.format(*main_color),
                "rgb": main_color
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _handle_ambient_noise(self, data: Dict[str, Any]):
        level = data.get("level", 0)
        if runner_server:
            runner_server.send_command(self.active_runner, "ambient_noise", str(level))

    def _check_focus_mode(self, data: Dict[str, Any]):
        is_coding = data.get("is_coding", False)
        if is_coding and not self.focus_mode_active:
            self.logger.info("Focus mode triggered. Switching to Lofi.")
            self.focus_mode_active = True
            focus_url = self.config.get("focus_bgm_url", "http://stream.zeno.fm/0r0xa792kwzuv")
            self.play(focus_url)
        elif not is_coding and self.focus_mode_active:
            self.focus_mode_active = False
            self.logger.info("Focus mode ended.")

def handle_request(jarvis_app, config, manifest, **kwargs):
    action = kwargs.get("action", "play")
    params = kwargs.get("params", {})
    skill = MusicSkill(config)
    return skill.handle_request(action, params)
