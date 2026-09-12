# Skill: Video Player

## Description
Butler 本地原生视频播放器。基于 mpv/VLC/ffplay 多级降级架构，支持几乎所有视频格式的零转码本地播放，提供媒体库管理、断点续播、多音轨切换、字幕管理、语音控制等专业级功能。

## Trigger
当用户提到以下关键词时激活本 Skill：
- 播放视频、看电影、看片、播放xxx
- 视频库、媒体库、影片列表
- 暂停、快进、快退、下一集、上一集
- 字幕、音轨、倍速、音量、截图
- 扫描视频、添加视频目录

## Capabilities
- 本地视频文件播放（支持 MP4/MKV/AVI/MOV/WMV/FLV/WebM/TS/RMVB/3GP/VOB 等 20+ 格式）
- 硬件加速解码（自动检测 NVENC/VAAPI/QSV/VideoToolbox）
- 媒体库扫描与管理（增量扫描、文件监听）
- 断点续播（自动记忆播放位置）
- 多音轨切换（国语/英语/导演评论等）
- 多字幕支持（内嵌 ASS/SSA/SRT/PGS + 外挂字幕 + AI 生成字幕）
- 播放速度调节（0.25x ~ 4.0x）
- 视频截图
- 播放列表管理
- 语音指令控制
- 播放历史记录

## Dependencies
- Python >= 3.10
- python-mpv >= 1.0.5 (主选播放器)
- python-vlc >= 3.0 (备选播放器)
- watchdog >= 3.0 (文件监听)
- FFmpeg / ffprobe (元数据提取)

## System Requirements
- mpv (推荐) / VLC (备选) / ffplay (兜底)
- FFmpeg (用于元数据提取和缩略图生成)
