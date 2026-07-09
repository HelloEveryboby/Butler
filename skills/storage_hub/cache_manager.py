import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

class MetaCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_cache (
                    drive_id TEXT,
                    parent_path TEXT,
                    file_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (drive_id, parent_path)
                )
            """)

    def get_files(self, drive_id: str, parent_path: str) -> Optional[List[Dict[str, Any]]]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT file_data FROM file_cache WHERE drive_id = ? AND parent_path = ?",
                (drive_id, parent_path)
            ).fetchone()
            if row:
                return json.loads(row[0])
        return None

    def set_files(self, drive_id: str, parent_path: str, files: List[Dict[str, Any]]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO file_cache (drive_id, parent_path, file_data, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (drive_id, parent_path, json.dumps(files))
            )
