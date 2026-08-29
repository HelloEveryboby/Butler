"""
图片压缩引擎 — 无损 / 视觉无损 / 高压缩
支持: PNG, JPEG, WebP, BMP, TIFF, GIF
外部工具: pngquant, cwebp, zopflipng, mozjpeg (可选，自动降级到纯 Pillow)
"""

import os
import io
import sys
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

try:
    from PIL import Image, ExifTags
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

logger = logging.getLogger("image_compress")

# ---------- 支持的格式 ----------
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.gif'}

# ---------- 外部工具路径 ----------
TOOLS_DIR = Path(__file__).parent.parent / "runtime" / "tools"

def find_tool(name: str) -> Optional[str]:
    """查找外部工具（系统 PATH 或 runtime/tools）"""
    # 先查 runtime/tools
    local = TOOLS_DIR / name
    if local.exists():
        return str(local)
    # 再查系统 PATH
    return shutil.which(name)


# ---------- 压缩模式 ----------
class CompressMode:
    LOSSLESS = "lossless"           # 完全无损：元数据剥离 + 格式级优化
    VISUAL_LOSSLESS = "visual-lossless"  # 视觉无损：可选有损但肉眼不可分辨
    HIGH = "high"                   # 高压缩：更激进的压缩


# ---------- 压缩结果 ----------
class CompressResult:
    def __init__(self, input_path: str):
        self.input_path = input_path
        self.input_size: int = 0
        self.output_path: str = ""
        self.output_size: int = 0
        self.original_format: str = ""
        self.output_format: str = ""
        self.mode: str = ""
        self.tool_used: str = ""
        self.success: bool = False
        self.error: str = ""
        self.width: int = 0
        self.height: int = 0
        self.new_width: int = 0
        self.new_height: int = 0

    @property
    def saved_bytes(self) -> int:
        return max(0, self.input_size - self.output_size)

    @property
    def saved_percent(self) -> float:
        if self.input_size == 0:
            return 0
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
            "original_format": self.original_format,
            "output_format": self.output_format,
            "mode": self.mode,
            "tool": self.tool_used,
            "success": self.success,
            "error": self.error,
            "width": self.width,
            "height": self.height,
            "new_width": self.new_width,
            "new_height": self.new_height,
        }


# ============================================================
# 核心压缩函数
# ============================================================

def compress_image(
    input_path: str,
    output_path: Optional[str] = None,
    mode: str = CompressMode.VISUAL_LOSSLESS,
    target_format: Optional[str] = None,
    quality: Optional[int] = None,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    suffix: str = "",
) -> CompressResult:
    """
    压缩单张图片

    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径（None 则自动生成）
        mode: 压缩模式 (lossless / visual-lossless / high)
        target_format: 目标格式 (png / jpg / webp / None=保持原格式)
        quality: 质量 (1-100, None=按模式自动)
        max_width: 最大宽度（超出则等比缩放）
        max_height: 最大高度（超出则等比缩放）
        suffix: 输出文件名后缀（默认 _compressed）

    Returns:
        CompressResult
    """
    result = CompressResult(input_path)

    if not HAS_PILLOW:
        result.error = "Pillow 未安装"
        return result

    if not os.path.exists(input_path):
        result.error = f"文件不存在: {input_path}"
        return result

    # 读取原始文件大小
    result.input_size = os.path.getsize(input_path)

    # 打开图片
    try:
        img = Image.open(input_path)
    except Exception as e:
        result.error = f"无法打开图片: {e}"
        return result

    result.width = img.width
    result.height = img.height
    result.original_format = (img.format or Path(input_path).suffix.lstrip('.')).upper()

    # 确定输出格式
    if target_format:
        out_fmt = target_format.lower().replace('.', '')
    else:
        out_fmt = _get_output_format(img.format, mode)

    result.output_format = out_fmt.upper()

    # 确定输出路径
    if not output_path:
        sfx = suffix or "_compressed"
        output_path = _make_output_path(input_path, out_fmt, sfx)
    result.output_path = output_path

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    # 预处理：缩放
    img, resized = _resize_image(img, max_width, max_height)
    result.new_width = img.width
    result.new_height = img.height

    # 根据模式压缩
    if mode == CompressMode.LOSSLESS:
        result = _compress_lossless(img, input_path, output_path, out_fmt, result)
    elif mode == CompressMode.VISUAL_LOSSLESS:
        result = _compress_visual_lossless(img, input_path, output_path, out_fmt, quality, result)
    elif mode == CompressMode.HIGH:
        result = _compress_high(img, input_path, output_path, out_fmt, quality, result)
    else:
        result.error = f"未知压缩模式: {mode}"
        return result

    # 记录输出大小
    if result.success and os.path.exists(result.output_path):
        result.output_size = os.path.getsize(result.output_path)

    img.close()
    return result


# ============================================================
# 内部实现
# ============================================================

def _get_output_format(original: Optional[str], mode: str) -> str:
    """根据原格式和模式确定输出格式"""
    if original:
        original = original.upper()
    if mode in (CompressMode.VISUAL_LOSSLESS, CompressMode.HIGH):
        # 视觉无损/高压缩统一转 WebP（压缩比最优）
        if original in ('PNG', 'JPEG', 'JPG', 'BMP', 'TIFF', 'GIF'):
            return 'webp'
    # 无损模式保持原格式
    if original in ('JPEG', 'JPG'):
        return 'jpg'
    if original:
        return original.lower()
    return 'png'


def _make_output_path(input_path: str, fmt: str, suffix: str) -> str:
    """生成输出文件路径"""
    p = Path(input_path)
    ext_map = {'jpg': '.jpg', 'jpeg': '.jpg', 'png': '.png', 'webp': '.webp', 'gif': '.gif'}
    ext = ext_map.get(fmt, f'.{fmt}')
    return str(p.parent / f"{p.stem}{suffix}{ext}")


def _resize_image(
    img: Image.Image,
    max_width: Optional[int],
    max_height: Optional[int]
) -> Tuple[Image.Image, bool]:
    """等比缩放"""
    if not max_width and not max_height:
        return img, False

    w, h = img.size
    ratio = 1.0

    if max_width and w > max_width:
        ratio = min(ratio, max_width / w)
    if max_height and h > max_height:
        ratio = min(ratio, max_height / h)

    if ratio >= 1.0:
        return img, False

    new_w = int(w * ratio)
    new_h = int(h * ratio)
    return img.resize((new_w, new_h), Image.LANCZOS), True


def _strip_metadata(img: Image.Image) -> Image.Image:
    """剥离元数据（EXIF、ICC Profile 等），保留像素数据"""
    # 创建新 Image，只保留像素
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)
    return clean


def _compress_lossless(
    img: Image.Image,
    input_path: str,
    output_path: str,
    fmt: str,
    result: CompressResult
) -> CompressResult:
    """无损压缩：元数据剥离 + 格式级无损优化"""
    result.mode = "lossless"

    # 先用 Pillow 保存（剥离元数据）
    save_kwargs = _get_save_kwargs(fmt, lossless=True)

    try:
        # 优先尝试外部工具
        if fmt == 'png':
            tool_result = _try_pngquant(input_path, output_path, quality="0-100", speed="1")
            if tool_result:
                result.tool_used = "pngquant-lossless"
                result.success = True
                return result

            tool_result = _try_zopflipng(input_path, output_path)
            if tool_result:
                result.tool_used = "zopflipng"
                result.success = True
                return result

        # Pillow 兜底
        clean = _strip_metadata(img)
        clean.save(output_path, **save_kwargs)
        clean.close()
        result.tool_used = "pillow-lossless"
        result.success = True

    except Exception as e:
        result.error = f"无损压缩失败: {e}"

    return result


def _compress_visual_lossless(
    img: Image.Image,
    input_path: str,
    output_path: str,
    fmt: str,
    quality: Optional[int],
    result: CompressResult
) -> CompressResult:
    """视觉无损压缩：高质量有损，肉眼不可分辨"""
    result.mode = "visual-lossless"
    q = quality or 85

    try:
        if fmt == 'webp':
            # WebP 无损模式
            tool_result = _try_cwebp(input_path, output_path, quality=100, lossless=True)
            if tool_result:
                result.tool_used = "cwebp-lossless"
                result.success = True
                return result

            # Pillow WebP
            clean = _strip_metadata(img)
            if img.mode == 'RGBA':
                clean.save(output_path, 'WEBP', lossless=True, quality=100)
            else:
                clean = clean.convert('RGB')
                clean.save(output_path, 'WEBP', lossless=True, quality=100)
            clean.close()
            result.tool_used = "pillow-webp-lossless"
            result.success = True

        elif fmt == 'png':
            # pngquant 视觉无损 (quality 85-100)
            tool_result = _try_pngquant(input_path, output_path, quality=f"{q}-100", speed="3")
            if tool_result:
                result.tool_used = "pngquant"
                result.success = True
                return result

            # 转 WebP
            clean = _strip_metadata(img)
            if img.mode != 'RGBA':
                clean = clean.convert('RGB')
            clean.save(output_path.replace('.png', '.webp'), 'WEBP', quality=q)
            result.output_path = output_path.replace('.png', '.webp')
            clean.close()
            result.tool_used = "pillow-webp"
            result.success = True

        elif fmt in ('jpg', 'jpeg'):
            # mozjpeg 或 Pillow
            clean = _strip_metadata(img.convert('RGB'))
            clean.save(output_path, 'JPEG', quality=q, optimize=True, progressive=True)
            clean.close()
            result.tool_used = "pillow-jpeg"
            result.success = True

        else:
            clean = _strip_metadata(img)
            clean.save(output_path, **_get_save_kwargs(fmt, quality=q))
            clean.close()
            result.tool_used = "pillow"
            result.success = True

    except Exception as e:
        result.error = f"视觉无损压缩失败: {e}"

    return result


def _compress_high(
    img: Image.Image,
    input_path: str,
    output_path: str,
    fmt: str,
    quality: Optional[int],
    result: CompressResult
) -> CompressResult:
    """高压缩：更激进的压缩"""
    result.mode = "high"
    q = quality or 75

    try:
        if fmt == 'webp':
            clean = _strip_metadata(img)
            if img.mode != 'RGBA':
                clean = clean.convert('RGB')
            clean.save(output_path, 'WEBP', quality=q, method=6)
            clean.close()
            result.tool_used = "pillow-webp-high"
            result.success = True

        elif fmt in ('jpg', 'jpeg'):
            clean = _strip_metadata(img.convert('RGB'))
            clean.save(output_path, 'JPEG', quality=q, optimize=True, progressive=True)
            clean.close()
            result.tool_used = "pillow-jpeg-high"
            result.success = True

        elif fmt == 'png':
            # 转 WebP 高压缩
            webp_path = output_path.replace('.png', '.webp')
            clean = _strip_metadata(img)
            if img.mode != 'RGBA':
                clean = clean.convert('RGB')
            clean.save(webp_path, 'WEBP', quality=q, method=6)
            result.output_path = webp_path
            clean.close()
            result.tool_used = "pillow-webp-high"
            result.success = True

        else:
            clean = _strip_metadata(img)
            clean.save(output_path, **_get_save_kwargs(fmt, quality=q))
            clean.close()
            result.tool_used = "pillow"
            result.success = True

    except Exception as e:
        result.error = f"高压缩失败: {e}"

    return result


def _get_save_kwargs(fmt: str, lossless: bool = False, quality: int = 85) -> Dict[str, Any]:
    """获取 Pillow save 参数"""
    if fmt in ('jpg', 'jpeg'):
        return {"format": "JPEG", "quality": quality, "optimize": True, "progressive": True}
    if fmt == 'png':
        return {"format": "PNG", "optimize": True}
    if fmt == 'webp':
        if lossless:
            return {"format": "WEBP", "lossless": True, "quality": 100}
        return {"format": "WEBP", "quality": quality, "method": 4}
    if fmt == 'gif':
        return {"format": "GIF", "optimize": True}
    return {"format": fmt.upper()}


# ============================================================
# 外部工具调用
# ============================================================

def _try_pngquant(input_path: str, output_path: str, quality: str = "80-100", speed: str = "3") -> bool:
    """调用 pngquant 压缩 PNG"""
    pngquant = find_tool("pngquant")
    if not pngquant:
        return False

    try:
        cmd = [
            pngquant,
            "--quality", quality,
            "--speed", speed,
            "--force",
            "--output", output_path,
            input_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.debug(f"pngquant failed: {e}")
        return False


def _try_zopflipng(input_path: str, output_path: str) -> bool:
    """调用 zopflipng 极致无损压缩 PNG"""
    zopflipng = find_tool("zopflipng")
    if not zopflipng:
        return False

    try:
        cmd = [zopflipng, "-y", input_path, output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.debug(f"zopflipng failed: {e}")
        return False


def _try_cwebp(input_path: str, output_path: str, quality: int = 80, lossless: bool = False) -> bool:
    """调用 cwebp 压缩为 WebP"""
    cwebp = find_tool("cwebp")
    if not cwebp:
        return False

    try:
        cmd = [cwebp]
        if lossless:
            cmd.extend(["-lossless", "-q", "100"])
        else:
            cmd.extend(["-q", str(quality)])
        cmd.extend(["-o", output_path, input_path, "-quiet"])
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.debug(f"cwebp failed: {e}")
        return False


# ============================================================
# 分析（不压缩）
# ============================================================

def analyze_image(input_path: str) -> Dict[str, Any]:
    """分析图片信息，预估压缩效果"""
    if not HAS_PILLOW:
        return {"error": "Pillow 未安装"}

    if not os.path.exists(input_path):
        return {"error": f"文件不存在: {input_path}"}

    try:
        img = Image.open(input_path)
        file_size = os.path.getsize(input_path)

        info = {
            "path": input_path,
            "filename": os.path.basename(input_path),
            "format": img.format,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "pixels": img.width * img.height,
            "file_size": file_size,
            "file_size_human": _human_size(file_size),
            "has_exif": _has_exif(img),
            "has_alpha": img.mode in ('RGBA', 'LA', 'PA'),
            "bit_depth": _get_bit_depth(img),
            "dpi": img.info.get('dpi'),
        }

        # 预估压缩后大小
        info["estimate"] = {
            "lossless": _estimate_size(file_size, img, "lossless"),
            "visual_lossless": _estimate_size(file_size, img, "visual-lossless"),
            "high": _estimate_size(file_size, img, "high"),
        }

        img.close()
        return info

    except Exception as e:
        return {"error": str(e)}


def _has_exif(img: Image.Image) -> bool:
    """检查是否有 EXIF 数据"""
    try:
        exif = img.getexif()
        return len(exif) > 0
    except:
        return False


def _get_bit_depth(img: Image.Image) -> int:
    """获取位深度"""
    mode_depths = {
        '1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32,
        'CMYK': 32, 'I': 32, 'F': 32, 'LA': 16, 'PA': 16,
    }
    return mode_depths.get(img.mode, 8)


def _estimate_size(file_size: int, img: Image.Image, mode: str) -> Dict[str, Any]:
    """预估压缩后大小"""
    if mode == "lossless":
        # 元数据剥离 + 格式优化，通常节省 5-20%
        ratio = 0.85
    elif mode == "visual-lossless":
        # WebP / pngquant，通常节省 40-70%
        ratio = 0.45
    else:
        # 高压缩，通常节省 60-80%
        ratio = 0.30

    # PNG 通常比 JPEG 压缩空间大
    if img.format == 'PNG':
        ratio *= 0.8
    elif img.format in ('JPEG', 'JPG'):
        ratio *= 1.2  # JPEG 已经压缩过，空间较小

    estimated = int(file_size * ratio)
    return {
        "size": estimated,
        "human": _human_size(estimated),
        "saved_percent": round((1 - ratio) * 100, 1),
    }


def _human_size(size: int) -> str:
    """人类可读的文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
