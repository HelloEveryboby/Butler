import unittest
import os
import shutil
import tempfile
from package.security.encrypt import DualLayerEncryptor

class TestSelfDestruct(unittest.TestCase):
    def setUp(self):
        self.encryptor = DualLayerEncryptor()
        self.test_dir = tempfile.mkdtemp()
        self.sample_file = os.path.join(self.test_dir, "sensitive_data.txt")
        self.sample_content = b"Super sensitive secret information about Butler project!"
        with open(self.sample_file, 'wb') as f:
            f.write(self.sample_content)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_strategy_a_freeze_lock(self):
        # Default strategy (shred_on_destruct=False) -> Strategy A
        self.encryptor.shred_on_destruct = False

        # Manually invoke freeze lock on the file
        self.encryptor._freeze_lock_file(self.sample_file)

        # Verify the original file is removed
        self.assertFalse(os.path.exists(self.sample_file))

        # Verify the garbled frozen file exists
        garbled_file = self.sample_file + ".garbled"
        self.assertTrue(os.path.exists(garbled_file))

        # Check the magic bytes in the garbled file
        with open(garbled_file, 'rb') as f:
            magic = f.read(20)
            self.assertEqual(magic, b"BUTLER_FROZEN_LOCKED")

    def test_strategy_b_secure_shred(self):
        # Enable Strategy B
        self.encryptor.shred_on_destruct = True

        # Verify original file exists first
        self.assertTrue(os.path.exists(self.sample_file))

        # Invoke secure shredding
        self.encryptor._secure_shred_file(self.sample_file)

        # Verify that the file is completely removed from disk
        self.assertFalse(os.path.exists(self.sample_file))

        # Verify that no .garbled file is created
        self.assertFalse(os.path.exists(self.sample_file + ".garbled"))

if __name__ == "__main__":
    unittest.main()
