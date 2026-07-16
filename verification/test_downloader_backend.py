import unittest
import os
import sys
import json
import shutil

# Add repository root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.downloader import (
    load_tasks,
    save_tasks,
    handle_request,
    calculate_eta,
    format_bytes,
    DOWNLOADS_DIR,
    CONFIG_PATH
)

class TestDownloaderBackend(unittest.TestCase):
    def setUp(self):
        # Back up existing tasks
        self.backup_exists = os.path.exists(CONFIG_PATH)
        self.backup_content = ""
        if self.backup_exists:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.backup_content = f.read()

        # Start with empty clean task list
        save_tasks({})

    def tearDown(self):
        # Restore backup
        if self.backup_exists:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(self.backup_content)
        elif os.path.exists(CONFIG_PATH):
            os.remove(CONFIG_PATH)

    def test_load_save_tasks(self):
        """Test task database serialization."""
        test_tasks = {
            "test_id": {
                "id": "test_id",
                "name": "test_file.bin",
                "status": "pending"
            }
        }
        save_tasks(test_tasks)
        loaded = load_tasks()
        self.assertIn("test_id", loaded)
        self.assertEqual(loaded["test_id"]["name"], "test_file.bin")

    def test_format_helpers(self):
        """Test file size and ETA string formatters."""
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(1500), "1.5 KB")
        self.assertEqual(format_bytes(3 * 1024 * 1024), "3.0 MB")

        self.assertEqual(calculate_eta(10, 100, 10), "9秒")
        self.assertEqual(calculate_eta(10, 1000, 10), "1分39秒")

    def test_thunder_link_decoding(self):
        """Test Thunder link base64 parser."""
        # thunder://AAh0dHBzOi8vd3d3Ljd6aXAub3JnL2EvN3oyNDA3LXg2NC5leGVaWg==
        # Decodes to https://www.7zip.org/a/7z2407-x64.exe
        thunder_link = "thunder://AAh0dHBzOi8vd3d3Ljd6aXAub3JnL2EvN3oyNDA3LXg2NC5leGVaWg=="
        res = handle_request("add_task", url=thunder_link, category="software", scheduled_time="03:00")

        self.assertEqual(res["status"], "ok")
        # Load tasks to check decoded URL
        tasks = load_tasks()
        task = tasks[res["task_id"]]
        self.assertEqual(task["url"], "https://www.7zip.org/a/7z2407-x64.exe")
        self.assertEqual(task["original_url"], thunder_link)

    def test_aggregate_search(self):
        """Test multi-hub aggregated search results."""
        results = handle_request("aggregate_search", query="毒液")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["provider"], "磁力猫")
        self.assertIn("magnet:", results[0]["url"])

    def test_network_diagnostics(self):
        """Test network diagnosis pings and trackers checks."""
        res = handle_request("network_diagnose")
        self.assertIn("ping_dns_114", res)
        self.assertIn("p2p_tracker_blocking", res)

    def test_storage_drives_listing(self):
        """Test Storage Hub linkage integrations."""
        drives = handle_request("get_storage_drives")
        self.assertGreater(len(drives), 0)
        self.assertIn("name", drives[0])

if __name__ == "__main__":
    unittest.main()
