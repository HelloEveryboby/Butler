# -*- coding: utf-8 -*-
import sqlite3
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MigrationManager:
    """
    Manages SQLite database migrations for Storage Hub.
    """
    def __init__(self, db_path=None):
        if db_path is None:
            # Default to the long_memory.db path
            current_dir = Path(__file__).resolve().parent
            self.db_path = current_dir.parent.parent / "butler" / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)
        self.migrations_dir = Path(__file__).resolve().parent / "migrations"

    def get_version(self) -> int:
        """
        Gets the number of applied migrations.
        """
        if not self.db_path.exists():
            return 0
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM applied_migrations")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def apply(self, migration_file: Path):
        """
        Applies a single migration file.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Create applied_migrations tracking table if not exists
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS applied_migrations (
                        filename TEXT PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            filename = migration_file.name
            sql = migration_file.read_text(encoding="utf-8")
            with conn:
                conn.executescript(sql)
                conn.execute("INSERT OR REPLACE INTO applied_migrations (filename) VALUES (?)", (filename,))
            logger.info(f"Successfully applied migration: {filename}")
        except Exception as e:
            logger.error(f"Failed to apply migration {migration_file.name}: {e}")
            raise
        finally:
            conn.close()

    def migrate(self):
        """
        Runs all pending migrations in sorted order.
        """
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory does not exist: {self.migrations_dir}")
            return

        migration_files = sorted(self.migrations_dir.glob("*.sql"))
        for migration_file in migration_files:
            filename = migration_file.name

            # Check if already applied
            if self.db_path.exists():
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='applied_migrations'")
                    if cursor.fetchone():
                        cursor.execute("SELECT 1 FROM applied_migrations WHERE filename = ?", (filename,))
                        if cursor.fetchone():
                            conn.close()
                            continue
                except Exception:
                    pass
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

            self.apply(migration_file)
