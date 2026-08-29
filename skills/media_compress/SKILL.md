---
id: media_compress
name: 图片视频无损压缩
description: 图片与视频无损/视觉无损压缩，支持批量处理、元数据剥离、格式转换
version: 1.0.0
author: Butler
icon: fa-compress
risk: low
keywords: [压缩, compress, 图片, 视频, 无损, png, jpg, webp, mp4, 压缩图片, 压缩视频]
allowed-tools: Bash(python:scripts/compress.py)
---

# 图片视频无损压缩

## 使用方式

```bash
# 单文件压缩（视觉无损）
python scripts/compress.py input.jpg --mode visual-lossless

# 批量压缩整个文件夹
python scripts/compress.py /path/to/photos --mode visual-lossless --output /path/to/output

# 无损压缩
python scripts/compress.py input.png --mode lossless

# 仅分析不压缩
python scripts/compress.py /path/to/photos --analyze

# 自定义参数
python scripts/compress.py input.png --quality 85 --format webp --max-width 1920
```

## 压缩模式

| 模式 | 图片 | 视频 |
|------|------|------|
| `lossless` | 元数据剥离 + zopfli/pngquant 近无损 | 仅去元数据 + 重封装 |
| `visual-lossless` | WebP lossless / pngquant q80+ | H.265 CRF 20 |
| `high` | WebP lossy q75 / JPEG q80 | H.265 CRF 28 |

## 视频输出

- 默认后缀: `_compressed`（如 `video_compressed.mp4`）
- 可通过 `--suffix` 自定义后缀
