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

    # Mapping of logical config paths to common/legacy environment variable names
    _legacy_env_map = {
        "api.deepseek.key": "DEEPSEEK_API_KEY",
        "api.baidu.app_id": "BAIDU_APP_ID",
        "api.baidu.api_key": "BAIDU_API_KEY",
        "api.baidu.secret_key": "BAIDU_SECRET_KEY",
        "api.azure.speech.key": "AZURE_SPEECH_KEY",
        "api.azure.speech.region": "AZURE_SERVICE_REGION",
        "api.azure.translate.key": "AZURE_TRANSLATE_KEY",
        "api.picovoice.access_key": "PICOVOICE_ACCESS_KEY",
        "api.bing.search_key": "BING_SEARCH_API_KEY"
    }

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
            # Check if it's a placeholder (e.g., "YOUR_API_KEY_HERE")
            if isinstance(value, str) and value.startswith("YOUR_") and value.endswith("_HERE"):
                pass # Fall back to environment variables
            else:
                return value

        # 1. Fallback to specific legacy environment variable names
        legacy_key = self._legacy_env_map.get(key_path)
        if legacy_key:
            env_val = os.getenv(legacy_key)
            if env_val: return env_val

        # 2. Fallback to standard hierarchical environment variable naming (API_DEEPSEEK_KEY)
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
