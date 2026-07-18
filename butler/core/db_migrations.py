# -*- coding: utf-8 -*-
import os
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseMigrationRunner:
    """
    管理 Butler v2.0 的自动化 SQLite 数据库迁移。
    """
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 定位默认的 long_memory.db 路径
            current_dir = Path(__file__).resolve().parent
            self.db_path = current_dir.parent / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)

        self.migrations_dir = Path(__file__).resolve().parent.parent.parent / "package" / "storage_hub" / "migrations"

    def run_migrations(self):
        """
        执行 package/storage_hub/migrations/ 目录下所有待处理的迁移。
        """
        try:
            # 确保数据库目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"正在连接数据库: {self.db_path}")
            conn = sqlite3.connect(str(self.db_path))

            # 创建迁移记录表，用于跟踪已应用的文件
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS applied_migrations (
                        filename TEXT PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            if not self.migrations_dir.exists():
                logger.warning(f"未找到迁移目录: {self.migrations_dir}")
                conn.close()
                return

            # 读取所有 SQL 迁移文件，按名字升序排序
            migration_files = sorted(self.migrations_dir.glob("*.sql"))

            for migration_file in migration_files:
                filename = migration_file.name

                # 检查该迁移是否已经执行过
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM applied_migrations WHERE filename = ?", (filename,))
                if cursor.fetchone():
                    logger.debug(f"迁移已应用，跳过: {filename}")
                    continue

                logger.info(f"正在应用数据库迁移: {filename}")
                sql = migration_file.read_text(encoding="utf-8")

                try:
                    # 在事务中执行 SQL 脚本
                    with conn:
                        conn.executescript(sql)
                        conn.execute("INSERT INTO applied_migrations (filename) VALUES (?)", (filename,))
                    logger.info(f"成功应用迁移: {filename}")
                except Exception as ex:
                    logger.error(f"应用迁移 {filename} 时发生错误: {ex}")
                    raise

            conn.close()
            logger.info("数据库迁移检查并执行完成。")
        except Exception as e:
            logger.error(f"数据库迁移运行器异常: {e}")
            raise

def run_all_migrations():
    runner = DatabaseMigrationRunner()
    runner.run_migrations()
