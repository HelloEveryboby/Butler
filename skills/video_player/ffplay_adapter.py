"""
FFplay 播放器适配器 — mpv 和 VLC 都不可用时的降级方案。
通过 subprocess 调用 ffplay，功能受限但格式支持同样全面。
注意：ffplay 是独立窗口，无法嵌入 UI，内部控制能力有限。
"""

import os
import signal
import logging
import subprocess
import threading
from typing import Optional

from .player_adapter import (
    PlayerAdapter, PlayerState, MediaInfo,
    AudioTrack, SubtitleTrack,
)

logger = logging.getLogger(__name__)


class FfplayAdapter(PlayerAdapter):
    """FFplay 播放器适配器（降级方案）"""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._state = PlayerState.IDLE
        self._file_path = ""
        self._start_time = 0.0
        self._volume = 80
        self._speed = 1.0
        self._muted = False
        self._duration = 0.0
        self._callbacks = {
            "state_change": [],
            "position_update": [],
            "media_loaded": [],
            "end_reached": [],
            "error": [],
        }

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                ["ffplay", "-version"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            # 尝试 ffplay.exe (Windows)
            try:
                result = subprocess.run(
                    ["ffplay.exe", "-version"],
                    capture_output=True, timeout=5
                )
                return result.returncode == 0
            except Exception:
                return False

    def initialize(self, config: dict) -> None:
        playback_config = config.get("playback", {})
        self._volume = playback_config.get("default_volume", 80)
        logger.info("FFplay 播放器初始化成功 (功能受限模式)")

    def destroy(self) -> None:
        self._kill_process()
        self._state = PlayerState.IDLE

    def _kill_process(self):
        if self._process and self._process.poll() is None:
            try:
                if os.name == "nt":
                    self._process.terminate()
                else:
                    self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=3)
            except Exception:
                self._process.kill()
            self._process = None

    def _monitor_process(self):
        """后台线程监控 ffplay 进程状态"""
        if self._process:
            self._process.wait()
            self._state = PlayerState.ENDED
            for cb in self._callbacks["end_reached"]:
                try:
                    cb()
                except Exception as e:
                    logger.error(f"end_reached 回调错误: {e}")

    # ── 播放控制 ──

    def load(self, file_path: str, start_time: float = 0) -> None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"视频文件不存在: {file_path}")

        self._kill_process()
        self._file_path = file_path
        self._start_time = start_time

        cmd = ["ffplay", "-autoexit"]

        # 音量 (ffplay 用 0-100)
        vol = int(self._volume)
        if self._muted:
            cmd += ["-an"]
        else:
            cmd += ["-volume", str(vol)]

        # 起始位置
        if start_time > 0:
            cmd += ["-ss", str(start_time)]

        # 窗口标题
        cmd += ["-window_title", f"Butler - {os.path.basename(file_path)}"]

        cmd.append(file_path)

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._state = PlayerState.PLAYING

        # 监控进程
        t = threading.Thread(target=self._monitor_process, daemon=True)
        t.start()

        logger.info(f"FFplay 加载视频: {file_path}")

    def play(self) -> None:
        # ffplay 启动即播放，无法暂停后恢复
        pass

    def pause(self) -> None:
        # ffplay 不支持暂停控制
        logger.warning("FFplay 模式不支持暂停操作")

    def toggle_pause(self) -> None:
        logger.warning("FFplay 模式不支持暂停操作")

    def stop(self) -> None:
        self._kill_process()
        self._state = PlayerState.IDLE

    def seek(self, time_sec: float, mode: str = "absolute") -> None:
        # ffplay 不支持运行时 seek
        logger.warning("FFplay 模式不支持进度跳转")

    def seek_percent(self, percent: float) -> None:
        logger.warning("FFplay 模式不支持进度跳转")

    # ── 速度与音量 ──

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.25, min(speed, 4.0))
        logger.warning("FFplay 模式不支持播放速度调节")

    def get_speed(self) -> float:
        return self._speed

    def set_volume(self, volume: float) -> None:
        self._volume = int(max(0, min(volume, 100)))
        logger.warning("FFplay 模式不支持运行时音量调节")

    def get_volume(self) -> float:
        return float(self._volume)

    def set_mute(self, muted: bool) -> None:
        self._muted = muted

    def is_muted(self) -> bool:
        return self._muted

    # ── 音轨（受限） ──

    def get_audio_tracks(self) -> list[AudioTrack]:
        return []

    def set_audio_track(self, track_index: int) -> None:
        logger.warning("FFplay 模式不支持音轨切换")

    def get_current_audio_track(self) -> int:
        return 0

    # ── 字幕（受限） ──

    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        return []

    def set_subtitle_track(self, track_index: int) -> None:
        logger.warning("FFplay 模式不支持字幕切换")

    def load_external_subtitle(self, file_path: str) -> None:
        logger.warning("FFplay 模式不支持外挂字幕")

    def set_subtitle_visibility(self, visible: bool) -> None:
        pass

    def is_subtitle_visible(self) -> bool:
        return True

    # ── 视频画面 ──

    def set_brightness(self, value: float) -> None:
        logger.warning("FFplay 模式不支持画面调节")

    def set_contrast(self, value: float) -> None:
        logger.warning("FFplay 模式不支持画面调节")

    def set_saturation(self, value: float) -> None:
        logger.warning("FFplay 模式不支持画面调节")

    def set_deinterlace(self, enabled: bool) -> None:
        pass

    def screenshot(self, output_path: str, include_subtitles: bool = True) -> bool:
        logger.warning("FFplay 模式不支持截图")
        return False

    # ── 状态查询 ──

    def get_state(self) -> PlayerState:
        if self._process and self._process.poll() is not None:
            return PlayerState.ENDED
        return self._state

    def get_position(self) -> float:
        return 0.0

    def get_duration(self) -> float:
        return self._duration

    def get_media_info(self) -> MediaInfo:
        return MediaInfo()

    # ── 事件回调 ──

    def on_state_change(self, callback):
        self._callbacks["state_change"].append(callback)

    def on_position_update(self, callback):
        self._callbacks["position_update"].append(callback)

    def on_media_loaded(self, callback):
        self._callbacks["media_loaded"].append(callback)

    def on_end_reached(self, callback):
        self._callbacks["end_reached"].append(callback)

    def on_error(self, callback):
        self._callbacks["error"].append(callback)
