"""配置备份与恢复管理器

支持：
- 自动备份与手动备份
- 列表、恢复、删除备份
- 配置导出与导入（ZIP 格式）
- 安全重置
"""

import os
import shutil
import zipfile
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class ConfigBackupManager:
    """配置备份与恢复管理器"""

    def __init__(self, backup_dir: str = "data/backups"):
        # 尝试定位项目根目录
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.backup_dir = self.project_root / backup_dir
        self.config_dir = self.project_root / "config"
        self.env_file = self.project_root / ".env"
        self.config_yaml = self.config_dir / "config.yaml"
        self.config_json = self.config_dir / "system_config.json"
        self.metadata_file = self.backup_dir / "metadata.json"

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_metadata()

    def _ensure_metadata(self):
        """确保元数据文件存在"""
        if not self.metadata_file.exists():
            self._save_metadata({})

    def _get_metadata(self) -> Dict[str, Any]:
        """获取备份元数据"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"读取备份元数据失败: {e}")
        return {}

    def _save_metadata(self, metadata: Dict[str, Any]):
        """保存备份元数据"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存备份元数据失败: {e}")

    def create_backup(self, description: str = "Manual Backup") -> Optional[str]:
        """创建配置备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)

        try:
            backed_up_files = []

            # 备份 .env
            if self.env_file.exists():
                shutil.copy2(self.env_file, backup_path / ".env")
                backed_up_files.append(".env")

            # 备份 config.yaml
            if self.config_yaml.exists():
                shutil.copy2(self.config_yaml, backup_path / "config.yaml")
                backed_up_files.append("config.yaml")

            # 备份 system_config.json
            if self.config_json.exists():
                shutil.copy2(self.config_json, backup_path / "system_config.json")
                backed_up_files.append("system_config.json")

            # 更新元数据
            metadata = self._get_metadata()
            metadata[backup_name] = {
                "timestamp": timestamp,
                "description": description,
                "files": backed_up_files
            }
            self._save_metadata(metadata)

            logger.info(f"配置备份已创建: {backup_name} ({description})")
            return backup_name
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            if backup_path.exists():
                shutil.rmtree(backup_path)
            return None

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        metadata = self._get_metadata()
        backups = []
        for name, info in metadata.items():
            backup_item = info.copy()
            backup_item["name"] = name
            backups.append(backup_item)
        # 按时间戳降序排列
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)

    def restore_backup(self, backup_name: str) -> bool:
        """恢复指定备份"""
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            logger.error(f"备份不存在: {backup_name}")
            return False

        try:
            # 恢复文件
            for filename in [".env", "config.yaml", "system_config.json"]:
                src = backup_path / filename
                if src.exists():
                    if filename == ".env":
                        dest = self.env_file
                    else:
                        dest = self.config_dir / filename

                    shutil.copy2(src, dest)
                    logger.info(f"已恢复文件: {filename}")

            logger.info(f"配置已从备份成功恢复: {backup_name}")
            return True
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False

    def delete_backup(self, backup_name: str) -> bool:
        """删除指定备份"""
        backup_path = self.backup_dir / backup_name
        try:
            if backup_path.exists():
                shutil.rmtree(backup_path)

            metadata = self._get_metadata()
            if backup_name in metadata:
                del metadata[backup_name]
                self._save_metadata(metadata)

            logger.info(f"备份已删除: {backup_name}")
            return True
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return False

    def export_config(self, export_path: str) -> bool:
        """导出配置为 ZIP"""
        try:
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if self.env_file.exists():
                    zipf.write(self.env_file, arcname=".env")
                if self.config_yaml.exists():
                    zipf.write(self.config_yaml, arcname="config.yaml")
                if self.config_json.exists():
                    zipf.write(self.config_json, arcname="system_config.json")
            logger.info(f"配置已成功导出至: {export_path}")
            return True
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False

    def import_config(self, zip_path: str) -> bool:
        """从 ZIP 导入配置"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # 验证 ZIP 内容
                names = zipf.namelist()
                valid_configs = [".env", "config.yaml", "system_config.json"]
                if not any(cfg in names for cfg in valid_configs):
                    logger.error("ZIP 文件不包含有效的配置文件")
                    return False

                # 导入前自动备份
                self.create_backup("Auto-backup before import")

                # 解压
                for name in names:
                    if name in valid_configs:
                        if name == ".env":
                            dest = self.env_file
                        else:
                            dest = self.config_dir / name

                        with zipf.open(name) as src, open(dest, "wb") as f:
                            shutil.copyfileobj(src, f)

            logger.info(f"配置已从 {zip_path} 成功导入")
            return True
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False

    def safe_reset(self) -> bool:
        """安全重置配置（恢复到 .env.example 状态）"""
        try:
            # 重置前自动备份
            self.create_backup("Auto-backup before reset")

            # 重置 .env
            env_example = self.project_root / ".env.example"
            if env_example.exists():
                shutil.copy2(env_example, self.env_file)
                logger.info("已重置 .env 为 .env.example")
            else:
                if self.env_file.exists():
                    self.env_file.unlink()
                logger.warning(".env.example 不存在，已删除当前 .env")

            # 移除其他配置文件
            if self.config_yaml.exists():
                self.config_yaml.unlink()
                logger.info("已移除 config.yaml")

            if self.config_json.exists():
                self.config_json.unlink()
                logger.info("已移除 system_config.json")

            return True
        except Exception as e:
            logger.error(f"重置配置失败: {e}")
            return False

if __name__ == "__main__":
    # 简单测试
    manager = ConfigBackupManager()
    backup = manager.create_backup("Test Backup")
    print(f"Created: {backup}")
    print(f"List: {manager.list_backups()}")
