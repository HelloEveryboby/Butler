"""
播放控制器 — Skill 的核心调度中枢。
协调播放器适配器、媒体库、字幕管理、播放历史等模块。
"""

import os
import time
import logging
import threading
from typing import Optional

from .player_adapter import (
    PlayerAdapter, PlayerState, MediaInfo,
    AudioTrack, SubtitleTrack, create_player,
)
from .library import MediaLibrary
from .subtitle_manager import SubtitleManager
from .db import VideoDatabase

logger = logging.getLogger(__name__)


class PlaybackController:
    """播放控制器"""

    def __init__(self, db: VideoDatabase, library: MediaLibrary, config: dict):
        self.db = db
        self.library = library
        self.config = config
        self.subtitle_mgr = SubtitleManager()

        # 播放器实例（延迟初始化）
        self._player: Optional[PlayerAdapter] = None
        self._current_video: Optional[dict] = None
        self._current_playlist: list[dict] = []
        self._playlist_index: int = 0

        # 进度保存
        self._progress_timer: Optional[threading.Timer] = None
        self._progress_interval = config.get("playback", {}).get("resume_save_interval_sec", 5)
        self._last_saved_pos: float = 0

        # WebSocket 广播回调
        self._ws_broadcast = None

    def _ensure_player(self) -> PlayerAdapter:
        """确保播放器已初始化"""
        if self._player is None:
            self._player = create_player(self.config)
            self._bind_player_events()
        return self._player

    def _bind_player_events(self):
        """绑定播放器事件到控制器处理"""
        player = self._player

        player.on_state_change(self._on_state_change)
        player.on_position_update(self._on_position_update)
        player.on_end_reached(self._on_end_reached)
        player.on_error(self._on_error)

    # ══════════════════════════════════════════
    # 核心播放流程
    # ══════════════════════════════════════════

    def play_video(self, video_id: str, resume: bool = True) -> dict:
        """
        播放视频的完整流程：
        1. 从数据库获取视频信息
        2. 检查断点续播位置
        3. 加载并播放
        4. 自动加载字幕
        5. 自动选择音轨
        6. 开始进度上报
        """
        video = self.db.get_video(video_id)
        if not video:
            return {"error": "视频不存在", "video_id": video_id}

        if not os.path.isfile(video["path"]):
            return {"error": "视频文件不存在", "path": video["path"]}

        player = self._ensure_player()

        # 断点续播
        start_time = 0.0
        if resume and self.config.get("playback", {}).get("resume_enabled", True):
            saved = self.db.get_resume_point(video_id)
            if saved:
                start_time = saved
                logger.info(f"断点续播: {video['title']} @ {start_time:.1f}s")

        # 加载播放
        player.load(video["path"], start_time=start_time)
        self._current_video = video

        # 自动字幕
        self._auto_load_subtitles(video)

        # 自动音轨
        self._auto_select_audio_track(video)

        # 启动进度保存
        self._start_progress_sync(video_id)

        # 记录播放历史
        self.db.record_play(video_id)

        result = {
            "status": "playing",
            "video_id": video_id,
            "title": video["title"],
            "path": video["path"],
            "resume_from": start_time,
            "container": video.get("container", ""),
            "video_codec": video.get("video_codec", ""),
            "audio_codec": video.get("audio_codec", ""),
            "resolution": f"{video.get('width', 0)}x{video.get('height', 0)}",
            "duration": video.get("duration", 0),
        }

        self._broadcast("media_loaded", result)
        return result

    def _auto_load_subtitles(self, video: dict) -> None:
        """自动加载字幕"""
        if not self.config.get("playback", {}).get("auto_subtitle_if_missing", True):
            return

        player = self._player
        if player is None:
            return

        # 1. 检查内嵌字幕
        embedded = player.get_subtitle_tracks()
        preferred_lang = self.config.get("playback", {}).get("preferred_subtitle_lang", "chi")
        preferred_names = self.subtitle_mgr._get_lang_names(preferred_lang)

        for track in embedded:
            if track.language in preferred_names or track.default:
                player.set_subtitle_track(track.index)
                logger.info(f"使用内嵌字幕: {track.language} / {track.title}")
                return

        # 2. 检查外挂字幕
        external = self.subtitle_mgr.find_subtitles(video["path"])
        if external:
            # 优先偏好语言
            for sub in external:
                if sub["language"] in preferred_names:
                    player.load_external_subtitle(sub["path"])
                    logger.info(f"加载外挂字幕: {sub['filename']} ({sub['language']})")
                    return
            # 降级：加载第一个
            player.load_external_subtitle(external[0]["path"])
            logger.info(f"加载外挂字幕: {external[0]['filename']}")

    def _auto_select_audio_track(self, video: dict) -> None:
        """自动选择音轨"""
        if not self.config.get("playback", {}).get("prefer_best_audio_track", True):
            return

        player = self._player
        if player is None:
            return

        tracks = player.get_audio_tracks()
        if len(tracks) <= 1:
            return

        preferred_lang = self.config.get("playback", {}).get("preferred_audio_lang", "chi")
        preferred_names = self.subtitle_mgr._get_lang_names(preferred_lang)

        # 优先：多声道 + 偏好语言
        best = None
        best_score = -1
        for track in tracks:
            score = 0
            if track.language in preferred_names:
                score += 100
            score += track.channels  # 声道数越多越好
            if score > best_score:
                best_score = score
                best = track

        if best and best.index != player.get_current_audio_track():
            player.set_audio_track(best.index)
            logger.info(f"自动选择音轨: {best.language} ({best.channels}ch) [{best.title}]")

    # ══════════════════════════════════════════
    # 播放控制快捷方法
    # ══════════════════════════════════════════

    def toggle_pause(self) -> dict:
        player = self._ensure_player()
        player.toggle_pause()
        state = player.get_state()
        return {"state": state.value}

    def pause(self) -> dict:
        player = self._ensure_player()
        player.pause()
        return {"state": "paused"}

    def resume(self) -> dict:
        player = self._ensure_player()
        player.play()
        return {"state": "playing"}

    def stop(self) -> dict:
        if self._player:
            self._save_current_progress()
            self._stop_progress_sync()
            self._player.stop()
        return {"state": "stopped"}

    def seek(self, position: float) -> dict:
        player = self._ensure_player()
        player.seek(position)
        return {"position": position}

    def seek_relative(self, offset: float) -> dict:
        player = self._ensure_player()
        current = player.get_position()
        player.seek(offset, mode="relative")
        return {"position": current + offset}

    def seek_percent(self, percent: float) -> dict:
        player = self._ensure_player()
        player.seek_percent(percent)
        return {"percent": percent}

    def set_speed(self, speed: float) -> dict:
        player = self._ensure_player()
        player.set_speed(speed)
        return {"speed": player.get_speed()}

    def set_volume(self, volume: float) -> dict:
        player = self._ensure_player()
        player.set_volume(volume)
        return {"volume": player.get_volume()}

    def set_mute(self, muted: bool) -> dict:
        player = self._ensure_player()
        player.set_mute(muted)
        return {"muted": player.is_muted()}

    def set_audio_track(self, index: int) -> dict:
        player = self._ensure_player()
        player.set_audio_track(index)
        return {"audio_track": index}

    def set_subtitle_track(self, index: int) -> dict:
        player = self._ensure_player()
        player.set_subtitle_track(index)
        return {"subtitle_track": index}

    def toggle_subtitle(self) -> dict:
        player = self._ensure_player()
        visible = not player.is_subtitle_visible()
        player.set_subtitle_visibility(visible)
        return {"subtitle_visible": visible}

    def load_subtitle(self, path: str) -> dict:
        player = self._ensure_player()
        player.load_external_subtitle(path)
        return {"loaded": path}

    def screenshot(self, output_dir: str = None) -> dict:
        player = self._ensure_player()
        if output_dir is None:
            output_dir = self.config.get("playback", {}).get("screenshot_dir", "")
            output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        title = self._current_video.get("title", "screenshot") if self._current_video else "screenshot"
        pos = player.get_position()
        filename = f"{title}_{int(pos)}s.png"
        output_path = os.path.join(output_dir, filename)

        if player.screenshot(output_path):
            return {"path": output_path, "success": True}
        return {"error": "截图失败", "success": False}

    def set_brightness(self, value: float) -> dict:
        self._ensure_player().set_brightness(value)
        return {"brightness": value}

    def set_contrast(self, value: float) -> dict:
        self._ensure_player().set_contrast(value)
        return {"contrast": value}

    # ══════════════════════════════════════════
    # 播放列表
    # ══════════════════════════════════════════

    def play_playlist(self, playlist_id: str, start_index: int = 0) -> dict:
        """播放整个播放列表"""
        videos = self.db.get_playlist_videos(playlist_id)
        if not videos:
            return {"error": "播放列表为空"}

        self._current_playlist = videos
        self._playlist_index = start_index
        return self.play_video(videos[start_index]["id"])

    def play_next(self) -> dict:
        """播放下一集"""
        if not self._current_playlist:
            return {"error": "无播放列表"}
        if self._playlist_index < len(self._current_playlist) - 1:
            self._playlist_index += 1
            return self.play_video(self._current_playlist[self._playlist_index]["id"])
        return {"error": "已是最后一集"}

    def play_prev(self) -> dict:
        """播放上一集"""
        if not self._current_playlist:
            return {"error": "无播放列表"}
        if self._playlist_index > 0:
            self._playlist_index -= 1
            return self.play_video(self._current_playlist[self._playlist_index]["id"])
        return {"error": "已是第一集"}

    # ══════════════════════════════════════════
    # 播放器事件处理
    # ══════════════════════════════════════════

    def _on_state_change(self, state: PlayerState):
        """播放器状态变化处理"""
        self._broadcast("state_change", {"state": state.value})
        if state == PlayerState.ENDED:
            self._on_playback_ended()

    def _on_position_update(self, position: float, duration: float):
        """播放位置更新"""
        self._broadcast("position_update", {
            "position": round(position, 2),
            "duration": round(duration, 2),
            "progress": round(position / duration * 100, 2) if duration > 0 else 0,
            "speed": self._player.get_speed() if self._player else 1.0,
        })

    def _on_end_reached(self):
        """播放结束"""
        self._save_current_progress()
        self._stop_progress_sync()

    def _on_error(self, error_msg: str):
        """播放错误"""
        logger.error(f"播放错误: {error_msg}")
        self._broadcast("error", {"message": error_msg})

    def _on_playback_ended(self):
        """播放结束后自动下一集"""
        if (self._current_playlist and
            self.config.get("playback", {}).get("auto_play_next", True)):
            self.play_next()

    # ══════════════════════════════════════════
    # 进度保存
    # ══════════════════════════════════════════

    def _start_progress_sync(self, video_id: str):
        """启动定时进度保存"""
        self._stop_progress_sync()
        self._last_saved_pos = 0
        self._progress_video_id = video_id
        self._schedule_progress_save()

    def _schedule_progress_save(self):
        """调度下一次进度保存"""
        if self._progress_timer:
            self._progress_timer.cancel()
        self._progress_timer = threading.Timer(
            self._progress_interval, self._progress_tick
        )
        self._progress_timer.daemon = True
        self._progress_timer.start()

    def _progress_tick(self):
        """进度保存定时回调"""
        self._save_current_progress()
        # 继续调度
        if self._player and self._player.get_state() in (
            PlayerState.PLAYING, PlayerState.PAUSED
        ):
            self._schedule_progress_save()

    def _save_current_progress(self):
        """保存当前播放进度"""
        if not self._player or not self._current_video:
            return
        try:
            position = self._player.get_position()
            duration = self._player.get_duration()
            if position > 0 and duration > 0:
                # 只在进度变化 >2% 时保存（减少写入）
                change = abs(position - self._last_saved_pos)
                if change > duration * 0.02 or change > 10:
                    self.db.save_progress(
                        self._current_video["id"], position, duration
                    )
                    self._last_saved_pos = position
        except Exception as e:
            logger.error(f"保存进度失败: {e}")

    def _stop_progress_sync(self):
        """停止进度保存定时器"""
        if self._progress_timer:
            self._progress_timer.cancel()
            self._progress_timer = None

    # ══════════════════════════════════════════
    # WebSocket 广播
    # ══════════════════════════════════════════

    def set_ws_broadcaster(self, callback):
        """设置 WebSocket 广播回调"""
        self._ws_broadcast = callback

    def _broadcast(self, event_type: str, data: dict):
        """广播事件到 WebSocket 客户端"""
        if self._ws_broadcast:
            try:
                self._ws_broadcast({"type": event_type, **data})
            except Exception as e:
                logger.error(f"WebSocket 广播失败: {e}")

    # ══════════════════════════════════════════
    # 状态查询
    # ══════════════════════════════════════════

    def get_status(self) -> dict:
        """获取当前播放状态"""
        player = self._player
        if not player or player.get_state() == PlayerState.IDLE:
            return {"state": "idle", "video": None}

        video_info = {}
        if self._current_video:
            video_info = {
                "video_id": self._current_video["id"],
                "title": self._current_video["title"],
                "path": self._current_video["path"],
            }

        return {
            "state": player.get_state().value,
            "position": player.get_position(),
            "duration": player.get_duration(),
            "speed": player.get_speed(),
            "volume": player.get_volume(),
            "muted": player.is_muted(),
            "subtitle_visible": player.is_subtitle_visible(),
            "audio_tracks": [
                {"index": t.index, "language": t.language, "title": t.title,
                 "channels": t.channels}
                for t in player.get_audio_tracks()
            ],
            "subtitle_tracks": [
                {"index": t.index, "language": t.language, "title": t.title,
                 "codec": t.codec, "is_external": t.is_external}
                for t in player.get_subtitle_tracks()
            ],
            "video": video_info,
            "playlist": {
                "current_index": self._playlist_index,
                "total": len(self._current_playlist),
            },
        }

    def get_resume_point(self, video_id: str) -> dict:
        """获取指定视频的续播点"""
        pos = self.db.get_resume_point(video_id)
        return {
            "video_id": video_id,
            "resume_position": pos,
            "has_resume": pos is not None,
        }

    # ══════════════════════════════════════════
    # 资源清理
    # ══════════════════════════════════════════

    def destroy(self):
        """清理所有资源"""
        self._save_current_progress()
        self._stop_progress_sync()
        if self._player:
            self._player.destroy()
            self._player = None
