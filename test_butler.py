import unittest
from unittest.mock import MagicMock, patch


from butler.butler_app import Jarvis

class TestButler(unittest.TestCase):

    def setUp(self):
        """Set up a mock root for the Jarvis instance."""
        self.mock_root = MagicMock()

    @patch.object(Jarvis, '_initialize_long_memory')
    def test_data_storage_persistence(self, mock_init_long_memory):
        """
        Tests that data saved using the DataStorageManager persists across different Jarvis instances.
        """
        from butler.data_storage import data_storage_manager
        from butler.core.extension_manager import extension_manager
        # 1. Setup mock and first Jarvis instance
        mock_init_long_memory.return_value = None

        # Setup mock storage
        storage = {}
        def mock_save(plugin, key, val): storage[f"{plugin}:{key}"] = val
        def mock_load(plugin, key): return storage.get(f"{plugin}:{key}")

        with patch.object(data_storage_manager, 'save', side_effect=mock_save), \
             patch.object(data_storage_manager, 'load', side_effect=mock_load):

            jarvis1 = Jarvis(self.mock_root)
            user_profile_plugin1 = extension_manager.plugin_manager.get_plugin("UserProfilePlugin")
            self.assertIsNotNone(user_profile_plugin1, "UserProfilePlugin should be loaded")

            # 2. Save data using the first instance
            user_name = "test_user"
            save_command = f"remember my name is {user_name}"
            save_args = {"name": user_name}
            save_result = user_profile_plugin1.run(save_command, save_args)
            self.assertTrue(save_result.success)
            self.assertIn(f"Okay, I've remembered your name is {user_name}", save_result.result)

            # 3. Create a new Jarvis instance to simulate a restart
            jarvis2 = Jarvis(self.mock_root)
            user_profile_plugin2 = extension_manager.plugin_manager.get_plugin("UserProfilePlugin")
            self.assertIsNotNone(user_profile_plugin2, "UserProfilePlugin should be loaded in the new instance")

            # 4. Retrieve the data using the second instance
            load_command = "what is my name"
            load_args = {}
            load_result = user_profile_plugin2.run(load_command, load_args)
            self.assertTrue(load_result.success)
            self.assertIn(f"Your name is {user_name}", load_result.result)


if __name__ == "__main__":
    unittest.main()
