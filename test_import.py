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
            'numpy': MagicMock(),
            'cv2': MagicMock(),
            'sklearn': MagicMock(),
            'sklearn.feature_extraction': MagicMock(),
            'sklearn.feature_extraction.text': MagicMock(),
            'sklearn.metrics': MagicMock(),
            'sklearn.metrics.pairwise': MagicMock(),
            'sklearn.cluster': MagicMock(),
            'pypinyin': MagicMock(),
            'pyttsx3': MagicMock(),
            'pygame': MagicMock(),
            'azure': MagicMock(),
            'azure.cognitiveservices': MagicMock(),
            'azure.cognitiveservices.speech': MagicMock(),
            'pydub': MagicMock(),
            'pydub.playback': MagicMock(),
            'instructor': MagicMock(),
            'pandas': MagicMock(),
            'markdownify': MagicMock(),
            'docx': MagicMock(),
            'pptx': MagicMock(),
            'pdfplumber': MagicMock(),
            'openpyxl': MagicMock(),
            'pytesseract': MagicMock(),
            'ebooklib': MagicMock(),
            'bs4': MagicMock(),
            'tabulate': MagicMock(),
            'PIL': MagicMock(),
            'PIL.ExifTags': MagicMock(),
            'tqdm': MagicMock(),
            'openai': MagicMock(),
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