"""
视频压缩引擎 — 无损 / 视觉无损 / 高压缩
依赖: ffmpeg (必须), ffprobe (必须)
"""

import os
import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("video_compress")

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.mts'}

# ---------- 工具检测 ----------
def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")

def find_ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")


# ---------- 视频信息 ----------
class VideoInfo:
    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)
        self.file_size: int = 0
        self.duration: float = 0
        self.width: int = 0
        self.height: int = 0
        self.codec: str = ""
        self.audio_codec: str = ""
        self.bitrate: int = 0
        self.fps: float = 0
        self.format_name: str = ""
        self.has_audio: bool = False
        self.error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "filename": self.filename,
            "file_size": self.file_size,
            "file_size_human": _human_size(self.file_size),
            "duration": round(self.duration, 2),
            "duration_human": _human_duration(self.duration),
            "width": self.width,
            "height": self.height,
            "resolution": f"{self.width}x{self.height}",
            "codec": self.codec,
            "audio_codec": self.audio_codec,
            "bitrate": self.bitrate,
            "bitrate_human": f"{self.bitrate // 1000} kbps" if self.bitrate else "N/A",
            "fps": round(self.fps, 2),
            "format": self.format_name,
            "has_audio": self.has_audio,
            "error": self.error,
        }


def probe_video(path: str) -> VideoInfo:
    """获取视频信息"""
    info = VideoInfo(path)

    if not os.path.exists(path):
        info.error = f"文件不存在: {path}"
        return info

    info.file_size = os.path.getsize(path)

    ffprobe = find_ffprobe()
    if not ffprobe:
        info.error = "ffprobe 未安装"
        return info

    try:
        cmd = [
            ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            info.error = f"ffprobe 失败: {result.stderr[:200]}"
            return info

        data = json.loads(result.stdout)

        # 格式信息
        fmt = data.get("format", {})
        info.duration = float(fmt.get("duration", 0))
        info.bitrate = int(fmt.get("bit_rate", 0))
        info.format_name = fmt.get("format_name", "")

        # 流信息
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and not info.codec:
                info.codec = stream.get("codec_name", "")
                info.width = int(stream.get("width", 0))
                info.height = int(stream.get("height", 0))
                # 帧率
                r_frame_rate = stream.get("r_frame_rate", "0/1")
                if "/" in r_frame_rate:
                    num, den = r_frame_rate.split("/")
                    info.fps = int(num) / max(1, int(den))

            if stream.get("codec_type") == "audio":
                info.has_audio = True
                info.audio_codec = stream.get("codec_name", "")

    except Exception as e:
        info.error = f"解析失败: {e}"

    return info


# ---------- 压缩结果 ----------
class CompressResult:
    def __init__(self, input_path: str):
        self.input_path = input_path
        self.input_size: int = 0
        self.output_path: str = ""
        self.output_size: int = 0
        self.mode: str = ""
        self.codec: str = ""
        self.success: bool = False
        self.error: str = ""
        self.duration: float = 0

    @property
    def saved_bytes(self) -> int:
        return max(0, self.input_size - self.output_size)

    @property
    def saved_percent(self) -> float:
        if self.input_size == 0: return 0
        return (self.saved_bytes / self.input_size) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input_path,
            "output": self.output_path,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "input_size_human": _human_size(self.input_size),
            "output_size_human": _human_size(self.output_size),
            "saved_bytes": self.saved_bytes,
            "saved_bytes_human": _human_size(self.saved_bytes),
            "saved_percent": round(self.saved_percent, 1),
            "mode": self.mode,
            "codec": self.codec,
            "success": self.success,
            "error": self.error,
            "duration": round(self.duration, 2),
        }


# ============================================================
# 压缩函数
# ============================================================

def compress_video(
    input_path: str,
    output_path: Optional[str] = None,
    mode: str = "visual-lossless",
    suffix: str = "_compressed",
    crf: Optional[int] = None,
    preset: Optional[str] = None,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    audio_bitrate: Optional[str] = None,
    copy_audio: bool = False,
) -> CompressResult:
    """
    压缩视频

    Args:
        input_path: 输入文件
        output_path: 输出文件（None 则自动生成）
        mode: lossless / visual-lossless / high
        suffix: 输出文件名后缀（默认 _compressed）
        crf: CRF 值（越小质量越高，None=按模式自动）
        preset: 编码速度（ultrafast~veryslow，None=medium）
        max_width: 最大宽度
        max_height: 最大高度
        audio_bitrate: 音频码率（如 "96k"）
        copy_audio: 是否直接复制音频流
    """
    result = CompressResult(input_path)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        result.error = "ffmpeg 未安装"
        return result

    if not os.path.exists(input_path):
        result.error = f"文件不存在: {input_path}"
        return result

    result.input_size = os.path.getsize(input_path)

    # 生成输出路径
    if not output_path:
        p = Path(input_path)
        output_path = str(p.parent / f"{p.stem}{suffix}{p.suffix}")
    result.output_path = output_path

    # 确定参数
    if mode == "lossless":
        # 纯无损：仅去元数据 + 重封装
        cmd = _build_lossless_cmd(ffmpeg, input_path, output_path)
        result.mode = "lossless"
        result.codec = "copy"
    elif mode == "visual-lossless":
        crf_val = crf or 20
        preset_val = preset or "medium"
        cmd = _build_encode_cmd(ffmpeg, input_path, output_path, crf_val, preset_val,
                                max_width, max_height, audio_bitrate, copy_audio)
        result.mode = "visual-lossless"
        result.codec = "H.265"
    elif mode == "high":
        crf_val = crf or 28
        preset_val = preset or "medium"
        cmd = _build_encode_cmd(ffmpeg, input_path, output_path, crf_val, preset_val,
                                max_width, max_height, audio_bitrate, copy_audio)
        result.mode = "high"
        result.codec = "H.265"
    else:
        result.error = f"未知模式: {mode}"
        return result

    # 执行
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    try:
        logger.info(f"[ffmpeg] {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if proc.returncode != 0:
            result.error = f"ffmpeg 失败: {proc.stderr[-300:]}"
            return result

        if os.path.exists(output_path):
            result.output_size = os.path.getsize(output_path)
            result.success = True
        else:
            result.error = "输出文件未生成"

    except subprocess.TimeoutExpired:
        result.error = "编码超时（>1小时）"
    except Exception as e:
        result.error = f"执行失败: {e}"

    return result


# ============================================================
# ffmpeg 命令构建
# ============================================================

def _build_lossless_cmd(ffmpeg: str, input_path: str, output_path: str) -> List[str]:
    """无损：仅去元数据 + 重封装"""
    return [
        ffmpeg, "-y", "-i", input_path,
        "-map", "0",
        "-c", "copy",           # 直接复制流
        "-map_metadata", "-1",  # 去除元数据
        "-movflags", "+faststart",
        output_path,
    ]


def _build_encode_cmd(
    ffmpeg: str, input_path: str, output_path: str,
    crf: int, preset: str,
    max_width: Optional[int], max_height: Optional[int],
    audio_bitrate: Optional[str], copy_audio: bool,
) -> List[str]:
    """H.265 编码压缩"""
    cmd = [ffmpeg, "-y", "-i", input_path]

    # 视频滤镜（缩放）
    vf_parts = []
    if max_width:
        vf_parts.append(f"scale='min({max_width},iw)':-2")
    if max_height:
        vf_parts.append(f"scale=-2:'min({max_height},ih)'")
    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])

    # 视频编码
    cmd.extend([
        "-c:v", "libx265",
        "-crf", str(crf),
        "-preset", preset,
        "-tag:v", "hvc1",       # Apple 兼容
        "-movflags", "+faststart",
    ])

    # 音频
    if copy_audio:
        cmd.extend(["-c:a", "copy"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", audio_bitrate or "96k"])

    cmd.append(output_path)
    return cmd


# ============================================================
# 分析
# ============================================================

def analyze_video(input_path: str) -> Dict[str, Any]:
    """分析视频，预估压缩效果"""
    info = probe_video(input_path)
    data = info.to_dict()

    if info.error:
        return data

    # 预估
    size = info.file_size
    codec = info.codec.lower()

    # 已经是 H.265/AV1 的压缩空间较小
    if codec in ('hevc', 'h265'):
        lossless_ratio = 0.95  # 仅去元数据
        visual_ratio = 0.80
        high_ratio = 0.60
    elif codec in ('av1', 'vp9'):
        lossless_ratio = 0.95
        visual_ratio = 0.85
        high_ratio = 0.70
    else:
        # H.264 有较大压缩空间
        lossless_ratio = 0.90
        visual_ratio = 0.50
        high_ratio = 0.35

    data["estimate"] = {
        "lossless": {
            "size": int(size * lossless_ratio),
            "human": _human_size(int(size * lossless_ratio)),
            "saved_percent": round((1 - lossless_ratio) * 100, 1),
        },
        "visual_lossless": {
            "size": int(size * visual_ratio),
            "human": _human_size(int(size * visual_ratio)),
            "saved_percent": round((1 - visual_ratio) * 100, 1),
        },
        "high": {
            "size": int(size * high_ratio),
            "human": _human_size(int(size * high_ratio)),
            "saved_percent": round((1 - high_ratio) * 100, 1),
        },
    }

    return data


# ============================================================
# 工具函数
# ============================================================

def _human_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _human_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
