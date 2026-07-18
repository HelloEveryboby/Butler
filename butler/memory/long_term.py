# -*- coding: utf-8 -*-
import sqlite3
import json
import uuid
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

class LongTermMemory:
    """
    管理 SQLite 数据库 memory 数据表中存储的长期历史事实、用户偏好习惯和任务归档。
    """
    def __init__(self, db_path: str = None):
        if db_path is None:
            current_dir = Path(__file__).resolve().parent
            self.db_path = current_dir.parent / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)

    def store(self, type_str: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        在 SQLite 长期事实表中持久化存储一条记录。
        """
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    "INSERT INTO memory (id, type, content, metadata) VALUES (?, ?, ?, ?)",
                    (mem_id, type_str, content, meta_json)
                )
            conn.close()
            return mem_id
        except Exception as e:
            print(f"存储长期记忆时发生错误: {e}")
            return ""

    def search(self, query: str, type_str: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        检索包含指定关键词的内容的长期记忆条目。
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            sql = "SELECT id, type, content, metadata, created_at FROM memory WHERE content LIKE ?"
            params = [f"%{query}%"]

            if type_str:
                sql += " AND type = ?"
                params.append(type_str)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "id": r[0],
                    "type": r[1],
                    "content": r[2],
                    "metadata": json.loads(r[3] or "{}"),
                    "created_at": r[4]
                }
                for r in rows
            ]
        except Exception as e:
            print(f"搜索长期记忆时发生错误: {e}")
            return []

    def get_all_by_type(self, type_str: str) -> List[Dict[str, Any]]:
        """
        根据指定类型（如 'preference' 用户画像偏好）获取其所有记录。
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT id, type, content, metadata, created_at FROM memory WHERE type = ? ORDER BY created_at DESC", (type_str,))
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": r[0],
                    "type": r[1],
                    "content": r[2],
                    "metadata": json.loads(r[3] or "{}"),
                    "created_at": r[4]
                }
                for r in rows
            ]
        except Exception:
            return []
