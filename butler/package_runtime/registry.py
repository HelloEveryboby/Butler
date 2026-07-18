# -*- coding: utf-8 -*-
import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path
from butler.package_runtime.manifest import PackageManifest

class PackageRegistry:
    """
    管理 SQLite 数据库 packages 数据表中的包注册信息，记录活跃的安装状态。
    """
    def __init__(self, db_path: str = None):
        if db_path is None:
            current_dir = Path(__file__).resolve().parent
            self.db_path = current_dir.parent / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)

    def register(self, name: str, version: str, status: str = "active") -> bool:
        """
        在 SQLite packages 表中保存或更新包注册信息。
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO packages (name, version, status) VALUES (?, ?, ?)",
                    (name, version, status)
                )
            conn.close()
            return True
        except Exception:
            return False

    def unregister(self, name: str) -> bool:
        """
        从 SQLite 数据库表中注销并删除一个包。
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute("DELETE FROM packages WHERE name = ?", (name,))
            conn.close()
            return True
        except Exception:
            return False

    def get_package_status(self, name: str) -> Optional[str]:
        """
        获取某个已注册包的当前状态。
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM packages WHERE name = ?", (name,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None

    def list_packages(self) -> List[Dict[str, str]]:
        """
        返回 SQLite 注册表中的所有已安装包列表。
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name, version, status FROM packages")
            rows = cursor.fetchall()
            conn.close()
            return [{"name": r[0], "version": r[1], "status": r[2]} for r in rows]
        except Exception:
            return []
