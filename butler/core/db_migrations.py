# -*- coding: utf-8 -*-
from package.storage_hub.migration_manager import MigrationManager

class DatabaseMigrationRunner:
    def __init__(self, db_path=None):
        self.manager = MigrationManager(db_path=db_path)

    def run_migrations(self):
        self.manager.migrate()

def run_all_migrations():
    manager = MigrationManager()
    manager.migrate()
