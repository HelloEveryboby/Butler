"""
播放器抽象接口层。
定义统一的播放器接口，屏蔽 mpv/VLC/ffplay 实现差异。
Butler 上层代码只依赖此接口，不直接接触底层播放器。
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field


class PlayerState(Enum):
    """播放器状态枚举"""
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    SEEKING = "seeking"
    BUFFERING = "buffering"
    ENDED = "ended"
    ERROR = "error"


@dataclass
class MediaInfo:
    """视频媒体信息"""
    video_codec: str = ""       # h264, hevc, vp9, av1...
    audio_codec: str = ""       # aac, ac3, dts, opus...
    container: str = ""         # mp4, mkv, avi...
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0      # 秒
    bitrate: int = 0
    file_size: int = 0


@dataclass
class AudioTrack:
    """音轨信息"""
    index: int = 0
    language: str = ""          # "chi", "eng", "jpn"...
    title: str = ""             # "导演评论" / "国语配音"
    codec: str = ""
    channels: int = 2           # 2=立体声, 6=5.1, 8=7.1
    default: bool = False


@dataclass
class SubtitleTrack:
    """字幕轨道信息"""
    index: int = 0
    language: str = ""
    title: str = ""
    codec: str = ""             # "ass", "srt", "pgs", "vobsub"...
    is_external: bool = False
    default: bool = False


@dataclass
class PlayerConfig:
    """播放器配置"""
    preferred: str = "mpv"
    fallback_chain: list = field(default_factory=lambda: ["mpv", "vlc", "ffplay", "system"])
    default_volume: int = 80
    default_speed: float = 1.0
    hwdec: str = "auto"
    vo: str = "gpu"


class PlayerAdapter(ABC):
    """播放器抽象基类 — 所有播放器适配器必须实现此接口"""

    # ══════════════════════════════════════════
    # 生命周期
    # ══════════════════════════════════════════

    @abstractmethod
    def initialize(self, config: dict) -> None:
        """初始化播放器实例"""
        ...

    @abstractmethod
    def destroy(self) -> None:
        """销毁播放器实例，释放资源"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检测此播放器是否可用（依赖是否安装）"""
        ...

    # ══════════════════════════════════════════
    # 播放控制
    # ══════════════════════════════════════════

    @abstractmethod
    def load(self, file_path: str, start_time: float = 0) -> None:
        """
        加载视频文件。
        :param file_path: 视频文件绝对路径
        :param start_time: 起始播放位置（秒），用于断点续播
        """
        ...

    @abstractmethod
    def play(self) -> None:
        """继续播放"""
        ...

    @abstractmethod
    def pause(self) -> None:
        """暂停播放"""
        ...

    @abstractmethod
    def toggle_pause(self) -> None:
        """切换暂停/播放"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止播放"""
        ...

    @abstractmethod
    def seek(self, time_sec: float, mode: str = "absolute") -> None:
        """
        跳转到指定时间。
        :param time_sec: 目标时间（秒）
        :param mode: "absolute" 绝对位置 / "relative" 相对偏移
        """
        ...

    @abstractmethod
    def seek_percent(self, percent: float) -> None:
        """按百分比跳转（0.0 ~ 100.0）"""
        ...

    # ══════════════════════════════════════════
    # 速度与音量
    # ══════════════════════════════════════════

    @abstractmethod
    def set_speed(self, speed: float) -> None:
        """设置播放速度：0.25 / 0.5 / 0.75 / 1.0 / 1.25 / 1.5 / 2.0 / 3.0 / 4.0"""
        ...

    @abstractmethod
    def get_speed(self) -> float:
        """获取当前播放速度"""
        ...

    @abstractmethod
    def set_volume(self, volume: float) -> None:
        """设置音量（0 ~ 100）"""
        ...

    @abstractmethod
    def get_volume(self) -> float:
        """获取当前音量"""
        ...

    @abstractmethod
    def set_mute(self, muted: bool) -> None:
        """设置静音"""
        ...

    @abstractmethod
    def is_muted(self) -> bool:
        """是否静音"""
        ...

    # ══════════════════════════════════════════
    # 音轨管理
    # ══════════════════════════════════════════

    @abstractmethod
    def get_audio_tracks(self) -> list[AudioTrack]:
        """获取所有音轨列表"""
        ...

    @abstractmethod
    def set_audio_track(self, track_index: int) -> None:
        """切换音轨"""
        ...

    @abstractmethod
    def get_current_audio_track(self) -> int:
        """获取当前音轨索引"""
        ...

    # ══════════════════════════════════════════
    # 字幕管理
    # ══════════════════════════════════════════

    @abstractmethod
    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        """获取所有字幕轨道（内嵌 + 外挂）"""
        ...

    @abstractmethod
    def set_subtitle_track(self, track_index: int) -> None:
        """切换字幕轨道"""
        ...

    @abstractmethod
    def load_external_subtitle(self, file_path: str) -> None:
        """加载外挂字幕文件"""
        ...

    @abstractmethod
    def set_subtitle_visibility(self, visible: bool) -> None:
        """开关字幕显示"""
        ...

    @abstractmethod
    def is_subtitle_visible(self) -> bool:
        """字幕是否可见"""
        ...

    # ══════════════════════════════════════════
    # 视频画面调节
    # ══════════════════════════════════════════

    @abstractmethod
    def set_brightness(self, value: float) -> None:
        """亮度调节（-100 ~ 100）"""
        ...

    @abstractmethod
    def set_contrast(self, value: float) -> None:
        """对比度调节（-100 ~ 100）"""
        ...

    @abstractmethod
    def set_saturation(self, value: float) -> None:
        """饱和度调节（-100 ~ 100）"""
        ...

    @abstractmethod
    def set_deinterlace(self, enabled: bool) -> None:
        """反交错开关"""
        ...

    @abstractmethod
    def screenshot(self, output_path: str, include_subtitles: bool = True) -> bool:
        """截图保存，返回是否成功"""
        ...

    # ══════════════════════════════════════════
    # 状态查询
    # ══════════════════════════════════════════

    @abstractmethod
    def get_state(self) -> PlayerState:
        """获取当前播放状态"""
        ...

    @abstractmethod
    def get_position(self) -> float:
        """获取当前播放位置（秒）"""
        ...

    @abstractmethod
    def get_duration(self) -> float:
        """获取视频总时长（秒）"""
        ...

    @abstractmethod
    def get_media_info(self) -> MediaInfo:
        """获取当前播放媒体的详细信息"""
        ...

    # ══════════════════════════════════════════
    # 事件回调注册
    # ══════════════════════════════════════════

    @abstractmethod
    def on_state_change(self, callback) -> None:
        """注册状态变化回调 callback(state: PlayerState)"""
        ...

    @abstractmethod
    def on_position_update(self, callback) -> None:
        """注册位置更新回调 callback(position: float, duration: float)"""
        ...

    @abstractmethod
    def on_media_loaded(self, callback) -> None:
        """注册媒体加载完成回调 callback(info: MediaInfo)"""
        ...

    @abstractmethod
    def on_end_reached(self, callback) -> None:
        """注册播放结束回调 callback()"""
        ...

    @abstractmethod
    def on_error(self, callback) -> None:
        """注册错误回调 callback(error_msg: str)"""
        ...


def create_player(config: dict) -> PlayerAdapter:
    """
    工厂函数：自动选择最佳可用播放器。
    按优先级尝试 mpv → VLC → ffplay → 系统默认播放器。
    """
    from .mpv_adapter import MpvAdapter
    from .vlc_adapter import VlcAdapter
    from .ffplay_adapter import FfplayAdapter
    from .system_adapter import SystemAdapter

    chain = config.get("player", {}).get("fallback_chain", ["mpv", "vlc", "ffplay", "system"])

    adapter_map = {
        "mpv": MpvAdapter,
        "vlc": VlcAdapter,
        "ffplay": FfplayAdapter,
        "system": SystemAdapter,
    }

    for name in chain:
        cls = adapter_map.get(name)
        if cls is None:
            continue
        try:
            adapter = cls()
            if adapter.is_available():
                adapter.initialize(config)
                return adapter
        except Exception:
            continue

    # 兜底：系统默认播放器（一定可用，但失去内部控制能力）
    adapter = SystemAdapter()
    adapter.initialize(config)
    return adapter
