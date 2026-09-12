"""
REST API + WebSocket 端点 — 视频播放 Skill 的 HTTP 接口层。
基于 Flask Blueprint，可集成到 Butler 的 Web 服务中。
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_api_blueprint(controller, library, db, config):
    """
    创建 Flask Blueprint，注册所有视频播放相关 API 端点。
    :param controller: PlaybackController 实例
    :param library: MediaLibrary 实例
    :param db: VideoDatabase 实例
    :param config: 配置字典
    :return: Flask Blueprint
    """
    try:
        from flask import Blueprint, request, jsonify, Response, redirect
    except ImportError:
        logger.error("Flask 未安装，无法创建 API Blueprint")
        return None

    api = Blueprint('video_api', __name__, url_prefix='/api/video')

    # ── 辅助函数 ──

    def success(data=None, status=200):
        return jsonify({"success": True, "data": data}), status

    def error(msg, status=400):
        return jsonify({"success": False, "error": msg}), status

    # ══════════════════════════════════════════
    # 媒体库
    # ══════════════════════════════════════════

    @api.route('/library', methods=['GET'])
    def get_library():
        """获取媒体库列表"""
        search = request.args.get('search', '')
        sort = request.args.get('sort', 'title')
        order = request.args.get('order', 'ASC')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        favorite = request.args.get('favorite', '').lower() == 'true'

        valid_sorts = {'title', 'duration', 'file_size', 'scanned_at', 'modified_at', 'width'}
        if sort not in valid_sorts:
            sort = 'title'
        order = 'DESC' if order.upper() == 'DESC' else 'ASC'

        offset = (page - 1) * per_page
        videos = db.get_all_videos(
            order_by=f"{sort} {order}",
            limit=per_page,
            offset=offset,
            search=search,
            favorite_only=favorite,
        )
        total = db.count_videos(search=search, favorite_only=favorite)

        return success({
            "videos": videos,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        })

    @api.route('/library/recent', methods=['GET'])
    def get_recent():
        """获取最近添加"""
        limit = int(request.args.get('limit', 20))
        return success(library.get_recently_added(limit))

    @api.route('/library/history', methods=['GET'])
    def get_history():
        """获取播放历史"""
        limit = int(request.args.get('limit', 50))
        return success(library.get_recently_played(limit))

    @api.route('/library/stats', methods=['GET'])
    def get_stats():
        """获取媒体库统计"""
        return success(library.get_library_stats())

    @api.route('/scan', methods=['POST'])
    async def trigger_scan():
        """触发媒体库扫描"""
        result = await library.full_scan()
        return success(result)

    # ══════════════════════════════════════════
    # 视频详情
    # ══════════════════════════════════════════

    @api.route('/info/<video_id>', methods=['GET'])
    def get_video_info(video_id):
        """获取视频详情"""
        video = library.get_video_info(video_id)
        if not video:
            return error("视频不存在", 404)
        # 补充字幕信息
        from .subtitle_manager import SubtitleManager
        sub_mgr = SubtitleManager()
        video['available_subtitles'] = sub_mgr.find_subtitles(video['path'])
        return success(video)

    @api.route('/<video_id>', methods=['DELETE'])
    def delete_video(video_id):
        """删除视频记录"""
        if library.delete_video(video_id):
            return success({"deleted": video_id})
        return error("视频不存在", 404)

    @api.route('/<video_id>/favorite', methods=['POST'])
    def toggle_favorite(video_id):
        """切换收藏"""
        new_state = library.toggle_favorite(video_id)
        return success({"is_favorite": new_state})

    @api.route('/<video_id>/rescan', methods=['POST'])
    async def rescan_video(video_id):
        """重新扫描视频元数据"""
        result = await library.rescan_video(video_id)
        if result:
            return success(result)
        return error("视频不存在或扫描失败", 404)

    # ══════════════════════════════════════════
    # 播放控制
    # ══════════════════════════════════════════

    @api.route('/play/<video_id>', methods=['POST'])
    def play_video(video_id):
        """播放视频"""
        resume = request.args.get('resume', 'true').lower() != 'false'
        result = controller.play_video(video_id, resume=resume)
        if "error" in result:
            return error(result["error"], 404)
        return success(result)

    @api.route('/pause', methods=['POST'])
    def pause():
        return success(controller.pause())

    @api.route('/resume', methods=['POST'])
    def resume():
        return success(controller.resume())

    @api.route('/toggle', methods=['POST'])
    def toggle():
        return success(controller.toggle_pause())

    @api.route('/stop', methods=['POST'])
    def stop():
        return success(controller.stop())

    @api.route('/seek', methods=['POST'])
    def seek():
        data = request.get_json(silent=True) or {}
        position = float(data.get('position', 0))
        return success(controller.seek(position))

    @api.route('/seek/relative', methods=['POST'])
    def seek_relative():
        data = request.get_json(silent=True) or {}
        offset = float(data.get('offset', 0))
        return success(controller.seek_relative(offset))

    @api.route('/seek/percent', methods=['POST'])
    def seek_percent():
        data = request.get_json(silent=True) or {}
        percent = float(data.get('percent', 0))
        return success(controller.seek_percent(percent))

    # ══════════════════════════════════════════
    # 速度 / 音量
    # ══════════════════════════════════════════

    @api.route('/speed', methods=['POST'])
    def set_speed():
        data = request.get_json(silent=True) or {}
        speed = float(data.get('speed', 1.0))
        return success(controller.set_speed(speed))

    @api.route('/volume', methods=['POST'])
    def set_volume():
        data = request.get_json(silent=True) or {}
        volume = float(data.get('volume', 80))
        return success(controller.set_volume(volume))

    @api.route('/mute', methods=['POST'])
    def set_mute():
        data = request.get_json(silent=True) or {}
        muted = bool(data.get('muted', True))
        return success(controller.set_mute(muted))

    # ══════════════════════════════════════════
    # 音轨 / 字幕
    # ══════════════════════════════════════════

    @api.route('/audio/tracks', methods=['GET'])
    def get_audio_tracks():
        status = controller.get_status()
        return success(status.get("audio_tracks", []))

    @api.route('/audio/track', methods=['POST'])
    def set_audio_track():
        data = request.get_json(silent=True) or {}
        index = int(data.get('index', 0))
        return success(controller.set_audio_track(index))

    @api.route('/subtitle/tracks', methods=['GET'])
    def get_subtitle_tracks():
        status = controller.get_status()
        return success(status.get("subtitle_tracks", []))

    @api.route('/subtitle/track', methods=['POST'])
    def set_subtitle_track():
        data = request.get_json(silent=True) or {}
        index = int(data.get('index', 0))
        return success(controller.set_subtitle_track(index))

    @api.route('/subtitle/toggle', methods=['POST'])
    def toggle_subtitle():
        return success(controller.toggle_subtitle())

    @api.route('/subtitle/load', methods=['POST'])
    def load_subtitle():
        data = request.get_json(silent=True) or {}
        path = data.get('path', '')
        if not path:
            return error("缺少字幕路径")
        return success(controller.load_subtitle(path))

    # ══════════════════════════════════════════
    # 播放列表
    # ══════════════════════════════════════════

    @api.route('/playlists', methods=['GET'])
    def get_playlists():
        return success(db.get_playlists())

    @api.route('/playlists', methods=['POST'])
    def create_playlist():
        data = request.get_json(silent=True) or {}
        name = data.get('name', '')
        if not name:
            return error("缺少播放列表名称")
        pid = db.create_playlist(name, data.get('description', ''))
        return success({"id": pid, "name": name}, 201)

    @api.route('/playlists/<playlist_id>', methods=['GET'])
    def get_playlist_videos(playlist_id):
        videos = db.get_playlist_videos(playlist_id)
        return success(videos)

    @api.route('/playlists/<playlist_id>/add', methods=['POST'])
    def add_to_playlist(playlist_id):
        data = request.get_json(silent=True) or {}
        video_id = data.get('video_id', '')
        if not video_id:
            return error("缺少 video_id")
        db.add_to_playlist(playlist_id, video_id)
        return success({"added": video_id})

    @api.route('/playlists/<playlist_id>/play', methods=['POST'])
    def play_playlist(playlist_id):
        data = request.get_json(silent=True) or {}
        start_index = int(data.get('start_index', 0))
        result = controller.play_playlist(playlist_id, start_index)
        if "error" in result:
            return error(result["error"])
        return success(result)

    @api.route('/playlists/<playlist_id>', methods=['DELETE'])
    def delete_playlist(playlist_id):
        db.delete_playlist(playlist_id)
        return success({"deleted": playlist_id})

    @api.route('/next', methods=['POST'])
    def play_next():
        result = controller.play_next()
        if "error" in result:
            return error(result["error"])
        return success(result)

    @api.route('/prev', methods=['POST'])
    def play_prev():
        result = controller.play_prev()
        if "error" in result:
            return error(result["error"])
        return success(result)

    # ══════════════════════════════════════════
    # 视频画面
    # ══════════════════════════════════════════

    @api.route('/screenshot', methods=['POST'])
    def take_screenshot():
        data = request.get_json(silent=True) or {}
        output_dir = data.get('output_dir')
        result = controller.screenshot(output_dir)
        if result.get("success"):
            return success(result)
        return error(result.get("error", "截图失败"))

    @api.route('/brightness', methods=['POST'])
    def set_brightness():
        data = request.get_json(silent=True) or {}
        value = float(data.get('value', 0))
        return success(controller.set_brightness(value))

    @api.route('/contrast', methods=['POST'])
    def set_contrast():
        data = request.get_json(silent=True) or {}
        value = float(data.get('value', 0))
        return success(controller.set_contrast(value))

    # ══════════════════════════════════════════
    # 播放器状态
    # ══════════════════════════════════════════

    @api.route('/status', methods=['GET'])
    def get_status():
        return success(controller.get_status())

    @api.route('/resume/<video_id>', methods=['GET'])
    def get_resume(video_id):
        return success(controller.get_resume_point(video_id))

    return api


def create_ws_handler(controller):
    """
    创建 WebSocket 消息处理器。
    可集成到 Butler 的 WebSocket 服务中。
    """

    def handle_ws_message(message: dict) -> dict:
        """
        处理来自前端的 WebSocket 消息。
        :param message: {"type": "command", "action": "...", ...}
        :return: 响应字典
        """
        action = message.get("action", "")
        params = {k: v for k, v in message.items() if k not in ("type", "action")}

        handlers = {
            "play": lambda: controller.play_video(params.get("video_id", "")),
            "pause": lambda: controller.pause(),
            "resume": lambda: controller.resume(),
            "toggle": lambda: controller.toggle_pause(),
            "stop": lambda: controller.stop(),
            "seek": lambda: controller.seek(float(params.get("position", 0))),
            "seek_relative": lambda: controller.seek_relative(float(params.get("offset", 0))),
            "seek_percent": lambda: controller.seek_percent(float(params.get("percent", 0))),
            "speed": lambda: controller.set_speed(float(params.get("value", 1.0))),
            "volume": lambda: controller.set_volume(float(params.get("value", 80))),
            "mute": lambda: controller.set_mute(bool(params.get("muted", True))),
            "audio_track": lambda: controller.set_audio_track(int(params.get("index", 0))),
            "subtitle_track": lambda: controller.set_subtitle_track(int(params.get("index", 0))),
            "subtitle_toggle": lambda: controller.toggle_subtitle(),
            "next": lambda: controller.play_next(),
            "prev": lambda: controller.play_prev(),
            "screenshot": lambda: controller.screenshot(),
            "status": lambda: controller.get_status(),
        }

        handler = handlers.get(action)
        if handler:
            try:
                result = handler()
                return {"type": "response", "action": action, "success": True, "data": result}
            except Exception as e:
                return {"type": "response", "action": action, "success": False, "error": str(e)}
        else:
            return {"type": "response", "action": action, "success": False, "error": f"未知操作: {action}"}

    return handle_ws_message
