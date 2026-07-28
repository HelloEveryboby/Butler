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

        安全修复：
        - PBKDF2 迭代次数提升至 600,000（OWASP 2023 建议）
        - 移除主密钥明文传输至 Runner 的不安全行为
        - Runner 密钥改为通过 HKDF 派生子密钥，按需分发
        """
        # 1. Try Keyring (Industrial-grade OS Native Integration)
        if keyring:
            try:
                system_root_key = keyring.get_password("Butler", "VaultRootKey")
                if not system_root_key:
                    system_root_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                    keyring.set_password("Butler", "VaultRootKey", system_root_key)

                self._master_key = base64.b64decode(system_root_key)
                self._key_source = 'keyring'

                # [Security Fix] 不再向 Runner 传输主密钥
                # Runner 通过独立的 token 认证，密钥派生走 HKDF
                self._sync_runner_derived_key()

                logger.info("SecretVault initialized via System Keyring (Industrial Mode).")
                self._ensure_default_tokens()
                return True
            except Exception as e:
                logger.warning(f"Failed to use OS Keychain: {e}")

        # 2. Fallback to Master Password
        if master_password:
            from butler.core.event_bus import event_bus
            event_bus.emit("vault_unlocking", {"source": "password"})

            salt = self._get_or_create_salt()
            # [Security Fix] PBKDF2 迭代次数提升至 600,000（OWASP 2023 建议）
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=600000,
            )
            self._master_key = kdf.derive(master_password.encode())
            self._key_source = 'password'

            # [Security Fix] 不再广播主密钥
            self._sync_runner_derived_key()

            logger.info("SecretVault initialized via Master Password (PBKDF2 600K iterations).")
            self._ensure_default_tokens()
            return True

        return False

    def _sync_runner_derived_key(self) -> None:
        """
        [Security Fix] 使用 HKDF 从主密钥派生 Runner 专用子密钥，
        替代旧的明文主密钥传输方案。
        """
        try:
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashes as _hashes

            hkdf = HKDF(
                algorithm=_hashes.SHA256(),
                length=32,
                salt=None,
                info=b"butler-runner-auth-key-v1",
            )
            runner_key = hkdf.derive(self._master_key)

            # 仅向本地默认 Runner 分发派生子密钥（非主密钥）
            from butler.core.runner_server import runner_server
            runner_server.send_command(
                "default_runner", "vault_init", runner_key.hex()
            )
            logger.debug("Runner 派生子密钥已同步（HKDF）")
        except Exception as e:
            logger.warning(f"Runner 密钥派生同步失败（非致命）: {e}")

    def _ensure_default_tokens(self):
        """Ensures that default secure tokens are generated and stored."""
        import secrets
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
