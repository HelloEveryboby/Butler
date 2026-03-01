import os
import json
from dotenv import load_dotenv
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

# Load environment variables once
load_dotenv()

class ConfigLoader:
    _instance = None
    _config = {}
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _config_path = os.path.join(_project_root, "config", "system_config.json")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        """Loads configuration from JSON file."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config from {self._config_path}: {e}")
                self._config = {}
        else:
            logger.warning(f"Config file not found at {self._config_path}. Using defaults/env.")
            self._config = {}

    def get(self, key_path: str, default=None):
        """
        Retrieves a configuration value using a dot-separated path (e.g., 'api.deepseek.key').
        Falls back to environment variables if the key is not found in JSON.
        """
        parts = key_path.split('.')
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break

        if value is not None:
            return value

        # Fallback to Environment Variables (uppercase, dot replaced by underscore)
        env_key = key_path.upper().replace('.', '_')
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        return default

    def save(self, new_config: dict = None):
        """Saves current config back to JSON."""
        if new_config:
            self._config.update(new_config)

        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

# Global instance for easy access
config_loader = ConfigLoader()
