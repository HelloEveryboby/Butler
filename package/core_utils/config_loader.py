import os
import json
import yaml
import re
from typing import Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from package.core_utils.log_manager import LogManager
from butler.core.constants import PROJECT_ROOT, SYSTEM_CONFIG_YAML, SYSTEM_CONFIG_JSON
from butler.core.config_model import ButlerConfig
from pydantic import ValidationError

logger = LogManager.get_logger(__name__)

# Load environment variables once
load_dotenv()

class ConfigLoader:
    _instance = None
    _config_obj: ButlerConfig = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _substitute_env_vars(self, content: str) -> str:
        """Substitutes ${VAR:-default} and ${VAR} in the string with environment variables."""
        def replace(match):
            var_name = match.group(1) or match.group(3)
            default = match.group(2) if match.group(2) is not None else ""
            return os.getenv(var_name, default)

        # Pattern for ${VAR:-default} or ${VAR}
        pattern = re.compile(r'\$\{(\w+)(?::-([^}]*))?\}|\$(\w+)')
        return pattern.sub(replace, content)

    def _load(self):
        """Loads configuration from YAML (preferred) or JSON file."""
        config_data = {}

        # 1. Try YAML
        if SYSTEM_CONFIG_YAML.exists():
            try:
                with open(SYSTEM_CONFIG_YAML, 'r', encoding='utf-8') as f:
                    content = f.read()
                    content = self._substitute_env_vars(content)
                    config_data = yaml.safe_load(content) or {}
                logger.info(f"Loaded config from {SYSTEM_CONFIG_YAML}")
            except Exception as e:
                logger.error(f"Failed to load YAML config: {e}")

        # 2. Try JSON (Fallback/Migration)
        elif SYSTEM_CONFIG_JSON.exists():
            try:
                with open(SYSTEM_CONFIG_JSON, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                logger.info(f"Loaded config from {SYSTEM_CONFIG_JSON} (legacy)")
            except Exception as e:
                logger.error(f"Failed to load JSON config: {e}")

        # 3. Validate with Pydantic
        try:
            self._config_obj = ButlerConfig(**config_data)
        except ValidationError as ve:
            logger.error(f"Configuration validation failed: {ve}")
            # Fallback to default config if validation fails
            self._config_obj = ButlerConfig()

    @property
    def _config(self):
        # Backward compatibility for code directly accessing _config
        return self._config_obj.model_dump()

    def get(self, key_path: str, default=None):
        """
        Retrieves a configuration value using a dot-separated path.
        """
        parts = key_path.split('.')
        value = self._config_obj.model_dump()
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break

        if value is not None:
            return value

        # Fallback to Environment Variables
        env_key = key_path.upper().replace('.', '_')
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        return default

    def save(self, new_config_updates: dict = None):
        """Saves current config back to YAML."""
        if new_config_updates:
            # We need to update the object and save
            current_data = self._config_obj.model_dump()

            # Simple recursive update
            def update(d, u):
                for k, v in u.items():
                    if isinstance(v, dict):
                        d[k] = update(d.get(k, {}), v)
                    else:
                        d[k] = v
                return d

            update(current_data, new_config_updates)
            try:
                self._config_obj = ButlerConfig(**current_data)
            except ValidationError as ve:
                logger.error(f"Failed to update config (validation error): {ve}")
                return False

        try:
            SYSTEM_CONFIG_YAML.parent.mkdir(parents=True, exist_ok=True)
            with open(SYSTEM_CONFIG_YAML, 'w', encoding='utf-8') as f:
                # Save as YAML without env var expansion (to preserve structure, though env vars will be lost if not careful)
                # Actually, standard practice is to save actual values.
                yaml.dump(self._config_obj.model_dump(), f, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

# Global instance for easy access
config_loader = ConfigLoader()
