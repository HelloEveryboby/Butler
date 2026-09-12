"""
VLC 播放器适配器 — mpv 不可用时的备选方案。
基于 python-vlc 绑定 libvlc，格式支持同样非常全面。
"""

import os
import logging
from typing import Optional

from .player_adapter import (
    PlayerAdapter, PlayerState, MediaInfo,
    AudioTrack, SubtitleTrack,
)

logger = logging.getLogger(__name__)


class VlcAdapter(PlayerAdapter):
    """VLC 播放器适配器（备选方案）"""

    def __init__(self):
        self._instance = None
        self._player = None
        self._media = None
        self._vlc_module = None
        self._state = PlayerState.IDLE
        self._callbacks = {
            "state_change": [],
            "position_update": [],
            "media_loaded": [],
            "end_reached": [],
            "error": [],
        }
        self._volume = 80
        self._speed = 1.0
        self._muted = False

    def is_available(self) -> bool:
        try:
            import vlc
            self._vlc_module = vlc
            instance = vlc.Instance("--no-video-title-show")
            player = instance.media_player_new()
            player.release()
            instance.release()
            return True
        except Exception as e:
            logger.debug(f"VLC 不可用: {e}")
            return False

    def initialize(self, config: dict) -> None:
        if self._vlc_module is None:
            import vlc
            self._vlc_module = vlc

        vlc_config = config.get("player", {}).get("vlc", {})
        playback_config = config.get("playback", {})
        self._volume = playback_config.get("default_volume", 80)

        vlc_args = [
            "--no-video-title-show",
            "--quiet",
            f"--network-caching={vlc_config.get('network_caching', 1000)}",
            f"--file-caching={vlc_config.get('file_caching', 1000)}",
        ]

        self._instance = self._vlc_module.Instance(*vlc_args)
        self._player = self._instance.media_player_new()
        self._player.audio_set_volume(self._volume)

        # 绑定事件
        event_manager = self._player.event_manager()
        event_manager.event_attach(
            self._vlc_module.EventType.MediaPlayerEndReached,
            self._on_end_reached
        )
        event_manager.event_attach(
            self._vlc_module.EventType.MediaPlayerPlaying,
            lambda _: self._set_state(PlayerState.PLAYING)
        )
        event_manager.event_attach(
            self._vlc_module.EventType.MediaPlayerPaused,
            lambda _: self._set_state(PlayerState.PAUSED)
        )

        logger.info("VLC 播放器初始化成功")

    def _on_end_reached(self, event):
        self._set_state(PlayerState.ENDED)
        for cb in self._callbacks["end_reached"]:
            try:
                cb()
            except Exception as e:
                logger.error(f"end_reached 回调错误: {e}")

    def _set_state(self, state: PlayerState):
        if state != self._state:
            self._state = state
            for cb in self._callbacks["state_change"]:
                try:
                    cb(state)
                except Exception as e:
                    logger.error(f"state_change 回调错误: {e}")

    def destroy(self) -> None:
        if self._player:
            self._player.stop()
            self._player.release()
            self._player = None
        if self._instance:
            self._instance.release()
            self._instance = None
        self._state = PlayerState.IDLE

    # ── 播放控制 ──

    def load(self, file_path: str, start_time: float = 0) -> None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"视频文件不存在: {file_path}")
        self._media = self._instance.media_new(file_path)
        if start_time > 0:
            self._media.add_option(f"start-time={start_time}")
        self._player.set_media(self._media)
        self._player.play()
        self._set_state(PlayerState.BUFFERING)
        logger.info(f"VLC 加载视频: {file_path}")

    def play(self) -> None:
        self._player.play()
        self._set_state(PlayerState.PLAYING)

    def pause(self) -> None:
        self._player.pause()
        self._set_state(PlayerState.PAUSED)

    def toggle_pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()
        self._set_state(PlayerState.IDLE)

    def seek(self, time_sec: float, mode: str = "absolute") -> None:
        if mode == "absolute":
            self._player.set_time(int(time_sec * 1000))
        else:
            current = self._player.get_time()
            self._player.set_time(int(current + time_sec * 1000))

    def seek_percent(self, percent: float) -> None:
        self._player.set_position(percent / 100.0)

    # ── 速度与音量 ──

    def set_speed(self, speed: float) -> None:
        speed = max(0.25, min(speed, 4.0))
        self._player.set_rate(speed)
        self._speed = speed

    def get_speed(self) -> float:
        return self._player.get_rate() or self._speed

    def set_volume(self, volume: float) -> None:
        self._volume = int(max(0, min(volume, 100)))
        self._player.audio_set_volume(self._volume)

    def get_volume(self) -> float:
        vol = self._player.audio_get_volume()
        return float(vol) if vol >= 0 else self._volume

    def set_mute(self, muted: bool) -> None:
        self._player.audio_set_mute(muted)
        self._muted = muted

    def is_muted(self) -> bool:
        return self._player.audio_get_mute() or self._muted

    # ── 音轨 ──

    def get_audio_tracks(self) -> list[AudioTrack]:
        tracks = []
        try:
            desc = self._player.audio_get_track_description()
            if desc:
                for t in desc:
                    tracks.append(AudioTrack(
                        index=t[0],
                        language="",
                        title=t[1].decode("utf-8", errors="replace") if isinstance(t[1], bytes) else str(t[1]),
                        codec="",
                        channels=0,
                        default=(t[0] == -1),
                    ))
        except Exception as e:
            logger.error(f"VLC 获取音轨失败: {e}")
        return tracks

    def set_audio_track(self, track_index: int) -> None:
        self._player.audio_set_track(track_index)

    def get_current_audio_track(self) -> int:
        return self._player.audio_get_track()

    # ── 字幕 ──

    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        tracks = []
        try:
            desc = self._player.video_get_spu_description()
            if desc:
                for t in desc:
                    tracks.append(SubtitleTrack(
                        index=t[0],
                        language="",
                        title=t[1].decode("utf-8", errors="replace") if isinstance(t[1], bytes) else str(t[1]),
                        codec="",
                        is_external=False,
                        default=(t[0] == -1),
                    ))
        except Exception as e:
            logger.error(f"VLC 获取字幕轨道失败: {e}")
        return tracks

    def set_subtitle_track(self, track_index: int) -> None:
        self._player.video_set_spu(track_index)

    def load_external_subtitle(self, file_path: str) -> None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"字幕文件不存在: {file_path}")
        self._player.video_set_subtitle_file(file_path)

    def set_subtitle_visibility(self, visible: bool) -> None:
        if visible:
            self._player.video_set_spu(0)
        else:
            self._player.video_set_spu(-1)

    def is_subtitle_visible(self) -> bool:
        return self._player.video_get_spu() != -1

    # ── 视频画面 ──

    def set_brightness(self, value: float) -> None:
        self._player.video_set_adjust_float(self._vlc_module.VideoAdjustOption.Brightness, value)

    def set_contrast(self, value: float) -> None:
        self._player.video_set_adjust_float(self._vlc_module.VideoAdjustOption.Contrast, value)

    def set_saturation(self, value: float) -> None:
        self._player.video_set_adjust_float(self._vlc_module.VideoAdjustOption.Saturation, value)

    def set_deinterlace(self, enabled: bool) -> None:
        mode = "blend" if enabled else "none"
        self._player.video_set_deinterlace(mode)

    def screenshot(self, output_path: str, include_subtitles: bool = True) -> bool:
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            # VLC 截图通过命令行更可靠
            self._player.video_take_snapshot(0, output_path, 0, 0)
            return True
        except Exception as e:
            logger.error(f"VLC 截图失败: {e}")
            return False

    # ── 状态查询 ──

    def get_state(self) -> PlayerState:
        return self._state

    def get_position(self) -> float:
        t = self._player.get_time()
        return t / 1000.0 if t and t > 0 else 0.0

    def get_duration(self) -> float:
        d = self._player.get_length()
        return d / 1000.0 if d and d > 0 else 0.0

    def get_media_info(self) -> MediaInfo:
        try:
            w = self._player.video_get_width() or 0
            h = self._player.video_get_height() or 0
            return MediaInfo(
                width=w,
                height=h,
                duration=self.get_duration(),
            )
        except Exception:
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
