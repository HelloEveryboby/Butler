import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import sys


class TestJarvisProgramLoading(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for package files."""
        self.test_dir = tempfile.mkdtemp(prefix="butler_test_")
        self.package_dir = os.path.join(self.test_dir, "package")
        os.makedirs(self.package_dir)
        self.mock_root = MagicMock()

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_dynamic_program_loading(self):
        """
        Tests that new programs are loaded correctly.
        This test patches all dependencies that fail in a headless environment.
        """
        # A comprehensive list of all modules that cause import errors.
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
            'pandas': MagicMock(),
            'markdownify': MagicMock(),
            'docx': MagicMock(),
            'pptx': MagicMock(),
            'pdfplumber': MagicMock(),
            'PIL': MagicMock(),
            'PIL.ExifTags': MagicMock(),
            'pytesseract': MagicMock(),
            'ebooklib': MagicMock(),
            'bs4': MagicMock(),
            'tqdm': MagicMock(),
            'openai': MagicMock(),
            'pyautogui': MagicMock(),
            'mss': MagicMock(),
            'pyttsx3': MagicMock(),
            'pygame': MagicMock(),
            'azure.cognitiveservices.speech': MagicMock(),
            'pydub': MagicMock(),
            'pydub.playback': MagicMock(),
        }

        # Use patch.dict to temporarily add the mocks to sys.modules
        with patch.dict(sys.modules, MOCK_MODULES):
            # The original patch for Interpreter is still needed to avoid
            # its initialization logic (e.g., loading API keys).
            with patch('butler.main.Interpreter', new_callable=MagicMock):
                from butler.main import Jarvis

                # Further patch methods on Jarvis to prevent side effects during instantiation.
                with patch.object(Jarvis, '_initialize_long_memory', return_value=None), \
                     patch.object(Jarvis, 'speak', return_value=None):

                    # 1. Instantiate Jarvis.
                    jarvis = Jarvis(self.mock_root)
                    jarvis.program_folder = [self.package_dir] # Set the program folder for the test

                    # 2. Create an initial program file.
                    prog1_path = os.path.join(self.package_dir, "prog1.py")
                    with open(prog1_path, "w") as f:
                        f.write("def run(): pass")

                    # 3. Call open_programs for the first time.
                    programs_before = jarvis.open_programs(self.package_dir)
                    prog1_name = f"{os.path.basename(self.package_dir)}.prog1"
                    self.assertIn(prog1_name, programs_before, "Initial program was not loaded.")
                    self.assertEqual(len(programs_before), 1)

                    # 4. Create a new program file at runtime.
                    prog2_path = os.path.join(self.package_dir, "prog2.py")
                    with open(prog2_path, "w") as f:
                        f.write("def run(): pass")

                    # 5. Call open_programs again on the same instance.
                    programs_after = jarvis.open_programs(self.package_dir)
                    prog2_name = f"{os.path.basename(self.package_dir)}.prog2"

                    # 6. Assert that the new program is loaded.
                    self.assertIn(prog2_name, programs_after, "Newly added program was not detected.")
                    self.assertEqual(len(programs_after), 2, "The program count should be 2 after adding the new program.")

if __name__ == "__main__":
    unittest.main()