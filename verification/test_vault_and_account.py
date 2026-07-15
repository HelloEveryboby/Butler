import unittest
import os
import shutil
import tempfile
import sys
from unittest.mock import MagicMock

# Mock pyautogui, pyperclip, and selenium before importing AccountPassword
sys.modules['pyautogui'] = MagicMock()
sys.modules['pyperclip'] = MagicMock()
sys.modules['selenium'] = MagicMock()
sys.modules['selenium.webdriver.chrome.service'] = MagicMock()
sys.modules['selenium.webdriver.chrome.options'] = MagicMock()
sys.modules['selenium.webdriver.common.by'] = MagicMock()
sys.modules['selenium.webdriver.common.keys'] = MagicMock()
sys.modules['selenium.webdriver.support.ui'] = MagicMock()
sys.modules['selenium.webdriver.support'] = MagicMock()
sys.modules['webdriver_manager.chrome'] = MagicMock()

from butler.core.secret_vault import SecretVault
from package.security.AccountPassword import AccountManager

class TestVaultAndAccount(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_secret_vault_argon2_and_gcm(self):
        # Initialize custom SecretVault with database in temp dir
        db_path = os.path.join(self.test_dir, "secrets.db")
        vault = SecretVault(db_path=db_path)

        # Initialize via master password (triggers SymmetricCrypto.derive_key i.e. Argon2id/PBKDF2)
        password = "vault_master_pass_2026!"
        res = vault.initialize(password)
        self.assertTrue(res)

        # Set and get secret
        vault.set_secret("deepseek_api_key", "sk-deepseek1234567890abcdef")
        secret = vault.get_secret("deepseek_api_key")
        self.assertEqual(secret, "sk-deepseek1234567890abcdef")

        # Test scrubbing
        vault.clear_session_key()
        self.assertIsNone(vault._master_key)

        # Re-initialize to verify key recovery
        vault.initialize(password)
        self.assertEqual(vault.get_secret("deepseek_api_key"), "sk-deepseek1234567890abcdef")

    def test_account_password_manager_gcm(self):
        # Override AccountManager.DB_PATH to use a temp db file
        temp_db = os.path.join(self.test_dir, "accounts.db")

        # Mock class variables or override inst
        old_db_path = AccountManager.DB_PATH
        AccountManager.DB_PATH = temp_db

        try:
            manager = AccountManager()

            # Setup master key
            manager.encryption_salt = os.urandom(16)
            from package.security.crypto_core import SymmetricCrypto
            manager.master_key = SymmetricCrypto.derive_key("master_pwd_987", manager.encryption_salt)

            # Encrypt and decrypt a password with AES-256-GCM
            test_pass = "my_super_secret_social_password"
            nonce, ct, tag = manager._encrypt(test_pass)

            # Verify we have non-empty tag (indicating GCM is active)
            self.assertIsNotNone(tag)
            self.assertTrue(len(tag) > 0)

            # Decrypt GCM
            decrypted = manager._decrypt(nonce, ct, tag=tag)
            self.assertEqual(decrypted, test_pass)

            # Test backward compatibility (CBC fallback)
            # Create old-style encrypted data (2-value iv, ct using AES-CBC)
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            import base64

            # Old AES-CBC Key (16 bytes derived from master key)
            l1_key = manager.master_key[:16]
            cipher = AES.new(l1_key, AES.MODE_CBC)
            old_iv = base64.b64encode(cipher.iv).decode('utf-8')
            old_ct = base64.b64encode(cipher.encrypt(pad(test_pass.encode('utf-8'), AES.block_size))).decode('utf-8')

            # Decrypt as CBC (by passing empty tag or tag=None)
            decrypted_old = manager._decrypt(old_iv, old_ct, tag=None)
            self.assertEqual(decrypted_old, test_pass)

        finally:
            AccountManager.DB_PATH = old_db_path

if __name__ == "__main__":
    unittest.main()
