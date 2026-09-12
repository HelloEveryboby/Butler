"""
元数据提取模块 — 通过 ffprobe 提取视频文件的详细信息。
用于媒体库扫描入库、格式信息展示。
"""

import os
import json
import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """视频文件元数据"""
    path: str = ""
    title: str = ""
    container: str = ""          # mp4, mkv, avi, matroska...
    format_long: str = ""        # Matroska / MP4 (MPEG-4 Part 14)...
    video_codec: str = ""        # h264, hevc, vp9, av1...
    video_codec_long: str = ""   # H.264 / AVC / H.265 / HEVC...
    audio_codec: str = ""        # aac, ac3, dts, opus...
    audio_codec_long: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0        # 秒
    file_size: int = 0           # 字节
    bitrate: int = 0             # bps
    video_bitrate: int = 0
    audio_bitrate: int = 0
    audio_channels: int = 0
    audio_sample_rate: int = 0
    audio_language: str = ""
    video_language: str = ""
    has_subtitle: bool = False
    subtitle_languages: list = field(default_factory=list)
    pixel_format: str = ""       # yuv420p, yuv420p10le...
    color_space: str = ""        # bt709, bt2020nc...
    color_range: str = ""        # tv, pc
    rotation: int = 0            # 旋转角度
    created_at: float = 0.0
    modified_at: float = 0.0
    scanned_at: float = 0.0

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: dict) -> 'VideoMetadata':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class MetadataExtractor:
    """视频元数据提取器"""

    # ffprobe 支持的容器格式名映射
    CONTAINER_MAP = {
        "mov,mp4,m4a,3gp,3g2,mj2": "mp4",
        "matroska,webm": "mkv",
        "avi": "avi",
        "flv": "flv",
        "mpegts": "ts",
        "rm": "rmvb",
        "asf": "wmv",
        "ogg": "ogv",
        "mpeg": "mpg",
    }

    def __init__(self, ffprobe_path: str = "ffprobe"):
        self.ffprobe = ffprobe_path

    async def extract(self, file_path: str) -> Optional[VideoMetadata]:
        """
        异步提取视频元数据。
        :param file_path: 视频文件路径
        :return: VideoMetadata 或 None（提取失败时）
        """
        try:
            probe_data = await self._run_ffprobe(file_path)
            return self._parse_probe_data(file_path, probe_data)
        except Exception as e:
            logger.error(f"提取元数据失败 [{file_path}]: {e}")
            return None

    def extract_sync(self, file_path: str) -> Optional[VideoMetadata]:
        """同步版本的元数据提取"""
        try:
            probe_data = self._run_ffprobe_sync(file_path)
            return self._parse_probe_data(file_path, probe_data)
        except Exception as e:
            logger.error(f"提取元数据失败 [{file_path}]: {e}")
            return None

    def _parse_probe_data(self, file_path: str, data: dict) -> VideoMetadata:
        """解析 ffprobe JSON 输出"""
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        video_stream = {}
        audio_stream = {}
        subtitle_streams = []

        for s in streams:
            codec_type = s.get("codec_type", "")
            if codec_type == "video" and not video_stream:
                video_stream = s
            elif codec_type == "audio" and not audio_stream:
                audio_stream = s
            elif codec_type == "sub":
                subtitle_streams.append(s)

        # 容器格式
        format_name = fmt.get("format_name", "")
        container = self.CONTAINER_MAP.get(format_name, format_name.split(",")[0])

        # 帧率
        fps = 0.0
        r_frame_rate = video_stream.get("r_frame_rate", "0/1")
        if "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            try:
                fps = round(float(num) / float(den), 3)
            except (ZeroDivisionError, ValueError):
                fps = 0.0

        # 旋转角度
        rotation = 0
        side_data = video_stream.get("side_data_list", [])
        for sd in side_data:
            if "rotation" in sd:
                rotation = abs(int(sd["rotation"]))

        # 文件时间戳
        stat = os.stat(file_path)

        return VideoMetadata(
            path=file_path,
            title=Path(file_path).stem,
            container=container,
            format_long=fmt.get("format_long_name", ""),
            video_codec=video_stream.get("codec_name", ""),
            video_codec_long=video_stream.get("codec_long_name", ""),
            audio_codec=audio_stream.get("codec_name", ""),
            audio_codec_long=audio_stream.get("codec_long_name", ""),
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=fps,
            duration=float(fmt.get("duration", 0)),
            file_size=int(fmt.get("size", 0)),
            bitrate=int(fmt.get("bit_rate", 0)),
            video_bitrate=int(video_stream.get("bit_rate", 0)),
            audio_bitrate=int(audio_stream.get("bit_rate", 0)),
            audio_channels=int(audio_stream.get("channels", 0)),
            audio_sample_rate=int(audio_stream.get("sample_rate", 0)),
            audio_language=audio_stream.get("tags", {}).get("language", ""),
            video_language=video_stream.get("tags", {}).get("language", ""),
            has_subtitle=len(subtitle_streams) > 0,
            subtitle_languages=[
                s.get("tags", {}).get("language", "und")
                for s in subtitle_streams
            ],
            pixel_format=video_stream.get("pix_fmt", ""),
            color_space=video_stream.get("color_space", ""),
            color_range=video_stream.get("color_range", ""),
            rotation=rotation,
            created_at=stat.st_ctime,
            modified_at=stat.st_mtime,
            scanned_at=__import__("time").time(),
        )

    async def _run_ffprobe(self, file_path: str) -> dict:
        """异步执行 ffprobe"""
        cmd = self._build_cmd(file_path)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {stderr.decode()}")
        return json.loads(stdout.decode())

    def _run_ffprobe_sync(self, file_path: str) -> dict:
        """同步执行 ffprobe"""
        cmd = self._build_cmd(file_path)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {result.stderr}")
        return json.loads(result.stdout)

    def _build_cmd(self, file_path: str) -> list[str]:
        return [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            "-show_entries",
            "stream=index,codec_type,codec_name,codec_long_name,width,height,"
            "r_frame_rate,pix_fmt,bit_rate,channels,sample_rate,tags,"
            "color_space,color_range,side_data_list;"
            "format=format_name,format_long_name,duration,size,bit_rate",
            file_path,
        ]

    def get_resolution_label(self, meta: VideoMetadata) -> str:
        """获取分辨率标签（4K / 2K / 1080p / 720p / 480p）"""
        h = meta.height
        if h >= 2160:
            return "4K"
        elif h >= 1440:
            return "2K"
        elif h >= 1080:
            return "1080p"
        elif h >= 720:
            return "720p"
        elif h >= 480:
            return "480p"
        elif h > 0:
            return f"{h}p"
        return "未知"

    def get_duration_label(self, meta: VideoMetadata) -> str:
        """获取时长标签（如 '1h23m' / '45m'）"""
        total = int(meta.duration)
        if total <= 0:
            return "未知"
        hours, remainder = divmod(total, 3600)
        minutes, _ = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h{minutes:02d}m"
        return f"{minutes}m"

    def get_file_size_label(self, meta: VideoMetadata) -> str:
        """获取文件大小标签（如 '4.2 GB' / '856 MB'）"""
        size = meta.file_size
        if size <= 0:
            return "未知"
        gb = size / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.1f} GB"
        mb = size / (1024 ** 2)
        return f"{mb:.0f} MB"
