import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import patch
from butler.core.config_backup_manager import ConfigBackupManager

class TestConfigBackup:

    @pytest.fixture
    def manager(self, tmp_path):
        # 创建模拟项目结构
        project_root = tmp_path / "project"
        project_root.mkdir()
        config_dir = project_root / "config"
        config_dir.mkdir()

        # 创建模拟文件
        (project_root / ".env").write_text("TEST=1")
        (config_dir / "config.yaml").write_text("key: value")

        backup_dir = "data/test_backups"

        # 补丁 ConfigBackupManager 的路径
        with patch('butler.core.config_backup_manager.Path') as mock_path:
            # 这是一个简化的测试策略
            pass

        # 实际测试我们直接实例化并手动设置路径
        mgr = ConfigBackupManager(backup_dir=str(tmp_path / "backups"))
        mgr.project_root = project_root
        mgr.config_dir = config_dir
        mgr.env_file = project_root / ".env"
        mgr.config_yaml = config_dir / "config.yaml"
        mgr.config_json = config_dir / "system_config.json"

        return mgr

    def test_create_and_list_backup(self, manager):
        name = manager.create_backup("Test")
        assert name is not None

        backups = manager.list_backups()
        assert len(backups) == 1
        assert backups[0]['description'] == "Test"

    def test_restore_backup(self, manager):
        # 1. 备份
        manager.create_backup("Initial")

        # 2. 修改文件
        manager.env_file.write_text("TEST=2")

        # 3. 恢复
        backups = manager.list_backups()
        manager.restore_backup(backups[0]['name'])

        # 4. 验证
        assert manager.env_file.read_text() == "TEST=1"

    def test_export_import(self, manager, tmp_path):
        zip_path = str(tmp_path / "config.zip")

        # 导出
        assert manager.export_config(zip_path) is True
        assert os.path.exists(zip_path)

        # 修改并导入
        manager.env_file.write_text("CHANGED")
        assert manager.import_config(zip_path) is True
        assert manager.env_file.read_text() == "TEST=1"

    def test_safe_reset(self, manager):
        # 创建 .env.example
        example = manager.project_root / ".env.example"
        example.write_text("TEMPLATE=1")

        assert manager.safe_reset() is True
        assert manager.env_file.read_text() == "TEMPLATE=1"
        assert not manager.config_yaml.exists()
