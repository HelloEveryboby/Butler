"""
Unit tests for Screen Capture & Recording Skill
"""
import unittest
import os
from skills.screen_capture import main

class TestScreenCapture(unittest.TestCase):
    def test_full_screenshot(self):
        res = main.execute("full_screenshot")
        self.assertEqual(res["status"], "success")
        self.assertTrue(os.path.exists(res["file_path"]))

    def test_area_screenshot(self):
        rect = {"x": 10, "y": 20, "width": 300, "height": 200}
        res = main.execute("area_screenshot", rect=rect)
        self.assertEqual(res["status"], "success")
        self.assertTrue(os.path.exists(res["file_path"]))

    def test_long_screenshot(self):
        res = main.execute("long_screenshot")
        self.assertEqual(res["status"], "success")
        self.assertTrue(os.path.exists(res["file_path"]))

    def test_recording_flow(self):
        start_res = main.execute("start_recording", type="full")
        self.assertEqual(start_res["status"], "success")

        stop_res = main.execute("stop_recording")
        self.assertEqual(stop_res["status"], "success")
        self.assertTrue(os.path.exists(stop_res["file_path"]))

if __name__ == "__main__":
    unittest.main()
