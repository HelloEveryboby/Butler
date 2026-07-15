import unittest
import os
import shutil
import tempfile
import zlib
from package.security.encrypt import DualLayerEncryptor, LegacyDecryptor
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

class TestLegacyMigration(unittest.TestCase):
    def setUp(self):
        self.encryptor = DualLayerEncryptor()
        self.test_dir = tempfile.mkdtemp()
        self.sample_file = os.path.join(self.test_dir, "legacy_sample.txt")
        self.sample_content = b"Old Legacy 2.0 Content of Butler Jarvis Assistant!"

        # Manually create a Legacy 2.0 encrypted file
        # Format: magic + cipher_layer1_key + iv + ciphertext
        magic = b"BUTLER_SECURE_V2"
        password = "old_password_123"

        # Compress
        compressed = zlib.compress(self.sample_content)

        # Layer 1 Key
        l1_key = b"1234567890123456"

        # Layer 2 Key
        import hashlib
        l2_key = hashlib.sha256(password.encode()).digest()

        # Cipher Layer 1 Key via XOR with Layer 2 Key[:16]
        cipher_layer1_key = bytes(a ^ b for a, b in zip(l1_key, l2_key[:16]))

        # Encrypt content via AES-CBC
        cipher = AES.new(l1_key, AES.MODE_CBC)
        iv = cipher.iv
        ciphertext = cipher.encrypt(pad(compressed, AES.block_size))

        with open(self.sample_file + ".ble", 'wb') as f:
            f.write(magic)
            f.write(cipher_layer1_key)
            f.write(iv)
            f.write(ciphertext)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_legacy_migration_to_v3(self):
        legacy_file = self.sample_file + ".ble"
        password = "old_password_123"

        # Decrypting a Legacy 2.0 file should trigger auto-migration in decrypt_file
        decrypted_path = os.path.join(self.test_dir, "restored.txt")
        res = self.encryptor.decrypt_file(legacy_file, password, decrypted_path)

        # The result of decrypt_file in migration mode is returning the path to the decrypted file
        self.assertEqual(res, decrypted_path)

        # Check decrypted file content
        with open(decrypted_path, 'rb') as f:
            self.assertEqual(f.read(), self.sample_content)

        # Also check that the legacy file itself has been converted into V3 format!
        with open(legacy_file, 'rb') as f:
            header = f.read(16)
            self.assertEqual(header, b"BUTLER_SECURE_V3")

if __name__ == "__main__":
    unittest.main()
