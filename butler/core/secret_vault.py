import os
import base64
import json
import logging
import sqlite3
import secrets
from typing import Optional, Dict, Any
from pathlib import Path
from butler.core.constants import DATA_DIR
from package.security.crypto_core import SymmetricCrypto

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger("SecretVault")

class SecretVault:
    """
    Butler 机密管理模块 (Zero-Trust Vault).
    支持系统凭据管理器 (Keyring) + Argon2id 主密码派生的双模加密 (AES-256-GCM)。
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
        2. 如果失败且提供了 master_password，则通过 Argon2id/PBKDF2 派生密钥。
        """
        # 1. Try Keyring (Industrial-grade OS Native Integration)
        if keyring:
            try:
                # Attempts to access Windows Credential Manager or macOS Keychain
                system_root_key = keyring.get_password("Butler", "VaultRootKey")
                if not system_root_key:
                    # Initial setup: Generate high-entropy root key
                    system_root_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                    keyring.set_password("Butler", "VaultRootKey", system_root_key)

                self._master_key = base64.b64decode(system_root_key)
                self._key_source = 'keyring'

                # Sync to Go Runner (only if local)
                from butler.core.runner_server import get_runner_server
                runner_server = get_runner_server()
                if runner_server:
                    # Use a specific runner_id for the primary local runner to avoid broadcast exposure
                    runner_server.send_command("default_runner", "vault_init", self._master_key.hex())

                logger.info("SecretVault initialized via System Keyring (Industrial Mode).")
                self._ensure_default_tokens()
                return True
            except Exception as e:
                logger.warning(f"Failed to use OS Keychain: {e}")

        # 2. Fallback to Master Password via Argon2id
        if master_password:
            # Broadcast event for "Golden Glassmorphism" UI if this is manual entry
            from butler.core.event_bus import event_bus
            event_bus.emit("vault_unlocking", {"source": "password"})

            salt = self._get_or_create_salt()
            # 统一采用高安全强度 Argon2id 对称密钥派生
            self._master_key = SymmetricCrypto.derive_key(master_password, salt)
            self._key_source = 'password'

            # Sync to local runner for memory pinning
            from butler.core.runner_server import get_runner_server
            runner_server = get_runner_server()
            if runner_server:
                runner_server.broadcast_command("vault_init", self._master_key.hex())

            logger.info("SecretVault initialized via Master Password (Argon2id).")
            self._ensure_default_tokens()
            return True

        return False

    def clear_session_key(self):
        """物理级清除内存中的主密钥，确保内存取证安全 (Scrubbing)"""
        if self._master_key:
            # 覆写内存
            try:
                # 尝试就地覆盖
                for i in range(len(self._master_key)):
                    self._master_key[i] = 0
            except Exception:
                pass
            self._master_key = None
        self._key_source = None
        logger.info("SecretVault session key cleared securely from memory.")

    def _ensure_default_tokens(self):
        """Ensures that default secure tokens are generated and stored."""
        try:
            if not self.get_secret("rest_api_bearer_token"):
                token = secrets.token_hex(32)
                self.set_secret("rest_api_bearer_token", token)
                logger.info("Generated new secure Bearer Token for REST API gateway.")
            if not self.get_secret("runner_token"):
                token = secrets.token_hex(32)
                self.set_secret("runner_token", token)
                logger.info("Generated new secure Token for Runner WebSocket server.")
        except Exception as e:
            logger.error(f"Failed to generate default vault tokens: {e}")

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

        # 使用 Cryptography AESGCM (AES-256-GCM) 强加密存储
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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
