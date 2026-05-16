import sqlite3
import os
import time

class InputMemory:
    def __init__(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.db_path = os.path.join(project_root, "data/system_data/input_memory.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS word_freq (
                    word TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 1,
                    last_used REAL
                )
            """)

    def record_word(self, word: str):
        if not word or len(word) < 1: return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO word_freq (word, count, last_used)
                VALUES (?, 1, ?)
                ON CONFLICT(word) DO UPDATE SET
                    count = count + 1,
                    last_used = excluded.last_used
            """, (word, time.time()))

    def suggest(self, prefix: str, limit: int = 5):
        if not prefix: return []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT word FROM word_freq
                WHERE word LIKE ?
                ORDER BY count DESC, last_used DESC
                LIMIT ?
            """, (prefix + "%", limit))
            return [row[0] for row in cursor.fetchall()]

input_memory = InputMemory()
