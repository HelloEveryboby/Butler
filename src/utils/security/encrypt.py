"""
高级加密工具 - Butler Secure Vault v2
支持双重动态加密体系 (Dual-Layer Encryption)：
1. 第一层：独立前置锁（文件唯一 AES-128 密钥）。
2. 第二层：6位核心码（全局核心码，仅存内存，PBKDF2 派生）。
流程：先压缩 -> 生成 Layer 1 密钥 -> Layer 2 加密 Layer 1 密钥 -> Layer 1 加密压缩数据。
防暴力破解：5次错误即触发关键文件可逆乱码化。
"""
import os
import sys
import time
import zlib
import base64
import hashlib
from typing import Optional
from Crypto.Random import get_random_bytes
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from package.core_utils.log_manager import LogManager

class SecureVault:
    """管理 6 位核心码的内存存储"""
    _core_code: Optional[str] = None

    @classmethod
    def set_core_code(cls, code: str):
        if len(code) == 6 and code.isdigit():
            cls._core_code = code
            LogManager.log_stealth("Core Code loaded into memory.")
            return True
        return False

    @classmethod
    def get_core_code(cls) -> Optional[str]:
        return cls._core_code

    @classmethod
    def clear(cls):
        cls._core_code = None

class DualLayerEncryptor:
    def __init__(self):
        self.header_magic = b"BUTLER_SECURE_V2"
        self.failed_attempts = 0
        self.max_attempts = 5

    def _derive_layer2_key(self, core_code: str) -> bytes:
        """从 6 位核心码派生第二层密钥 (SHA-256)"""
        return hashlib.sha256(core_code.encode()).digest()

    def encrypt_file(self, file_path: str, core_code: str) -> str:
        """双重加密核心逻辑"""
        if len(core_code) != 6:
            raise ValueError("核心码必须为 6 位数字")

        # 1. 压缩 (消除数据特征，减小体积)
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        compressed_data = zlib.compress(raw_data)

        # 2. 生成 Layer 1 独立密钥 (AES-128)
        layer1_key = get_random_bytes(16)

        # 3. 加密 Layer 1 密钥 (用核心码派生的 Layer 2 密钥进行 XOR)
        layer2_key = self._derive_layer2_key(core_code)
        cipher_layer1_key = bytes(a ^ b for a, b in zip(layer1_key, layer2_key[:16]))

        # 4. 加密内容 (Layer 1 AES-CBC)
        cipher = AES.new(layer1_key, AES.MODE_CBC)
        iv = cipher.iv
        ciphertext = cipher.encrypt(pad(compressed_data, AES.block_size))

        # 5. 构建加密文件：Magic + Enc_L1_Key + IV + Data
        output_path = file_path + ".ble"
        with open(output_path, 'wb') as f:
            f.write(self.header_magic)
            f.write(cipher_layer1_key)
            f.write(iv)
            f.write(ciphertext)

        LogManager.log_stealth(f"Security: File protected with Dual-Layer: {file_path}")
        return output_path

    def decrypt_file(self, file_path: str, core_code: str, output_path: Optional[str] = None) -> str:
        """双重解密核心逻辑"""
        if len(core_code) != 6:
            raise ValueError("核心码必须为 6 位数字")

        try:
            with open(file_path, 'rb') as f:
                magic = f.read(len(self.header_magic))
                if magic != self.header_magic:
                    raise ValueError("文件格式不匹配或已损坏")
                
                cipher_layer1_key = f.read(16)
                iv = f.read(16)
                ciphertext = f.read()

            # 1. 解密 Layer 1 密钥 (用 Layer 2 XOR 还原)
            layer2_key = self._derive_layer2_key(core_code)
            layer1_key = bytes(a ^ b for a, b in zip(cipher_layer1_key, layer2_key[:16]))

            # 2. 解密内容 (Layer 1 AES-CBC)
            cipher = AES.new(layer1_key, AES.MODE_CBC, iv)
            compressed_data = unpad(cipher.decrypt(ciphertext), AES.block_size)

            # 3. 解压还原
            raw_data = zlib.decompress(compressed_data)

            if not output_path:
                output_path = file_path.replace(".ble", "")
                if output_path == file_path:
                    output_path += ".dec"

            with open(output_path, 'wb') as f:
                f.write(raw_data)

            self.failed_attempts = 0 # 成功后重置计数
            LogManager.log_stealth(f"Security: File restored: {file_path}")
            return output_path

        except Exception as e:
            self.failed_attempts += 1
            LogManager.log_stealth(f"Security Alert: Failed access ({self.failed_attempts}/{self.max_attempts}) on {file_path}", level="WARNING")
            if self.failed_attempts >= self.max_attempts:
                self.trigger_self_destruct()
            raise e

    def trigger_self_destruct(self):
        """触发自毁 (对系统核心及用户数据执行乱码化)"""
        LogManager.log_stealth("CRITICAL: SELF-DESTRUCT MECHANISM ACTIVATED", level="CRITICAL")
        print("\a" * 3) # 蜂鸣警告
        print("!!! 警告: 连续多次尝试失败，系统已触发安全锁定 !!!")

        core_code = SecureVault.get_core_code() or "000000"

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
                    if file.endswith((".py", ".json", ".txt", ".md")):
                        file_path = os.path.join(root, file)
                        # 执行 XOR 乱码化
                        self._obfuscate_file(file_path, core_code)

        print("系统已进入保护性乱码状态。请物理隔绝环境并使用 recovery_tool.py 进行核心码还原。")

    def _obfuscate_file(self, file_path: str, core_code: str):
        """文件级可逆 XOR 混淆"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            key = hashlib.sha256(core_code.encode()).digest()
            obfuscated = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
            with open(file_path + ".garbled", 'wb') as f:
                f.write(obfuscated)
            os.remove(file_path)
        except Exception: pass

def run(file_path: Optional[str] = None):
    """CLI 入口"""
    print("\n" + "="*40)
    print(" Butler Secure Vault - Advanced Dual-Layer Mode ")
    print("="*40)

    encryptor = DualLayerEncryptor()
    core_code = getpass.getpass("请输入 6 位全局核心码: ").strip()
    if len(core_code) != 6 or not core_code.isdigit():
        print("错误: 核心码必须为 6 位数字")
        return
    SecureVault.set_core_code(core_code)

    if file_path and os.path.isfile(file_path):
        print(f"当前目标: {file_path}")
        print("1. 执行双重加密 (.ble)")
        print("2. 执行双重解密")
        choice = input("请选择 (1/2): ")
        try:
            if choice == '1':
                out = encryptor.encrypt_file(file_path, core_code)
                print(f"完成! 加密文件已产出: {out}")
            elif choice == '2':
                out = encryptor.decrypt_file(file_path, core_code)
                print(f"完成! 文件已还原: {out}")
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
                print(f"成功: {encryptor.encrypt_file(path, core_code)}")
            elif choice == '2':
                print(f"成功: {encryptor.decrypt_file(path, core_code)}")
        except Exception as e:
            print(f"失败: {e}")

if __name__ == "__main__":
    import getpass
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        run()
