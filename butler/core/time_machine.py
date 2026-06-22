import sqlite3
import json
import time
import logging
from typing import Dict, Any, List, Optional
from butler.core.constants import DATA_DIR

logger = logging.getLogger("TimeMachine")

class TimeMachine:
    """
    Butler 时光机日志与回溯引擎。
    记录系统指标、任务日志、UI 事件等状态快照，支持影音级回溯。
    """
    def __init__(self, db_path: str = None):
        self.db_path = DATA_DIR / "system_data" / "time_machine.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 记录全量状态快照
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    timestamp REAL PRIMARY KEY,
                    category TEXT,
                    payload TEXT
                )
            """)
            # 建立时间索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON snapshots(timestamp)")

    def record(self, category: str, payload: Any):
        """记录一个状态快照"""
        ts = time.time()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO snapshots (timestamp, category, payload) VALUES (?, ?, ?)",
                    (ts, category, json.dumps(payload, ensure_ascii=False))
                )
        except Exception as e:
            logger.error(f"TimeMachine record failed: {e}")

    def get_snapshot_at(self, timestamp: float) -> Dict[str, Any]:
        """获取最接近给定时间戳的系统全量快照"""
        with sqlite3.connect(self.db_path) as conn:
            # 查找该时间点之前最后的一个快照
            row = conn.execute(
                "SELECT payload FROM snapshots WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1",
                (timestamp,)
            ).fetchone()
            return json.loads(row[0]) if row else {}

    def get_range(self, start: float, end: float, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取时间范围内的所有快照"""
        query = "SELECT timestamp, category, payload FROM snapshots WHERE timestamp >= ? AND timestamp <= ?"
        params = [start, end]
        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY timestamp ASC"

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [{"timestamp": r[0], "category": r[1], "payload": json.loads(r[2])} for r in rows]

    def cleanup(self, retention_days: int = 7):
        """清理旧数据"""
        cutoff = time.time() - (retention_days * 86400)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM snapshots WHERE timestamp < ?", (cutoff,))

time_machine = TimeMachine()
