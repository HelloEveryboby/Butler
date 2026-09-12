"""
mpv 播放器适配器 — 基于 libmpv 的本地原生播放器。

mpv 原生支持的格式（无需任何转码）：
- 容器：MP4, MKV, AVI, MOV, WMV, FLV, WebM, TS, M2TS, RMVB, RM,
        3GP, MPG, MPEG, VOB, ASF, OGV, F4V, SWF, ISO...
- 视频编码：H.264, H.265/HEVC, VP8, VP9, AV1, MPEG-1/2/4,
            Xvid, DivX, RealVideo, WMV9, Theora, ProRes...
- 音频编码：AAC, MP3, AC3, EAC3, DTS, TrueHD, FLAC, Opus,
            Vorbis, WMA, PCM, ALAC, DSD...
- 字幕：SRT, ASS, SSA, PGS, VobSub, DVB, WebVTT, MicroDVD...
"""

import os
import logging
from typing import Optional, Callable

from .player_adapter import (
    PlayerAdapter, PlayerState, MediaInfo,
    AudioTrack, SubtitleTrack,
)

logger = logging.getLogger(__name__)


class MpvAdapter(PlayerAdapter):
    """mpv 播放器适配器（主选方案）"""

    def __init__(self):
        self._player = None
        self._mpv_module = None
        self._state = PlayerState.IDLE
        self._config = {}
        self._callbacks = {
            "state_change": [],
            "position_update": [],
            "media_loaded": [],
            "end_reached": [],
            "error": [],
        }

    # ══════════════════════════════════════════
    # 生命周期
    # ══════════════════════════════════════════

    def is_available(self) -> bool:
        """检测 mpv 是否可用"""
        try:
            import mpv
            self._mpv_module = mpv
            # 尝试创建一个临时实例来验证
            test = mpv.MPV(vo="null", ao="null")
            test.terminate()
            return True
        except Exception as e:
            logger.debug(f"mpv 不可用: {e}")
            return False

    def initialize(self, config: dict) -> None:
        """初始化 mpv 播放器实例"""
        if self._mpv_module is None:
            import mpv
            self._mpv_module = mpv

        self._config = config
        mpv_config = config.get("player", {}).get("mpv", {})
        playback_config = config.get("playback", {})

        self._player = self._mpv_module.MPV(
            # ── 视频输出 ──
            vo=mpv_config.get("vo", "gpu"),
            hwdec=mpv_config.get("hwdec", "auto"),
            gpu_api=mpv_config.get("gpu_api", "auto"),

            # ── 窗口控制 ──
            title="Butler Video Player",
            keep_open=mpv_config.get("keep_open", "yes"),
            cursor_autohide=mpv_config.get("cursor_autohide", 1000),

            # ── 字幕 ──
            sub_auto=mpv_config.get("sub_auto", "fuzzy"),
            sub_font_size=mpv_config.get("sub_font_size", 42),
            sub_color="#FFFFFF",
            sub_border_size=2,
            sub_shadow_offset=1,

            # ── 音频 ──
            audio_channels=mpv_config.get("audio_channels", "stereo"),
            volume=playback_config.get("default_volume", 80),

            # ── 缓冲 ──
            cache=mpv_config.get("cache", "yes"),
            demuxer_max_bytes=mpv_config.get("demuxer_max_bytes", "150M"),
            demuxer_max_back_bytes=mpv_config.get("demuxer_max_back_bytes", "75M"),

            # ── OSD ──
            osd_level=1,
            osd_duration=2000,

            # ── 输入绑定 ──
            input_default_bindings=False,
            input_vo_keyboard=False,
        )

        self._bind_events()
        logger.info("mpv 播放器初始化成功")

    def _bind_events(self) -> None:
        """绑定 mpv 属性观察者，转换为统一事件"""

        @self._player.property_observer('time-pos')
        def _on_position(_name, value):
            if value is not None:
                duration = self._player.duration or 0
                for cb in self._callbacks["position_update"]:
                    try:
                        cb(value, duration)
                    except Exception as e:
                        logger.error(f"position_update 回调错误: {e}")

        @self._player.property_observer('pause')
        def _on_pause(_name, value):
            if value is None:
                return
            new_state = PlayerState.PAUSED if value else PlayerState.PLAYING
            if new_state != self._state:
                self._state = new_state
                self._fire_state_change(new_state)

        @self._player.property_observer('eof-reached')
        def _on_eof(_name, value):
            if value:
                self._state = PlayerState.ENDED
                self._fire_state_change(PlayerState.ENDED)
                for cb in self._callbacks["end_reached"]:
                    try:
                        cb()
                    except Exception as e:
                        logger.error(f"end_reached 回调错误: {e}")

        @self._player.property_observer('idle-active')
        def _on_idle(_name, value):
            if value and self._state != PlayerState.IDLE:
                self._state = PlayerState.IDLE
                self._fire_state_change(PlayerState.IDLE)

        @self._player.property_observer('paused-for-cache')
        def _on_buffering(_name, value):
            if value:
                self._state = PlayerState.BUFFERING
                self._fire_state_change(PlayerState.BUFFERING)
            elif self._state == PlayerState.BUFFERING:
                self._state = PlayerState.PLAYING
                self._fire_state_change(PlayerState.PLAYING)

    def _fire_state_change(self, state: PlayerState) -> None:
        """触发状态变化回调"""
        for cb in self._callbacks["state_change"]:
            try:
                cb(state)
            except Exception as e:
                logger.error(f"state_change 回调错误: {e}")

    def destroy(self) -> None:
        """销毁播放器实例"""
        if self._player:
            try:
                self._player.stop()
                self._player.terminate()
            except Exception:
                pass
            self._player = None
        self._state = PlayerState.IDLE

    # ══════════════════════════════════════════
    # 播放控制
    # ══════════════════════════════════════════

    def load(self, file_path: str, start_time: float = 0) -> None:
        """加载并开始播放视频"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"视频文件不存在: {file_path}")

        self._state = PlayerState.BUFFERING
        self._fire_state_change(PlayerState.BUFFERING)

        kwargs = {}
        if start_time > 0:
            kwargs["start"] = start_time

        self._player.loadfile(file_path, **kwargs)
        logger.info(f"加载视频: {file_path} (起始: {start_time}s)")

    def play(self) -> None:
        self._player.pause = False

    def pause(self) -> None:
        self._player.pause = True

    def toggle_pause(self) -> None:
        self._player.cycle("pause")

    def stop(self) -> None:
        self._player.stop()
        self._state = PlayerState.IDLE
        self._fire_state_change(PlayerState.IDLE)

    def seek(self, time_sec: float, mode: str = "absolute") -> None:
        if mode == "absolute":
            self._player.seek(time_sec, reference="absolute")
        else:
            self._player.seek(time_sec, reference="relative")

    def seek_percent(self, percent: float) -> None:
        self._player.seek(percent, reference="absolute", precision="percent")

    # ══════════════════════════════════════════
    # 速度与音量
    # ══════════════════════════════════════════

    def set_speed(self, speed: float) -> None:
        speed = max(0.25, min(speed, 4.0))
        self._player.speed = speed

    def get_speed(self) -> float:
        return self._player.speed or 1.0

    def set_volume(self, volume: float) -> None:
        self._player.volume = max(0, min(volume, 100))

    def get_volume(self) -> float:
        return self._player.volume or 0.0

    def set_mute(self, muted: bool) -> None:
        self._player.mute = muted

    def is_muted(self) -> bool:
        return bool(self._player.mute)

    # ══════════════════════════════════════════
    # 音轨管理
    # ══════════════════════════════════════════

    def get_audio_tracks(self) -> list[AudioTrack]:
        tracks = []
        try:
            track_list = self._player.track_list
            if track_list:
                for track in track_list:
                    if track.get("type") == "audio":
                        tracks.append(AudioTrack(
                            index=track.get("id", 0),
                            language=track.get("lang", "und"),
                            title=track.get("title", ""),
                            codec=track.get("codec", ""),
                            channels=track.get("demux-channel-count", 2),
                            default=track.get("default", False),
                        ))
        except Exception as e:
            logger.error(f"获取音轨列表失败: {e}")
        return tracks

    def set_audio_track(self, track_index: int) -> None:
        self._player.aid = track_index

    def get_current_audio_track(self) -> int:
        return self._player.aid or 0

    # ══════════════════════════════════════════
    # 字幕管理
    # ══════════════════════════════════════════

    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        tracks = []
        try:
            track_list = self._player.track_list
            if track_list:
                for track in track_list:
                    if track.get("type") == "sub":
                        tracks.append(SubtitleTrack(
                            index=track.get("id", 0),
                            language=track.get("lang", "und"),
                            title=track.get("title", ""),
                            codec=track.get("codec", ""),
                            is_external=track.get("external", False),
                            default=track.get("default", False),
                        ))
        except Exception as e:
            logger.error(f"获取字幕轨道列表失败: {e}")
        return tracks

    def set_subtitle_track(self, track_index: int) -> None:
        self._player.sub = track_index

    def load_external_subtitle(self, file_path: str) -> None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"字幕文件不存在: {file_path}")
        self._player.sub_add(file_path)
        logger.info(f"加载外挂字幕: {file_path}")

    def set_subtitle_visibility(self, visible: bool) -> None:
        self._player.sub_visibility = visible

    def is_subtitle_visible(self) -> bool:
        try:
            return bool(self._player.sub_visibility)
        except Exception:
            return True

    # ══════════════════════════════════════════
    # 视频画面调节
    # ══════════════════════════════════════════

    def set_brightness(self, value: float) -> None:
        self._player.brightness = max(-100, min(value, 100))

    def set_contrast(self, value: float) -> None:
        self._player.contrast = max(-100, min(value, 100))

    def set_saturation(self, value: float) -> None:
        self._player.saturation = max(-100, min(value, 100))

    def set_deinterlace(self, enabled: bool) -> None:
        self._player.deinterlace = "yes" if enabled else "no"

    def screenshot(self, output_path: str, include_subtitles: bool = True) -> bool:
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            self._player.screenshot(
                output_path,
                subtitles=include_subtitles,
                each_frame=False,
            )
            return True
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return False

    # ══════════════════════════════════════════
    # 状态查询
    # ══════════════════════════════════════════

    def get_state(self) -> PlayerState:
        return self._state

    def get_position(self) -> float:
        pos = self._player.time_pos
        return pos if pos is not None else 0.0

    def get_duration(self) -> float:
        dur = self._player.duration
        return dur if dur is not None else 0.0

    def get_media_info(self) -> MediaInfo:
        try:
            return MediaInfo(
                video_codec=self._player.video_codec or "",
                audio_codec=self._player.audio_codec or "",
                container=self._player.current_demuxer or "",
                width=self._player.width or 0,
                height=self._player.height or 0,
                fps=self._player.estimated_vf_fps or 0.0,
                duration=self.get_duration(),
                bitrate=self._player.audio_bitrate or 0,
                file_size=0,
            )
        except Exception:
            return MediaInfo()

    # ══════════════════════════════════════════
    # 事件回调注册
    # ══════════════════════════════════════════

    def on_state_change(self, callback) -> None:
        self._callbacks["state_change"].append(callback)

    def on_position_update(self, callback) -> None:
        self._callbacks["position_update"].append(callback)

    def on_media_loaded(self, callback) -> None:
        self._callbacks["media_loaded"].append(callback)

    def on_end_reached(self, callback) -> None:
        self._callbacks["end_reached"].append(callback)

    def on_error(self, callback) -> None:
        self._callbacks["error"].append(callback)

    # ══════════════════════════════════════════
    # mpv 特有方法
    # ══════════════════════════════════════════

    def get_property(self, name: str):
        """获取 mpv 属性（高级用法）"""
        try:
            return getattr(self._player, name, None)
        except Exception:
            return None

    def set_property(self, name: str, value) -> None:
        """设置 mpv 属性（高级用法）"""
        try:
            setattr(self._player, name, value)
        except Exception as e:
            logger.error(f"设置属性 {name}={value} 失败: {e}")

    def command(self, *args) -> None:
        """发送原始 mpv 命令（高级用法）"""
        try:
            self._player.command(*args)
        except Exception as e:
            logger.error(f"mpv 命令执行失败: {e}")
