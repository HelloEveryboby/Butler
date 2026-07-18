# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path

class SQLiteMemory:
    """
    SQLite memory persistent operations directly on existing storage_hub SQLite long_memory.db.
    """
    def __init__(self, db_path=None):
        if db_path is None:
            current_dir = Path(__file__).resolve().parent
            self.db_path = current_dir.parent / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)

    def save(self, key: str, value: str):
        conn = sqlite3.connect(str(self.db_path))
        try:
            with conn:
                conn.execute(
                    "INSERT INTO memory (key, value) VALUES (?, ?)",
                    (key, value)
                )
        finally:
            conn.close()

    def get(self, key: str):
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM memory WHERE key = ? ORDER BY id DESC LIMIT 1", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def search(self, query: str):
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM memory WHERE key LIKE ? OR value LIKE ?", (f"%{query}%", f"%{query}%"))
            rows = cursor.fetchall()
            return [{"key": r[0], "value": r[1]} for r in rows]
        finally:
            conn.close()
