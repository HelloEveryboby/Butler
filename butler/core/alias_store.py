# -*- coding: utf-8 -*-
"""别名存储 —— 中文显示名 / 英文真实名的映射层。

原则: **真实文件名永不修改**。本库只记录"显示名"，
Butler 界面显示中文（显示名），命令行/系统/git 看到的仍是英文真名。

    alias_store.set_alias("data/docs", "文档")
    alias_store.resolve_display("data/docs", "docs")   -> "文档"
    alias_store.resolve_display("data/other", "other") -> "other"  (无别名回退原名)

存储: SQLite 单表 data/alias.db（线程安全，进程内单例见模块底部）。
配套: butler/core/naming_policy.py（中文显示名 → 英文/拼音真名）。
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AliasStore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "alias.db"

# 常见英文词 → 中文显示名建议（批量起名用；未收录的词不猜）
WORD_DICT: Dict[str, str] = {
    "data": "数据", "docs": "文档", "doc": "文档", "document": "文档", "documents": "文档",
    "report": "报告", "note": "笔记", "notes": "笔记", "memo": "备忘", "memo s": "备忘",
    "backup": "备份", "bak": "备份", "temp": "临时", "tmp": "临时",
    "image": "图片", "images": "图片", "img": "图片", "pic": "图片", "picture": "图片",
    "photo": "照片", "photos": "照片", "video": "视频", "movie": "视频",
    "audio": "音频", "music": "音乐", "sound": "声音",
    "config": "配置", "cfg": "配置", "setting": "设置", "settings": "设置",
    "log": "日志", "logs": "日志", "src": "源码", "source": "源码", "code": "代码",
    "test": "测试", "tests": "测试", "project": "项目", "demo": "示例",
    "file": "文件", "files": "文件", "folder": "文件夹", "dir": "目录", "directory": "目录",
    "download": "下载", "downloads": "下载", "upload": "上传", "export": "导出",
    "import": "导入", "archive": "归档", "draft": "草稿", "final": "最终版",
    "weekly": "每周", "daily": "每日", "monthly": "每月", "work": "工作",
    "meeting": "会议", "plan": "计划", "summary": "总结", "readme": "说明",
}

_WORD_SPLIT_RE = re.compile(r"[_\-\s.]+|(?<=[a-z0-9])(?=[A-Z])")


class AliasStore:
    """显示名映射库（单例见模块底部 ``alias_store``）。"""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = Path(db_path or DEFAULT_DB)
        self._lock = threading.RLock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_alias (
                    real_path   TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    pinyin      TEXT DEFAULT '',
                    tags        TEXT DEFAULT '',
                    created_by  TEXT DEFAULT 'user',
                    updated_at  REAL
                )
                """
            )
            self._conn.commit()

    # ---------- 增删改查 ----------

    def set_alias(self, real_path: str, display_name: str,
                  tags: str = "", created_by: str = "user") -> Dict[str, Any]:
        real_path = str(real_path)
        display_name = str(display_name).strip()
        if not display_name:
            raise ValueError("显示名不能为空")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO file_alias (real_path, display_name, pinyin, tags, created_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(real_path) DO UPDATE SET
                    display_name=excluded.display_name,
                    pinyin=excluded.pinyin,
                    tags=excluded.tags,
                    updated_at=excluded.updated_at
                """,
                (real_path, display_name, self._pinyin(display_name), tags, created_by, time.time()),
            )
            self._conn.commit()
        return {"status": "ok", "real_path": real_path, "display_name": display_name}

    def get(self, real_path: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM file_alias WHERE real_path = ?", (str(real_path),)
            ).fetchone()
        return dict(row) if row else None

    def resolve_display(self, real_path: str, fallback_name: str = "") -> str:
        """路径 → 显示名（无别名回退原文件名）。"""
        record = self.get(real_path)
        if record:
            return record["display_name"]
        return fallback_name or Path(str(real_path)).name

    def find_by_display(self, display_name: str, parent_dir: str = "") -> List[Dict[str, Any]]:
        """按显示名反查真实路径（同名时用 parent_dir 消歧）。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM file_alias WHERE display_name = ?", (str(display_name),)
            ).fetchall()
        results = [dict(r) for r in rows]
        if parent_dir:
            parent = str(Path(parent_dir).resolve())
            results = [r for r in results if str(Path(r["real_path"]).parent) == parent]
        return results

    def remove(self, real_path: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM file_alias WHERE real_path = ?", (str(real_path),)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM file_alias ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 批量起名（建议 → 用户确认 → 应用） ----------

    def suggest_display_name(self, real_name: str) -> str:
        """英文真实名 → 中文显示名建议（只翻译认识的词，不认识返回空）。"""
        stem = Path(str(real_name)).stem
        words = [w for w in _WORD_SPLIT_RE.split(stem) if w]
        translated = [WORD_DICT.get(w.lower()) for w in words]
        known = [t for t in translated if t]
        if not known or len(known) < max(1, len(words) // 2):
            return ""
        return "".join(known)

    def batch_suggest(self, parent_dir: str) -> List[Dict[str, Any]]:
        """扫描目录，给出中文显示名建议（不含已设别名的；由用户确认后应用）。"""
        parent = Path(parent_dir).expanduser()
        if not parent.is_dir():
            return []
        suggestions = []
        for entry in sorted(parent.iterdir()):
            if entry.name.startswith("."):
                continue
            if self.get(str(entry)):
                continue
            suggested = self.suggest_display_name(entry.name)
            if suggested:
                suggestions.append({
                    "real_path": str(entry),
                    "real_name": entry.name,
                    "suggested": suggested,
                })
        return suggestions

    def apply_batch(self, mapping: Dict[str, str], created_by: str = "batch") -> int:
        """应用 {real_path: display_name} 映射（用户确认后调用）。"""
        count = 0
        for real_path, display_name in (mapping or {}).items():
            try:
                self.set_alias(real_path, display_name, created_by=created_by)
                count += 1
            except Exception as exc:
                logger.warning(f"批量别名写入失败 {real_path}: {exc}")
        return count

    # ---------- 工具 ----------

    @staticmethod
    def _pinyin(text: str) -> str:
        try:
            from pypinyin import lazy_pinyin
            return "_".join(lazy_pinyin(str(text)))
        except Exception:
            return ""


# 全局单例
alias_store = AliasStore()
