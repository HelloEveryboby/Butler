"""
Butler Video Player Skill — 本地原生视频播放器。

基于 mpv/VLC/ffplay 多级降级架构，支持几乎所有视频格式的零转码本地播放。
提供媒体库管理、断点续播、多音轨切换、字幕管理、播放列表等专业级功能。

用法：
    from skills.video_player import setup_video_player

    # 在 Butler 启动时调用
    result = setup_video_player(butler_app)
    # result 包含 controller, library, api_blueprint, ws_handler
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Skill 元信息
SKILL_NAME = "video_player"
SKILL_VERSION = "1.0.0"
SKILL_DESCRIPTION = "本地原生视频播放器 — 支持 20+ 格式零转码播放"


def load_config(config_path: str = None) -> dict:
    """加载 Skill 配置"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")

    default_config = {
        "player": {
            "preferred": "mpv",
            "fallback_chain": ["mpv", "vlc", "ffplay", "system"],
            "mpv": {"vo": "gpu", "hwdec": "auto"},
        },
        "library": {
            "scan_dirs": ["~/Videos", "~/Movies", "~/Downloads"],
            "scan_recursive": True,
        },
        "playback": {
            "default_volume": 80,
            "default_speed": 1.0,
            "resume_enabled": True,
            "preferred_audio_lang": "chi",
            "preferred_subtitle_lang": "chi",
        },
        "cache": {
            "db_path": "~/.butler/data/video_library.db",
        },
        "api": {
            "host": "127.0.0.1",
            "port": 5800,
        },
    }

    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            # 深度合并
            _deep_merge(default_config, user_config)
        except Exception as e:
            logger.warning(f"加载配置失败，使用默认配置: {e}")

    return default_config


def _deep_merge(base: dict, override: dict):
    """深度合并字典"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def setup_video_player(butler_app=None, config: dict = None):
    """
    初始化视频播放 Skill。
    在 Butler 启动时调用此函数完成注册。

    :param butler_app: Butler 应用实例（可选）
    :param config: 自定义配置（可选，默认从 config.json 加载）
    :return: dict 包含所有组件实例
    """
    if config is None:
        config = load_config()

    from .db import VideoDatabase
    from .library import MediaLibrary
    from .controller import PlaybackController

    # 初始化数据库
    db_path = os.path.expanduser(config.get("cache", {}).get("db_path", "~/.butler/data/video_library.db"))
    db = VideoDatabase(db_path)
    logger.info(f"视频数据库: {db_path}")

    # 初始化媒体库
    library = MediaLibrary(db, config)

    # 初始化播放控制器
    controller = PlaybackController(db, library, config)

    # 创建 API
    api_blueprint = None
    ws_handler = None
    try:
        from .api import create_api_blueprint, create_ws_handler
        api_blueprint = create_api_blueprint(controller, library, db, config)
        ws_handler = create_ws_handler(controller)
    except ImportError:
        logger.warning("Flask 未安装，HTTP API 不可用")

    # 如果有 Butler 应用实例，注册 Blueprint
    if butler_app and api_blueprint:
        try:
            if hasattr(butler_app, 'register_blueprint'):
                butler_app.register_blueprint(api_blueprint)
                logger.info("Video Player API 已注册到 Butler")
        except Exception as e:
            logger.warning(f"注册 API Blueprint 失败: {e}")

    result = {
        "controller": controller,
        "library": library,
        "db": db,
        "config": config,
        "api_blueprint": api_blueprint,
        "ws_handler": ws_handler,
        "skill_name": SKILL_NAME,
        "skill_version": SKILL_VERSION,
    }

    logger.info(f"🎬 Video Player Skill v{SKILL_VERSION} 初始化完成")
    return result


def get_skill_info() -> dict:
    """获取 Skill 信息（供 Butler 技能管理器使用）"""
    return {
        "name": SKILL_NAME,
        "version": SKILL_VERSION,
        "description": SKILL_DESCRIPTION,
        "trigger_keywords": [
            "播放视频", "看电影", "看片", "播放",
            "视频库", "媒体库", "影片",
            "暂停", "快进", "快退", "下一集", "上一集",
            "字幕", "音轨", "倍速", "音量", "截图",
            "扫描视频", "添加视频",
        ],
        "dependencies": {
            "python": ["python-mpv>=1.0.5", "watchdog>=3.0"],
            "system": ["mpv", "ffmpeg"],
        },
    }
