import os
import base64
import json
import logging
import sqlite3
from typing import Optional, Dict, Any
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from butler.core.constants import DATA_DIR

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger("SecretVault")

class SecretVault:
    """
    Butler 机密管理模块 (Zero-Trust Vault).
    支持系统凭据管理器 (Keyring) + PBKDF2 主密码派生的双模加密 (AES-256-GCM)。
    """
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path or DATA_DIR / "system_data" / "secrets.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._master_key = None
        self._key_source = None # 'keyring' or 'password'

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS secrets (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    nonce BLOB,
                    tag TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vault_meta (
                    meta_key TEXT PRIMARY KEY,
                    meta_value TEXT
                )
            """)

    def initialize(self, master_password: str = None) -> bool:
        """
        初始化保险库密钥。
        1. 尝试从 Keyring 获取系统生成的随机根密钥。
        2. 如果失败且提供了 master_password，则通过 PBKDF2 派生密钥。
        """
        # 1. Try Keyring
        if keyring:
            try:
                system_root_key = keyring.get_password("Butler", "VaultRootKey")
                if not system_root_key:
                    # 第一次运行，生成随机密钥存入 Keyring
                    system_root_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                    keyring.set_password("Butler", "VaultRootKey", system_root_key)

                self._master_key = base64.b64decode(system_root_key)
                self._key_source = 'keyring'
                logger.info("SecretVault initialized via System Keyring.")
                return True
            except Exception as e:
                logger.warning(f"Failed to use Keyring: {e}")

        # 2. Fallback to Master Password
        if master_password:
            salt = self._get_or_create_salt()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            self._master_key = kdf.derive(master_password.encode())
            self._key_source = 'password'
            logger.info("SecretVault initialized via Master Password.")
            return True

        return False

    def _get_or_create_salt(self) -> bytes:
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT meta_value FROM vault_meta WHERE meta_key='salt'").fetchone()
            if res:
                return base64.b64decode(res[0])
            else:
                salt = os.urandom(16)
                conn.execute("INSERT INTO vault_meta (meta_key, meta_value) VALUES ('salt', ?)", (base64.b64encode(salt).decode(),))
                return salt

    def set_secret(self, key: str, value: str):
        if not self._master_key:
            raise RuntimeError("Vault not initialized.")

        aesgcm = AESGCM(self._master_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, value.encode(), None)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO secrets (key, value, nonce) VALUES (?, ?, ?)",
                (key, ciphertext, nonce)
            )

    def get_secret(self, key: str) -> Optional[str]:
        if not self._master_key:
            raise RuntimeError("Vault not initialized.")

        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT value, nonce FROM secrets WHERE key=?", (key,)).fetchone()
            if not res:
                return None

            ciphertext, nonce = res
            aesgcm = AESGCM(self._master_key)
            try:
                decrypted = aesgcm.decrypt(nonce, ciphertext, None)
                return decrypted.decode()
            except Exception as e:
                logger.error(f"Failed to decrypt secret '{key}': {e}")
                return None

    def list_secrets(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            return [row[0] for row in conn.execute("SELECT key FROM secrets").fetchall()]

    def delete_secret(self, key: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM secrets WHERE key=?", (key,))

secret_vault = SecretVault()
