import json
from typing import Any, Optional

from butler.redis_client import redis_client
from package.log_manager import LogManager

class DataStorageManager:
    """
    Manages the storage of structured data for plugins using Redis.
    This provides a simple key-value interface where keys are specific to each plugin.
    """
    def __init__(self):
        self._logger = LogManager.get_logger(__name__)
        self.redis_client = redis_client
        if not self.redis_client:
            self._logger.warning("DataStorageManager initialized without a Redis connection. Data will not be persisted.")
        else:
            self._logger.info("DataStorageManager initialized.")

    def _get_plugin_key(self, plugin_name: str, key: str) -> str:
        """
        Generates a unique Redis key for a given plugin and key.
        This ensures that data from different plugins does not conflict.
        """
        return f"plugin:{plugin_name}:data:{key}"

    def save(self, plugin_name: str, key: str, value: Any):
        """
        Saves a value for a specific plugin. The value will be serialized to JSON.
        """
        if not self.redis_client:
            self._logger.error(f"Cannot save data: No Redis connection.")
            return

        try:
            redis_key = self._get_plugin_key(plugin_name, key)
            serialized_value = json.dumps(value)
            self.redis_client.set(redis_key, serialized_value)
            self._logger.info(f"Saved data for plugin '{plugin_name}' with key '{key}'.")
        except Exception as e:
            self._logger.error(f"Failed to save data for plugin '{plugin_name}' with key '{key}': {e}")

    def load(self, plugin_name: str, key: str) -> Optional[Any]:
        """
        Loads a value for a specific plugin. The value will be deserialized from JSON.
        """
        if not self.redis_client:
            self._logger.error(f"Cannot load data: No Redis connection.")
            return None

        try:
            redis_key = self._get_plugin_key(plugin_name, key)
            serialized_value = self.redis_client.get(redis_key)
            if serialized_value:
                self._logger.info(f"Loaded data for plugin '{plugin_name}' with key '{key}'.")
                return json.loads(serialized_value)
            return None
        except Exception as e:
            self._logger.error(f"Failed to load data for plugin '{plugin_name}' with key '{key}': {e}")
            return None

    def delete(self, plugin_name: str, key: str):
        """
        Deletes a value for a specific plugin.
        """
        if not self.redis_client:
            self._logger.error(f"Cannot delete data: No Redis connection.")
            return

        try:
            redis_key = self._get_plugin_key(plugin_name, key)
            self.redis_client.delete(redis_key)
            self._logger.info(f"Deleted data for plugin '{plugin_name}' with key '{key}'.")
        except Exception as e:
            self._logger.error(f"Failed to delete data for plugin '{plugin_name}' with key '{key}': {e}")

# Global instance to be used across the application
data_storage_manager = DataStorageManager()
