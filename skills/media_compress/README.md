# 图片视频无损压缩 (Media Compress)

图片与视频无损/视觉无损/高压缩压缩，支持批量处理。

## 快速使用

```bash
# 压缩单张图片（视觉无损，自动转 WebP）
python scripts/compress.py photo.png

# 压缩整个文件夹
python scripts/compress.py /path/to/photos --output /path/to/output

# 无损压缩（保持原格式）
python scripts/compress.py photo.png --mode lossless

# 高压缩
python scripts/compress.py photo.png --mode high

# 自定义参数
python scripts/compress.py photo.png --quality 80 --format webp --max-width 1920

# 仅分析不压缩
python scripts/compress.py /path/to/photos --analyze

# JSON 输出（供程序调用）
python scripts/compress.py photo.png --json
```

## 压缩模式

| 模式 | 图片 | 视频 |
|------|------|------|
| `lossless` | 元数据剥离 + 格式级优化 | 仅去元数据 + 重封装 |
| `visual-lossless` | 转 WebP lossless (默认) | H.265 CRF 20 |
| `high` | WebP lossy q75 | H.265 CRF 28 |

## 视频输出

- 默认后缀: `_compressed`
- 可通过 `--suffix` 自定义

## 依赖

- Python 3.10+
- Pillow (必须)
- ffmpeg (视频压缩必须)
- pngquant / cwebp / zopflipng (可选，自动下载或降级到纯 Pillow)
