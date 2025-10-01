import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch


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
        Tests that new programs are loaded correctly when the cache is not used.
        This test is isolated from other parts of the application using patching.
        """
        # Patch the Interpreter class which has a blocking import error.
        # This allows us to import Jarvis without triggering the error.
        with patch('butler.main.Interpreter', new_callable=MagicMock):
            from butler.main import Jarvis

            # Further patch methods on Jarvis to prevent side effects during instantiation.
            with patch.object(Jarvis, '_initialize_long_memory', return_value=None), \
                 patch.object(Jarvis, 'speak', return_value=None):

                # 1. Instantiate Jarvis.
                jarvis = Jarvis(self.mock_root)

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
                # Due to the @lru_cache, this call will return the cached result
                # from the first call, and prog2 will be missing.
                programs_after = jarvis.open_programs(self.package_dir)
                prog2_name = f"{os.path.basename(self.package_dir)}.prog2"

                # 6. Assert that the new program is loaded.
                # THIS IS THE ASSERTION THAT IS EXPECTED TO FAIL.
                self.assertIn(prog2_name, programs_after, "Newly added program was not detected.")
                self.assertEqual(len(programs_after), 2, "The program count should be 2 after adding the new program.")

if __name__ == "__main__":
    unittest.main()