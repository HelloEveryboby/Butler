import unittest
import os
import shutil
import tempfile
from package.security.encrypt import DualLayerEncryptor, SecureVault

class TestDualLayerEncryptor(unittest.TestCase):
    def setUp(self):
        self.encryptor = DualLayerEncryptor()
        self.test_dir = tempfile.mkdtemp()
        self.sample_file = os.path.join(self.test_dir, "sample.txt")
        self.sample_content = b"Butler Jarvis Secure Vault v3 Test Data: Hello World!"
        with open(self.sample_file, 'wb') as f:
            f.write(self.sample_content)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_encrypt_decrypt_v3(self):
        # 3.0 Standard Password
        password = "strong_password_123!"
        ble_file = self.encryptor.encrypt_file(self.sample_file, password)
        self.assertTrue(os.path.exists(ble_file))

        # Decrypt V3
        decrypted_file = os.path.join(self.test_dir, "decrypted.txt")
        res = self.encryptor.decrypt_file(ble_file, password, decrypted_file)
        self.assertEqual(res, decrypted_file)

        with open(decrypted_file, 'rb') as f:
            self.assertEqual(f.read(), self.sample_content)

    def test_encrypt_decrypt_v3_six_digit(self):
        # 3.0 Low-Entropy 6 digit code
        password = "123456"
        ble_file = self.encryptor.encrypt_file(self.sample_file, password)
        self.assertTrue(os.path.exists(ble_file))

        # Decrypt V3
        decrypted_file = os.path.join(self.test_dir, "decrypted.txt")
        res = self.encryptor.decrypt_file(ble_file, password, decrypted_file)
        self.assertEqual(res, decrypted_file)

        with open(decrypted_file, 'rb') as f:
            self.assertEqual(f.read(), self.sample_content)

if __name__ == "__main__":
    unittest.main()
