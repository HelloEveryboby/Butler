import os
import tarfile
import datetime
import logging
import shutil
import glob
from typing import List

logger = logging.getLogger("AssetSyncHub.Rollback")

class RollbackManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.android_dir = os.path.join(root_dir, "butler_android")
        self.backup_dir = os.path.join(self.android_dir, ".sync_backups")
        self.max_backups = 3

    def create_backup(self) -> str:
        """Backs up assets and config to a tar.gz file."""
        if not os.path.exists(self.android_dir):
            return "Android project not found. Skipping backup."

        os.makedirs(self.backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.tar.gz"
        backup_path = os.path.join(self.backup_dir, backup_name)

        # Files to backup: assets/ and config files in python/config/
        assets_dir = "app/src/main/assets"
        python_config = "app/src/main/python/config"

        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                full_assets = os.path.join(self.android_dir, assets_dir)
                if os.path.exists(full_assets):
                    tar.add(full_assets, arcname=assets_dir)

                full_config = os.path.join(self.android_dir, python_config)
                if os.path.exists(full_config):
                    tar.add(full_config, arcname=python_config)

            self._cleanup_old_backups()
            logger.info(f"Created backup: {backup_name}")
            return f"Backup created: {backup_name}"
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return f"Backup failed: {e}"

    def rollback(self, step: int = 1) -> str:
        """Rolls back to the N-th previous backup."""
        backups = self.list_backups()
        if not backups:
            return "No backups found."

        if step > len(backups):
            return f"Cannot rollback {step} steps. Only {len(backups)} backups available."

        target_backup = backups[step-1] # backups are sorted newest first
        target_path = os.path.join(self.backup_dir, target_backup)

        try:
            # Clear current assets before restoring
            assets_path = os.path.join(self.android_dir, "app/src/main/assets")
            if os.path.exists(assets_path):
                shutil.rmtree(assets_path)

            with tarfile.open(target_path, "r:gz") as tar:
                tar.extractall(path=self.android_dir)

            logger.info(f"Rolled back to {target_backup}")
            return f"Successfully rolled back to {target_backup}"
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return f"Rollback failed: {e}"

    def list_backups(self) -> List[str]:
        """Returns a list of backup filenames, newest first."""
        if not os.path.exists(self.backup_dir):
            return []
        backups = glob.glob(os.path.join(self.backup_dir, "backup_*.tar.gz"))
        return sorted([os.path.basename(b) for b in backups], reverse=True)

    def _cleanup_old_backups(self):
        backups = self.list_backups()
        if len(backups) > self.max_backups:
            for old_backup in backups[self.max_backups:]:
                os.remove(os.path.join(self.backup_dir, old_backup))
                logger.info(f"Removed old backup: {old_backup}")
