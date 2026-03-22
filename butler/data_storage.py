import json
from typing import Any, Optional
from pathlib import Path

from butler.redis_client import redis_client
from package.core_utils.log_manager import LogManager

class DataStorageManager:
    """
    Manages the storage of structured data for plugins using Redis, with local file fallback.
    This provides a simple key-value interface where keys are specific to each plugin.
    """
    def __init__(self):
        self._logger = LogManager.get_logger(__name__)
        self.redis_client = redis_client
        self.local_storage_path = Path(__file__).resolve().parent.parent / "data" / "local_storage"
        self.local_storage_path.mkdir(parents=True, exist_ok=True)

        if not self.redis_client:
            self._logger.warning("DataStorageManager initialized without a Redis connection. Falling back to local file storage.")
        else:
            self._logger.info("DataStorageManager initialized with Redis.")

    def _get_plugin_key(self, plugin_name: str, key: str) -> str:
        """
        Generates a unique Redis key for a given plugin and key.
        This ensures that data from different plugins does not conflict.
        """
        return f"plugin:{plugin_name}:data:{key}"

    def _get_local_path(self, plugin_name: str, key: str) -> Path:
        """Generates a local file path for storage."""
        return self.local_storage_path / f"{plugin_name}_{key}.json"

    def save(self, plugin_name: str, key: str, value: Any):
        """
        Saves a value for a specific plugin. The value will be serialized to JSON.
        """
        serialized_value = json.dumps(value, ensure_ascii=False)

        if self.redis_client:
            try:
                redis_key = self._get_plugin_key(plugin_name, key)
                self.redis_client.set(redis_key, serialized_value)
                self._logger.info(f"Saved data to Redis for plugin '{plugin_name}' with key '{key}'.")
                return
            except Exception as e:
                self._logger.error(f"Failed to save data to Redis for plugin '{plugin_name}' with key '{key}': {e}")

        # Fallback to local file storage
        try:
            local_path = self._get_local_path(plugin_name, key)
            with local_path.open('w', encoding='utf-8') as f:
                f.write(serialized_value)
            self._logger.info(f"Saved data to local file for plugin '{plugin_name}' with key '{key}'.")
        except Exception as e:
            self._logger.error(f"Failed to save data locally for plugin '{plugin_name}' with key '{key}': {e}")

    def load(self, plugin_name: str, key: str) -> Optional[Any]:
        """
        Loads a value for a specific plugin. The value will be deserialized from JSON.
        """
        if self.redis_client:
            try:
                redis_key = self._get_plugin_key(plugin_name, key)
                serialized_value = self.redis_client.get(redis_key)
                if serialized_value:
                    self._logger.info(f"Loaded data from Redis for plugin '{plugin_name}' with key '{key}'.")
                    return json.loads(serialized_value)
            except Exception as e:
                self._logger.error(f"Failed to load data from Redis for plugin '{plugin_name}' with key '{key}': {e}")

        # Fallback to local file storage
        try:
            local_path = self._get_local_path(plugin_name, key)
            if local_path.exists():
                with local_path.open('r', encoding='utf-8') as f:
                    serialized_value = f.read()
                self._logger.info(f"Loaded data from local file for plugin '{plugin_name}' with key '{key}'.")
                return json.loads(serialized_value)
            return None
        except Exception as e:
            self._logger.error(f"Failed to load data locally for plugin '{plugin_name}' with key '{key}': {e}")
            return None

    def delete(self, plugin_name: str, key: str):
        """
        Deletes a value for a specific plugin.
        """
        deleted = False
        if self.redis_client:
            try:
                redis_key = self._get_plugin_key(plugin_name, key)
                self.redis_client.delete(redis_key)
                self._logger.info(f"Deleted data from Redis for plugin '{plugin_name}' with key '{key}'.")
                deleted = True
            except Exception as e:
                self._logger.error(f"Failed to delete data from Redis for plugin '{plugin_name}' with key '{key}': {e}")

        # Always try to delete local file as well
        try:
            local_path = self._get_local_path(plugin_name, key)
            if local_path.exists():
                local_path.unlink()
                self._logger.info(f"Deleted data from local file for plugin '{plugin_name}' with key '{key}'.")
                deleted = True
        except Exception as e:
            self._logger.error(f"Failed to delete data locally for plugin '{plugin_name}' with key '{key}': {e}")

        if not deleted and not self.redis_client:
            self._logger.warning(f"No data found to delete for plugin '{plugin_name}' with key '{key}'.")

# Global instance to be used across the application
data_storage_manager = DataStorageManager()
