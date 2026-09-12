"""
系统默认播放器适配器 — 最终兜底方案。
调用操作系统默认播放器打开视频文件，完全失去内部控制能力。
仅用于 mpv/VLC/ffplay 均不可用的极端情况。
"""

import os
import sys
import logging
import subprocess
import threading

from .player_adapter import (
    PlayerAdapter, PlayerState, MediaInfo,
    AudioTrack, SubtitleTrack,
)

logger = logging.getLogger(__name__)


class SystemAdapter(PlayerAdapter):
    """系统默认播放器适配器（兜底方案，功能极度受限）"""

    def __init__(self):
        self._state = PlayerState.IDLE
        self._process = None
        self._callbacks = {
            "state_change": [],
            "position_update": [],
            "media_loaded": [],
            "end_reached": [],
            "error": [],
        }

    def is_available(self) -> bool:
        return True  # 系统默认播放器始终可用

    def initialize(self, config: dict) -> None:
        logger.warning("使用系统默认播放器（功能受限：无内部控制能力）")

    def destroy(self) -> None:
        self._state = PlayerState.IDLE

    def _open_file(self, file_path: str) -> None:
        """调用系统默认播放器"""
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])

            self._state = PlayerState.PLAYING
            for cb in self._callbacks["state_change"]:
                try:
                    cb(PlayerState.PLAYING)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"系统播放器打开失败: {e}")
            for cb in self._callbacks["error"]:
                try:
                    cb(str(e))
                except Exception:
                    pass

    # ── 播放控制 ──

    def load(self, file_path: str, start_time: float = 0) -> None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"视频文件不存在: {file_path}")
        threading.Thread(target=self._open_file, args=(file_path,), daemon=True).start()
        logger.info(f"系统播放器打开: {file_path}")

    def play(self) -> None: pass
    def pause(self) -> None: pass
    def toggle_pause(self) -> None: pass
    def stop(self) -> None: pass
    def seek(self, time_sec: float, mode: str = "absolute") -> None: pass
    def seek_percent(self, percent: float) -> None: pass

    def set_speed(self, speed: float) -> None: pass
    def get_speed(self) -> float: return 1.0
    def set_volume(self, volume: float) -> None: pass
    def get_volume(self) -> float: return 100.0
    def set_mute(self, muted: bool) -> None: pass
    def is_muted(self) -> bool: return False

    def get_audio_tracks(self) -> list[AudioTrack]: return []
    def set_audio_track(self, track_index: int) -> None: pass
    def get_current_audio_track(self) -> int: return 0

    def get_subtitle_tracks(self) -> list[SubtitleTrack]: return []
    def set_subtitle_track(self, track_index: int) -> None: pass
    def load_external_subtitle(self, file_path: str) -> None: pass
    def set_subtitle_visibility(self, visible: bool) -> None: pass
    def is_subtitle_visible(self) -> bool: return True

    def set_brightness(self, value: float) -> None: pass
    def set_contrast(self, value: float) -> None: pass
    def set_saturation(self, value: float) -> None: pass
    def set_deinterlace(self, enabled: bool) -> None: pass
    def screenshot(self, output_path: str, include_subtitles: bool = True) -> bool: return False

    def get_state(self) -> PlayerState: return self._state
    def get_position(self) -> float: return 0.0
    def get_duration(self) -> float: return 0.0
    def get_media_info(self) -> MediaInfo: return MediaInfo()

    def on_state_change(self, callback): self._callbacks["state_change"].append(callback)
    def on_position_update(self, callback): self._callbacks["position_update"].append(callback)
    def on_media_loaded(self, callback): self._callbacks["media_loaded"].append(callback)
    def on_end_reached(self, callback): self._callbacks["end_reached"].append(callback)
    def on_error(self, callback): self._callbacks["error"].append(callback)
