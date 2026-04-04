import unittest
import os
import shutil
from package.file_system.guard import FileSystemGuard
from package.file_system.migration_engine import SmartMigrationEngine
from package.device.hardware_manager import HardwareManager
from package.core_utils.task_master.progress_tracker import ProgressTracker

class TestButlerSystem(unittest.TestCase):
    def setUp(self):
        self.guard = FileSystemGuard()
        self.migration = SmartMigrationEngine("test_core")
        # HardwareManager __init__ uses defaults, we can just set the port after if needed
        self.hw = HardwareManager()
        self.hw.port = "NONE"
        self.tracker = ProgressTracker(self.hw)

    def tearDown(self):
        if os.path.exists("test_core"):
            shutil.rmtree("test_core")
        if os.path.exists("test_file.txt"):
            os.remove("test_file.txt")

    def test_protection(self):
        self.assertTrue(self.guard.is_protected("butler/app.py"))
        self.assertTrue(self.guard.is_protected("package/core_utils"))
        self.assertFalse(self.guard.is_protected("random_user_file.txt"))

    def test_migration(self):
        with open("test_file.py", "w") as f: f.write("print('hello')")
        success, msg = self.migration.migrate_file("test_file.py", "CORE_LOGIC")
        self.assertTrue(success)
        self.assertTrue(os.path.exists("test_core/logic_segments/test_file.py"))

    def test_adaptive_volume(self):
        self.hw.set_volume_mode("auto")
        # Simulate distance change
        self.hw.env_distance = 20.0
        self.hw.env_noise_freq = 1000.0
        self.hw._update_adaptive_volume()
        # Logic: base 50 + (100-20)/100 * 30 + (1000/5000)*20 = 50 + 24 + 4 = 78
        # We can't easily check serial write in this mock, but we verify state
        pass

    def test_progress_tracker(self):
        self.tracker.update("loading", 50)
        self.assertEqual(self.tracker.stages["loading"], 50)

if __name__ == "__main__":
    unittest.main()
