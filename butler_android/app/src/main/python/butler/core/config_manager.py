"""统一的配置管理系统

这个模块提供了一个统一的配置管理接口，支持：
- YAML 和 .env 文件的无缝切换
- 配置验证和类型转换
- 运行时配置修改
- 配置备份和恢复
"""

import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv, set_key, dotenv_values
import threading
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)


class ConfigManager:
    """统一的配置管理器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.env_file = self.project_root / ".env"
        self.config_dir = self.project_root / "config"
        self.config_yaml = self.config_dir / "config.yaml"
        self.config_json = self.config_dir / "system_config.json"

        # 确保配置目录存在
        self.config_dir.mkdir(exist_ok=True)

        # 加载环境变量
        load_dotenv(self.env_file)

        # 初始化配置缓存
        self._config_cache = {}
        self._load_config()

        self._initialized = True

    def _load_config(self):
        """加载配置文件"""
        self._config_cache.clear()

        # 优先加载 YAML
        if self.config_yaml.exists():
            try:
                with open(self.config_yaml, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f) or {}
                    self._config_cache.update(yaml_config)
                    logger.info(f"已加载 YAML 配置: {self.config_yaml}")
            except Exception as e:
                logger.error(f"加载 YAML 配置失败: {e}")

        # 加载 .env 文件（覆盖 YAML）
        try:
            env_values = dotenv_values(self.env_file)
            if env_values:
                # 将 .env 值转换为嵌套结构
                for key, value in env_values.items():
                    if key.startswith("DEEPSEEK"):
                        if "api" not in self._config_cache:
                            self._config_cache["api"] = {}
                        self._config_cache["api"]["deepseek_key"] = value
                    elif key.startswith("BAIDU"):
                        if "api" not in self._config_cache:
                            self._config_cache["api"] = {}
                        if key == "BAIDU_APP_ID":
                            self._config_cache["api"]["baidu_app_id"] = value
                        elif key == "BAIDU_API_KEY":
                            self._config_cache["api"]["baidu_api_key"] = value
                        elif key == "BAIDU_SECRET_KEY":
                            self._config_cache["api"]["baidu_secret_key"] = value
                logger.info(f"已加载 .env 配置")
        except Exception as e:
            logger.error(f"加载 .env 配置失败: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值（支持点分路径）

        Args:
            key_path: 配置路径，如 'api.deepseek_key'
            default: 默认值

        Returns:
            配置值或默认值
        """
        parts = key_path.split('.')
        value = self._config_cache

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                # 尝试从环境变量中获取
                env_key = key_path.upper().replace('.', '_')
                env_value = os.getenv(env_key)
                return env_value if env_value is not None else default

        return value if value != self._config_cache else default

    def set(self, key_path: str, value: Any, persist: bool = True) -> bool:
        """设置配置值

        Args:
            key_path: 配置路径
            value: 新值
            persist: 是否持久化到文件

        Returns:
            是否设置成功
        """
        try:
            # 更新缓存
            parts = key_path.split('.')
            config = self._config_cache

            for part in parts[:-1]:
                if part not in config:
                    config[part] = {}
                config = config[part]

            config[parts[-1]] = value

            # 持久化到文件
            if persist:
                if key_path.startswith('api.'):
                    # API 密钥保存到 .env
                    env_key = key_path.split('.')[-1].upper()
                    if key_path.startswith('api.deepseek'):
                        env_key = 'DEEPSEEK_API_KEY'
                    elif key_path.startswith('api.baidu_app'):
                        env_key = 'BAIDU_APP_ID'
                    elif key_path.startswith('api.baidu_api'):
                        env_key = 'BAIDU_API_KEY'
                    elif key_path.startswith('api.baidu_secret'):
                        env_key = 'BAIDU_SECRET_KEY'

                    set_key(self.env_file, env_key, str(value))
                else:
                    # 其他配置保存到 YAML
                    self._save_yaml()

            logger.info(f"已设置配置: {key_path} = {value}")
            return True
        except Exception as e:
            logger.error(f"设置配置失败: {key_path} = {value}, 错误: {e}")
            return False

    def _save_yaml(self):
        """保存配置到 YAML 文件"""
        try:
            with open(self.config_yaml, 'w', encoding='utf-8') as f:
                yaml.dump(self._config_cache, f, default_flow_style=False, allow_unicode=True)
                logger.info(f"已保存配置到 {self.config_yaml}")
        except Exception as e:
            logger.error(f"保存 YAML 配置失败: {e}")

    def reload(self):
        """重新加载所有配置"""
        logger.info("正在重新加载配置...")
        self._load_config()

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config_cache.copy()

    def validate_required_keys(self) -> tuple[bool, list]:
        """验证必需的 API 密钥是否已配置

        Returns:
            (是否有效, 缺失的密钥列表)
        """
        missing = []
        deepseek_key = self.get('api.deepseek_key') or os.getenv('DEEPSEEK_API_KEY', '')

        if not deepseek_key or 'YOUR_' in deepseek_key:
            missing.append('DEEPSEEK_API_KEY')

        return len(missing) == 0, missing


# 全局实例
config_manager = ConfigManager()
