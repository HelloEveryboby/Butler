"""
SQLite 数据库层 — 视频库、播放历史、播放列表的持久化存储。
复用 Butler 的 Local-First 理念，纯本地 SQLite，零外部依赖。
"""

import os
import time
import uuid
import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VideoDatabase:
    """视频数据库管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表结构"""
        self._conn.executescript("""
            -- 视频库
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL,
                container TEXT,
                format_long TEXT,
                video_codec TEXT,
                video_codec_long TEXT,
                audio_codec TEXT,
                audio_codec_long TEXT,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                fps REAL DEFAULT 0,
                duration REAL DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                bitrate INTEGER DEFAULT 0,
                video_bitrate INTEGER DEFAULT 0,
                audio_bitrate INTEGER DEFAULT 0,
                audio_channels INTEGER DEFAULT 0,
                audio_sample_rate INTEGER DEFAULT 0,
                audio_language TEXT DEFAULT '',
                video_language TEXT DEFAULT '',
                has_subtitle INTEGER DEFAULT 0,
                subtitle_languages TEXT DEFAULT '[]',
                pixel_format TEXT DEFAULT '',
                color_space TEXT DEFAULT '',
                color_range TEXT DEFAULT '',
                rotation INTEGER DEFAULT 0,
                thumbnail_path TEXT DEFAULT '',
                poster_url TEXT DEFAULT '',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                is_favorite INTEGER DEFAULT 0,
                created_at REAL,
                modified_at REAL,
                scanned_at REAL DEFAULT (strftime('%s','now'))
            );

            -- 播放历史
            CREATE TABLE IF NOT EXISTS play_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,
                position REAL NOT NULL DEFAULT 0,
                duration REAL NOT NULL DEFAULT 0,
                progress REAL DEFAULT 0,
                played_at REAL DEFAULT (strftime('%s','now'))
            );

            -- 播放列表
            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at REAL DEFAULT (strftime('%s','now')),
                updated_at REAL DEFAULT (strftime('%s','now'))
            );

            -- 播放列表项
            CREATE TABLE IF NOT EXISTS playlist_items (
                playlist_id TEXT REFERENCES playlists(id) ON DELETE CASCADE,
                video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,
                sort_order INTEGER DEFAULT 0,
                added_at REAL DEFAULT (strftime('%s','now')),
                PRIMARY KEY (playlist_id, video_id)
            );

            -- 索引
            CREATE INDEX IF NOT EXISTS idx_videos_path ON videos(path);
            CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title);
            CREATE INDEX IF NOT EXISTS idx_videos_container ON videos(container);
            CREATE INDEX IF NOT EXISTS idx_history_video ON play_history(video_id);
            CREATE INDEX IF NOT EXISTS idx_history_time ON play_history(played_at DESC);
            CREATE INDEX IF NOT EXISTS idx_plist_items ON playlist_items(playlist_id, sort_order);
        """)
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()

    # ══════════════════════════════════════════
    # 视频 CRUD
    # ══════════════════════════════════════════

    def insert_video(self, data: dict) -> str:
        """插入视频记录，返回 video_id"""
        video_id = str(uuid.uuid4())
        data["id"] = video_id
        data.setdefault("scanned_at", time.time())

        # 确保 list 类型字段序列化为 JSON
        for key in ("subtitle_languages", "tags"):
            if isinstance(data.get(key), list):
                import json
                data[key] = json.dumps(data[key], ensure_ascii=False)

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        self._conn.execute(
            f"INSERT OR REPLACE INTO videos ({columns}) VALUES ({placeholders})",
            list(data.values())
        )
        self._conn.commit()
        return video_id

    def get_video(self, video_id: str) -> Optional[dict]:
        """获取视频详情"""
        row = self._conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_video_by_path(self, path: str) -> Optional[dict]:
        """通过路径查找视频"""
        row = self._conn.execute(
            "SELECT * FROM videos WHERE path = ?", (path,)
        ).fetchone()
        return dict(row) if row else None

    def exists(self, path: str) -> bool:
        """检查路径是否已入库"""
        row = self._conn.execute(
            "SELECT 1 FROM videos WHERE path = ?", (path,)
        ).fetchone()
        return row is not None

    def update_video(self, video_id: str, updates: dict) -> None:
        """更新视频字段"""
        sets = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [video_id]
        self._conn.execute(
            f"UPDATE videos SET {sets} WHERE id = ?", values
        )
        self._conn.commit()

    def delete_video(self, video_id: str) -> None:
        """删除视频记录"""
        self._conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        self._conn.commit()

    def get_all_videos(self, order_by: str = "title ASC",
                       limit: int = 100, offset: int = 0,
                       search: str = "", favorite_only: bool = False) -> list[dict]:
        """获取视频列表（支持搜索、排序、分页）"""
        where_clauses = []
        params = []

        if search:
            where_clauses.append("title LIKE ?")
            params.append(f"%{search}%")

        if favorite_only:
            where_clauses.append("is_favorite = 1")

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        rows = self._conn.execute(
            f"SELECT * FROM videos {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
        return [dict(r) for r in rows]

    def count_videos(self, search: str = "", favorite_only: bool = False) -> int:
        """统计视频数量"""
        where_clauses = []
        params = []
        if search:
            where_clauses.append("title LIKE ?")
            params.append(f"%{search}%")
        if favorite_only:
            where_clauses.append("is_favorite = 1")
        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM videos {where}", params
        ).fetchone()
        return row["cnt"] if row else 0

    def search_videos(self, query: str) -> list[dict]:
        """搜索视频（标题模糊匹配）"""
        return self.get_all_videos(
            search=query,
            order_by="title ASC",
            limit=50,
        )

    def get_recent_videos(self, limit: int = 20) -> list[dict]:
        """获取最近添加的视频"""
        return self.get_all_videos(order_by="scanned_at DESC", limit=limit)

    def get_favorite_videos(self) -> list[dict]:
        """获取收藏的视频"""
        return self.get_all_videos(favorite_only=True, order_by="title ASC")

    def toggle_favorite(self, video_id: str) -> bool:
        """切换收藏状态，返回新的收藏状态"""
        row = self._conn.execute(
            "SELECT is_favorite FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        if not row:
            return False
        new_val = 0 if row["is_favorite"] else 1
        self._conn.execute(
            "UPDATE videos SET is_favorite = ? WHERE id = ?",
            (new_val, video_id)
        )
        self._conn.commit()
        return bool(new_val)

    # ══════════════════════════════════════════
    # 播放历史 + 断点续播
    # ══════════════════════════════════════════

    def save_progress(self, video_id: str, position: float, duration: float) -> None:
        """保存播放进度（断点续播）"""
        progress = (position / duration * 100) if duration > 0 else 0
        self._conn.execute(
            "INSERT INTO play_history (video_id, position, duration, progress, played_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (video_id, position, duration, progress, time.time())
        )
        self._conn.commit()

    def get_resume_point(self, video_id: str) -> Optional[float]:
        """获取断点续播位置（秒）"""
        row = self._conn.execute(
            "SELECT position FROM play_history "
            "WHERE video_id = ? ORDER BY played_at DESC LIMIT 1",
            (video_id,)
        ).fetchone()
        if row and row["position"] > 5:  # 超过 5 秒才算有效续播点
            return row["position"]
        return None

    def get_play_history(self, limit: int = 50) -> list[dict]:
        """获取播放历史（最近播放优先）"""
        rows = self._conn.execute(
            "SELECT h.*, v.title, v.path, v.duration as video_duration, "
            "v.container, v.video_codec, v.width, v.height "
            "FROM play_history h "
            "JOIN videos v ON h.video_id = v.id "
            "ORDER BY h.played_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def record_play(self, video_id: str) -> None:
        """记录一次播放（用于历史统计）"""
        self._conn.execute(
            "INSERT INTO play_history (video_id, position, duration, played_at) "
            "VALUES (?, 0, 0, ?)",
            (video_id, time.time())
        )
        self._conn.commit()

    # ══════════════════════════════════════════
    # 播放列表
    # ══════════════════════════════════════════

    def create_playlist(self, name: str, description: str = "") -> str:
        """创建播放列表"""
        playlist_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO playlists (id, name, description) VALUES (?, ?, ?)",
            (playlist_id, name, description)
        )
        self._conn.commit()
        return playlist_id

    def get_playlists(self) -> list[dict]:
        """获取所有播放列表"""
        rows = self._conn.execute(
            "SELECT p.*, COUNT(pi.video_id) as video_count "
            "FROM playlists p LEFT JOIN playlist_items pi ON p.id = pi.playlist_id "
            "GROUP BY p.id ORDER BY p.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        """添加视频到播放列表"""
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 as next_order "
            "FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,)
        ).fetchone()
        order = row["next_order"] if row else 1
        self._conn.execute(
            "INSERT OR IGNORE INTO playlist_items (playlist_id, video_id, sort_order) "
            "VALUES (?, ?, ?)",
            (playlist_id, video_id, order)
        )
        self._conn.execute(
            "UPDATE playlists SET updated_at = ? WHERE id = ?",
            (time.time(), playlist_id)
        )
        self._conn.commit()

    def remove_from_playlist(self, playlist_id: str, video_id: str) -> None:
        """从播放列表移除视频"""
        self._conn.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ? AND video_id = ?",
            (playlist_id, video_id)
        )
        self._conn.commit()

    def get_playlist_videos(self, playlist_id: str) -> list[dict]:
        """获取播放列表中的所有视频"""
        rows = self._conn.execute(
            "SELECT v.* FROM playlist_items pi "
            "JOIN videos v ON pi.video_id = v.id "
            "WHERE pi.playlist_id = ? ORDER BY pi.sort_order",
            (playlist_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_playlist(self, playlist_id: str) -> None:
        """删除播放列表"""
        self._conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        self._conn.commit()

    # ══════════════════════════════════════════
    # 统计
    # ══════════════════════════════════════════

    def get_stats(self) -> dict:
        """获取媒体库统计信息"""
        video_count = self.count_videos()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(file_size), 0) as total_size, "
            "COALESCE(SUM(duration), 0) as total_duration "
            "FROM videos"
        ).fetchone()
        return {
            "video_count": video_count,
            "total_size_bytes": row["total_size"],
            "total_size_gb": round(row["total_size"] / (1024 ** 3), 2),
            "total_duration_hours": round(row["total_duration"] / 3600, 1),
            "favorite_count": self.count_videos(favorite_only=True),
            "playlist_count": len(self.get_playlists()),
        }
