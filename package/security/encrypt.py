"""
高级加密工具 - Butler Secure Vault v3
支持双重高强度防御纵深体系 (Dual-Layer Encryption - AES-256-GCM + Argon2id):
1. 第一层：独立前置锁（文件唯一 AES-256 主密钥，AES-256-GCM 模式）。
2. 第二层：全局核心密码/核心码（支持任意长度强密码与 6 位数字，Argon2id/PBKDF2 强力慢速派生）。
防暴力破解：5次错误即触发高强度冷冻锁死或物理级安全粉碎（通过配置自毁策略）。

向后兼容性：
支持 Legacy 2.0 格式解密，并在首次解密成功后自动转换升级为 3.0 高强度格式。
"""

import os
import sys
import time
import zlib
import base64
import hashlib
import json
import secrets
import tempfile
from typing import Optional, Tuple

from Crypto.Random import get_random_bytes
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from package.core_utils.log_manager import LogManager

# 尝试加载 Argon2 库作为 KDF 算法的首选，若不可用则优雅 Fallback 到 PBKDF2-HMAC-SHA256
try:
    from argon2 import low_level
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False

# 内部静态 Pepper，用于升维低熵 6 位核心码，防止彩虹表或弱密码快速爆破
INTERNAL_PEPPER = b"ButlerJarvisSecureShield_v3_Pepper2026!#"

class SecureVault:
    """管理全局核心码/密码的内存存储与安全擦除"""
    _core_code: Optional[str] = None

    @classmethod
    def set_core_code(cls, code: str):
        if code and len(code) >= 6:
            cls._core_code = code
            LogManager.log_stealth("Core Password loaded into memory securely.")
            return True
        return False

    @classmethod
    def get_core_code(cls) -> Optional[str]:
        return cls._core_code

    @classmethod
    def clear(cls):
        # 内存擦除 (Scrubbing)
        cls._core_code = None

class LegacyDecryptor:
    """
    负责旧版 2.0 加密格式的解密，供 Fallback 与无损迁移引擎使用。
    """
    def __init__(self, header_magic: bytes = b"BUTLER_SECURE_V2"):
        self.header_magic = header_magic

    def _derive_layer2_key(self, core_code: str) -> bytes:
        return hashlib.sha256(core_code.encode()).digest()

    def decrypt_file_data(self, file_path: str, core_code: str) -> bytes:
        """从旧格式解密并返回原始数据字节"""
        with open(file_path, 'rb') as f:
            magic = f.read(len(self.header_magic))
            if magic != self.header_magic:
                raise ValueError("文件不是合法的 Legacy 2.0 格式")

            cipher_layer1_key = f.read(16)
            iv = f.read(16)
            ciphertext = f.read()

        layer2_key = self._derive_layer2_key(core_code)
        layer1_key = bytes(a ^ b for a, b in zip(cipher_layer1_key, layer2_key[:16]))

        cipher = AES.new(layer1_key, AES.MODE_CBC, iv)
        compressed_data = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return zlib.decompress(compressed_data)


class DualLayerEncryptor:
    def __init__(self):
        self.header_magic = b"BUTLER_SECURE_V3"
        self.legacy_magic = b"BUTLER_SECURE_V2"
        self.failed_attempts = 0
        self.max_attempts = 5
        self.shred_on_destruct = False # 默认使用策略 A 冷冻锁死，可通过配置设为 True 触发物理粉碎

    def _derive_layer2_key(self, password: str, salt: bytes) -> bytes:
        """
        基于 Argon2id 或 PBKDF2-HMAC-SHA256 的高强度慢速密钥派生函数（KDF）。
        若输入是 6 位纯数字，首先使用内部 Pepper 进行混合升维。
        """
        # 兼容与升维低熵数字码
        processed_password = password
        if len(password) == 6 and password.isdigit():
            # 使用 Pepper + 盐混合进行前置哈希，升维成高熵输入
            h = hashlib.sha256()
            h.update(password.encode('utf-8'))
            h.update(INTERNAL_PEPPER)
            processed_password = h.hexdigest()

        # 首选 Argon2id (RFC 9106)
        if ARGON2_AVAILABLE:
            try:
                # 极限安全配置：让单次验证耗时接近 300ms ~ 500ms
                # 增加计算和内存开销
                derived = low_level.hash_secret_raw(
                    secret=processed_password.encode('utf-8'),
                    salt=salt,
                    time_cost=4,       # t=4 迭代轮数
                    memory_cost=65536, # m=64MB 内存占用
                    parallelism=2,     # p=2 并行线程
                    hash_len=32,       # 派生 256 位密钥
                    type=low_level.Type.ID
                )
                return derived
            except Exception as e:
                LogManager.log_stealth(f"Argon2id derivation failed: {e}. Falling back to PBKDF2.", level="WARNING")

        # 降级纯 Python 兼容方案 (PBKDF2-HMAC-SHA256, 100,000次迭代)
        return hashlib.pbkdf2_hmac(
            'sha256',
            processed_password.encode('utf-8'),
            salt,
            100000,
            dklen=32
        )

    def encrypt_file(self, file_path: str, password: str) -> str:
        """
        安全升级双重加密核心逻辑：
        - Argon2id/PBKDF2 安全密钥派生
        - 16 字节随机独立 Salt
        - 第一层：AES-256 主密钥随机生成
        - 密钥包装：使用 Layer 2 Key 通过 AES-256-GCM 封装 Layer 1 Key
        - 数据加密：采用 Layer 1 Key 结合 AES-256-GCM 加密，并用 zlib 预压缩
        - 完整打包：包含 Magic + Salt + L2_Wrapped_L1_Key + L1_IV + L1_Tag + Data_IV + Data_Tag + Data
        """
        if len(password) < 6:
            raise ValueError("密码长度不能少于 6 位")

        with open(file_path, 'rb') as f:
            raw_data = f.read()

        # 1. zlib 压缩
        compressed_data = zlib.compress(raw_data)

        # 2. 生成随机 Salt, 派生 Layer 2 Key
        salt = secrets.token_bytes(16)
        layer2_key = self._derive_layer2_key(password, salt)

        # 3. 生成随机 Layer 1 Key
        layer1_key = secrets.token_bytes(32)

        # 4. 用 Layer 2 AES-256-GCM 包装 Layer 1 Key
        l1_nonce = secrets.token_bytes(12)
        l1_wrap_cipher = AES.new(layer2_key, AES.MODE_GCM, nonce=l1_nonce)
        wrapped_layer1_key, l1_tag = l1_wrap_cipher.encrypt_and_digest(layer1_key)

        # 5. 用 Layer 1 AES-256-GCM 加密压缩的数据内容
        data_nonce = secrets.token_bytes(12)
        data_cipher = AES.new(layer1_key, AES.MODE_GCM, nonce=data_nonce)
        ciphertext, data_tag = data_cipher.encrypt_and_digest(compressed_data)

        # 6. 打包保存
        output_path = file_path + ".ble"
        with open(output_path, 'wb') as f:
            # 头部标识
            f.write(self.header_magic)
            # KDF Salt (16B)
            f.write(salt)
            # L1 Key 包装信息 (L1 Nonce 12B + Tag 16B + Wrapped Key 32B)
            f.write(l1_nonce)
            f.write(l1_tag)
            f.write(wrapped_layer1_key)
            # 数据加密辅助信息 (Data Nonce 12B + Data Tag 16B)
            f.write(data_nonce)
            f.write(data_tag)
            # 密文数据
            f.write(ciphertext)

        LogManager.log_stealth(f"Security: File protected with Industrial Dual-Layer (GCM+Argon2id): {file_path}")
        return output_path

    def decrypt_file(self, file_path: str, password: str, output_path: Optional[str] = None) -> str:
        """
        解密核心逻辑：
        - 自动判定 Legacy 2.0 / 3.0。
        - 2.0 格式自动触发无损重加密转换。
        - 3.0 格式采用 AES-256-GCM 严格鉴权解密。
        """
        if len(password) < 6:
            raise ValueError("密码长度不能少于 6 位")

        try:
            with open(file_path, 'rb') as f:
                magic = f.read(16) # 检查 16 字节魔数

            # 兼容性判定与无缝转换迁移逻辑
            if magic == self.legacy_magic:
                LogManager.log_stealth(f"Legacy 2.0 file detected. Migrating securely to 3.0...", level="INFO")
                # 读出 Legacy 数据
                legacy_decoder = LegacyDecryptor(header_magic=self.legacy_magic)
                raw_data = legacy_decoder.decrypt_file_data(file_path, password)

                # 将解密后数据临时重构在安全目录中，用于 3.0 格式重新加密
                fd, temp_plain_path = tempfile.mkstemp()
                try:
                    with os.fdopen(fd, 'wb') as tmp_f:
                        tmp_f.write(raw_data)

                    # 重新用 3.0 格式进行加密，会生成 temp_plain_path.ble
                    new_ble = self.encrypt_file(temp_plain_path, password)

                    # 替换原有的旧 V2 .ble 文件
                    os.replace(new_ble, file_path)
                finally:
                    # 安全擦除临时明文
                    self._secure_shred_file(temp_plain_path)

                # 最终根据用户要求写到 output_path
                if not output_path:
                    output_path = file_path.replace(".ble", "")
                    if output_path == file_path:
                        output_path += ".dec"

                with open(output_path, 'wb') as f_out:
                    f_out.write(raw_data)

                self.failed_attempts = 0
                LogManager.log_stealth(f"Migration Complete: Legacy file converted successfully to 3.0 structure: {file_path}")
                return output_path

            elif magic != self.header_magic:
                raise ValueError("文件格式不匹配或已损坏（不支持的 Magic 头）")

            # 读取 3.0 打包数据
            # 结构: Magic (16B) + Salt (16B) + L1 Nonce (12B) + L1 Tag (16B) + Wrapped Key (32B) + Data Nonce (12B) + Data Tag (16B) + Ciphertext
            with open(file_path, 'rb') as f:
                _ = f.read(16) # Skip magic
                salt = f.read(16)
                l1_nonce = f.read(12)
                l1_tag = f.read(16)
                wrapped_layer1_key = f.read(32)
                data_nonce = f.read(12)
                data_tag = f.read(16)
                ciphertext = f.read()

            # 1. 派生 Layer 2 Key
            layer2_key = self._derive_layer2_key(password, salt)

            # 2. 解包 Layer 1 Key 并严格校验 GCM Integrity
            l1_wrap_cipher = AES.new(layer2_key, AES.MODE_GCM, nonce=l1_nonce)
            layer1_key = l1_wrap_cipher.decrypt_and_verify(wrapped_layer1_key, l1_tag)

            # 3. 解密压缩的数据内容并严格校验 Data Integrity
            data_cipher = AES.new(layer1_key, AES.MODE_GCM, nonce=data_nonce)
            compressed_data = data_cipher.decrypt_and_verify(ciphertext, data_tag)

            # 4. zlib 还原
            raw_data = zlib.decompress(compressed_data)

            if not output_path:
                output_path = file_path.replace(".ble", "")
                if output_path == file_path:
                    output_path += ".dec"

            with open(output_path, 'wb') as f:
                f.write(raw_data)

            self.failed_attempts = 0 # 成功后重置计数
            LogManager.log_stealth(f"Security: File restored with GCM Integrity check: {file_path}")
            return output_path

        except Exception as e:
            self.failed_attempts += 1
            LogManager.log_stealth(f"Security Alert: Failed access ({self.failed_attempts}/{self.max_attempts}) on {file_path}", level="WARNING")
            if self.failed_attempts >= self.max_attempts:
                self.trigger_self_destruct()
            raise e

    def trigger_self_destruct(self):
        """触发自毁机制 (双重策略自毁，支持冷冻锁死与物理级覆盖粉碎)"""
        LogManager.log_stealth("CRITICAL: SELF-DESTRUCT MECHANISM ACTIVATED", level="CRITICAL")
        print("\a" * 3) # 蜂鸣警告
        print("!!! 警告: 连续多次尝试失败，系统已触发安全自毁防御 !!!")

        # 保护范围
        targets = [
            os.path.join("package", "security"),
            os.path.join("data", "user_data"),
            os.path.join("butler", "core")
        ]

        # 获取项目根目录 (兼容 pathlib 结构)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        for rel_path in targets:
            abs_path = os.path.join(project_root, rel_path)
            if not os.path.exists(abs_path): continue

            for root, _, files in os.walk(abs_path):
                for file in files:
                    if file.endswith((".py", ".json", ".txt", ".md", ".db")):
                        file_path = os.path.join(root, file)
                        if self.shred_on_destruct:
                            # 策略 B: 物理级安全粉碎 (覆写 3 次并擦除文件节点)
                            self._secure_shred_file(file_path)
                        else:
                            # 策略 A: 高强度冷冻锁死 (AES-256-GCM 强加密，随机一次性高熵密钥销毁，仅保留密文)
                            self._freeze_lock_file(file_path)

        print("系统已进入强密码自毁模式。数据处于高度密码学冻结状态。")

    def _freeze_lock_file(self, file_path: str):
        """
        策略 A：使用 AES-256-GCM 物理级强加密冷冻文件。
        内存生成随机一次性密钥及 IV 后对文件重写加密，不落盘该密钥，实际上不可复原。
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            # 生成一次性物理高熵随机密钥
            ephemeral_key = secrets.token_bytes(32)
            cipher = AES.new(ephemeral_key, AES.MODE_GCM)
            ciphertext, tag = cipher.encrypt_and_digest(data)
            nonce = cipher.nonce

            # 重构写入
            with open(file_path + ".garbled", 'wb') as f:
                f.write(b"BUTLER_FROZEN_LOCKED")
                f.write(nonce)
                f.write(tag)
                f.write(ciphertext)

            os.remove(file_path)
        except Exception as e:
            LogManager.log_stealth(f"Freeze lock failed on {file_path}: {e}", level="ERROR")

    def _secure_shred_file(self, file_path: str):
        """
        策略 B：物理级安全擦除防取证。
        1. 覆写写零 (Zero-filling)。
        2. 覆写随机高熵噪声数据 (DoD 5220.22-M 模式) 至少 3 遍。
        3. 截断文件，移除节点。
        """
        try:
            if not os.path.exists(file_path):
                return
            file_size = os.path.getsize(file_path)

            with open(file_path, 'r+b') as f:
                # 1. 写零
                f.seek(0)
                f.write(b'\x00' * file_size)
                f.flush()
                os.fsync(f.fileno())

                # 2. 多轮随机噪声写入 (3轮)
                for _ in range(3):
                    f.seek(0)
                    f.write(secrets.token_bytes(file_size))
                    f.flush()
                    os.fsync(f.fileno())

                # 3. 再次全量归零
                f.seek(0)
                f.write(b'\x00' * file_size)
                f.flush()
                os.fsync(f.fileno())

            # 截断文件，彻底移除空间分配
            with open(file_path, 'wb') as f:
                pass

            os.remove(file_path)
        except Exception:
            try:
                os.remove(file_path)
            except Exception:
                pass

def run(file_path: Optional[str] = None):
    """CLI 交互模式入口"""
    print("\n" + "="*50)
    print(" 🔐 Butler Secure Vault - Industrial v3.0 GCM ")
    print("="*50)

    encryptor = DualLayerEncryptor()
    password = getpass.getpass("请输入全局核心加密密码 (至少 6 位): ").strip()
    if len(password) < 6:
        print("错误: 密码长度必须至少为 6 位")
        return
    SecureVault.set_core_code(password)

    # 选项：选择自毁模式
    print("\n自毁防御配置:")
    print("1. 策略 A：强密码冷冻封锁 (高强度不可逆加密，默认)")
    print("2. 策略 B：物理安全粉碎 (DoD 5220.22-M 防取证覆盖擦除)")
    shred_choice = input("请选择自毁模式 (1/2): ").strip()
    if shred_choice == '2':
        encryptor.shred_on_destruct = True
        print("⚠️ 已启用：物理级覆写粉碎自毁机制。")
    else:
        print("已启用：冷冻封锁自毁机制。")

    if file_path and os.path.isfile(file_path):
        print(f"\n当前目标: {file_path}")
        print("1. 执行双重加密 (.ble)")
        print("2. 执行双重解密 (兼容旧版 V2 自动迁移)")
        choice = input("请选择 (1/2): ")
        try:
            if choice == '1':
                out = encryptor.encrypt_file(file_path, password)
                print(f"完成! 加密文件已产出: {out}")
            elif choice == '2':
                out = encryptor.decrypt_file(file_path, password)
                print(f"完成! 文件已还原/迁移成功: {out}")
        except Exception as e:
            print(f"操作失败: {e}")
        return

    while True:
        print("\n1. 加密文件")
        print("2. 解密文件")
        print("0. 退出")
        choice = input("请选择: ")
        if choice == '0': break
        path = input("输入文件路径: ").strip()
        if not os.path.isfile(path):
            print("文件路径无效")
            continue
        try:
            if choice == '1':
                print(f"成功: {encryptor.encrypt_file(path, password)}")
            elif choice == '2':
                print(f"成功: {encryptor.decrypt_file(path, password)}")
        except Exception as e:
            print(f"失败: {e}")

if __name__ == "__main__":
    import getpass
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        run()
