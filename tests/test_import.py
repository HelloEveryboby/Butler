import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

class TestImport(unittest.TestCase):
    def test_can_import_butler(self):
        project_root = Path(__file__).resolve().parent.parent
        src_path = project_root / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Mock pydantic.ValidationError properly so it's a type
        class MockValidationError(Exception):
            pass

        MOCK_MODULES = {
            'tkinter': MagicMock(),
            'requests': MagicMock(),
            'watchdog': MagicMock(),
            'watchdog.observers': MagicMock(),
            'watchdog.events': MagicMock(),
            'dotenv': MagicMock(),
            'numpy': MagicMock(),
            'cv2': MagicMock(),
            'sklearn': MagicMock(),
            'pypinyin': MagicMock(),
            'pyttsx3': MagicMock(),
            'pygame': MagicMock(),
            'pydub': MagicMock(),
            'instructor': MagicMock(),
            'pandas': MagicMock(),
            'yaml': MagicMock(),
            'pydantic': MagicMock(),
            'pydantic.ValidationError': MockValidationError,
            'mss': MagicMock(),
            'PIL': MagicMock(),
            'pyautogui': MagicMock(),
            'redis': MagicMock(),
            'psutil': MagicMock(),
            'websockets': MagicMock(),
        }

        with patch.dict(sys.modules, MOCK_MODULES):
            try:
                from Butler import Butler
                print("Successfully imported Butler class")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.fail(f"Failed to import Butler: {e}")

if __name__ == "__main__":
    unittest.main()
