import unittest
import traceback
from unittest.mock import MagicMock, patch
import sys

class TestImport(unittest.TestCase):
    def test_can_import_main(self):
        """
        A minimal test to identify the root cause of the import failure.
        This test now mocks dependencies that are not available in the
        headless test environment.
        """
        MOCK_MODULES = {
            'tkinter': MagicMock(),
            'requests': MagicMock(),
            'watchdog': MagicMock(),
            'watchdog.observers': MagicMock(),
            'watchdog.events': MagicMock(),
            'dotenv': MagicMock(),
        }
        with patch.dict(sys.modules, MOCK_MODULES):
            try:
                from butler import main
                print("Successfully imported butler.main")
            except Exception as e:
                traceback.print_exc()
                self.fail(f"Failed to import butler.main: {e}")

if __name__ == "__main__":
    unittest.main()