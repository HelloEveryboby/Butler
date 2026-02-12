"""
对称加密工具，支持 AES 和 DES 算法。
支持文件加密/解密以及字符串加密/解密。
"""
import os
import time
import sys
import base64
import getpass
import hashlib
from package.crypto_core import SymmetricCrypto
from Crypto.Random import get_random_bytes

class EnhancedEncryptor:
    def __init__(self):
        self.key_file_aes = "encryption_key_aes.bin"
        self.key_file_des = "encryption_key_des.bin"
        self.audit_log = "encryption_log.txt"
    
    def log_operation(self, operation, target, status):
        """记录操作日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {operation}: {target} -> {status}\n"
        try:
            with open(self.audit_log, "a", encoding='utf-8') as f:
                f.write(log_entry)
        except Exception:
            pass

    def get_key(self, algorithm='AES'):
        algorithm = algorithm.upper()
        key_file = self.key_file_aes if algorithm == 'AES' else self.key_file_des
        if not os.path.exists(key_file):
            print(f"未找到 {algorithm} 密钥配置。正在创建...")
            password = getpass.getpass(f"输入用于派生 {algorithm} 密钥的密码: ").strip()
            if not password:
                print("密码不能为空。")
                return None
            salt = get_random_bytes(16)
            key = SymmetricCrypto.derive_key(password, salt, algorithm)

            # 安全改进：不直接存储密钥，仅存储盐和密钥哈希作为验证器
            verifier = hashlib.sha256(key).digest()
            with open(key_file, 'wb') as f:
                f.write(salt + verifier)
            print(f"{algorithm} 密钥配置已创建。")
            return key
        else:
            password = getpass.getpass(f"输入密码以解锁 {algorithm} 密钥: ").strip()
            if not password:
                return None
            try:
                with open(key_file, 'rb') as f:
                    data = f.read()
                    salt = data[:16]
                    stored_verifier = data[16:]
                    key = SymmetricCrypto.derive_key(password, salt, algorithm)
                    # 验证派生密钥是否正确
                    if hashlib.sha256(key).digest() == stored_verifier:
                        return key
                    else:
                        print("密码错误。")
                        return None
            except Exception as e:
                print(f"加载密钥失败: {e}")
                return None

    def handle_file(self, file_path, algorithm='AES', mode='encrypt'):
        key = self.get_key(algorithm)
        if not key: return

        try:
            if mode == 'encrypt':
                output_file = file_path + ".enc"
                SymmetricCrypto.encrypt_file(file_path, output_file, key, algorithm)
                print(f"文件已加密: {output_file}")
                self.log_operation(f"{algorithm}加密文件", file_path, "成功")
            else:
                if file_path.endswith('.enc'):
                    output_file = file_path[:-4]
                else:
                    output_file = file_path + ".dec"
                
                # Avoid overwriting
                if os.path.exists(output_file):
                    base, ext = os.path.splitext(output_file)
                    output_file = f"{base}_{int(time.time())}{ext}"
                
                SymmetricCrypto.decrypt_file(file_path, output_file, key, algorithm)
                print(f"文件已解密: {output_file}")
                self.log_operation(f"{algorithm}解密文件", file_path, "成功")
        except Exception as e:
            print(f"操作失败: {e}")
            self.log_operation(f"{algorithm}{mode}文件", file_path, f"失败: {e}")

    def handle_string(self, algorithm='AES', mode='encrypt'):
        key = self.get_key(algorithm)
        if not key: return

        if mode == 'encrypt':
            data = input("请输入要加密的字符串: ")
            iv, ct = SymmetricCrypto.encrypt_data(data, key, algorithm)
            print(f"IV (Base64): {iv}")
            print(f"密文 (Base64): {ct}")
            print(f"组合结果: {iv}:{ct}")
            self.log_operation(f"{algorithm}加密字符串", "文本数据", "成功")
        else:
            combined = input("请输入组合结果 (IV:密文): ")
            try:
                iv, ct = combined.split(':')
                pt = SymmetricCrypto.decrypt_data(iv, ct, key, algorithm)
                print(f"解密结果: {pt}")
                self.log_operation(f"{algorithm}解密字符串", "文本数据", "成功")
            except Exception as e:
                print(f"解密失败: {e}")
                self.log_operation(f"{algorithm}解密字符串", "文本数据", f"失败: {e}")

def run(file_path=None):
    encryptor = EnhancedEncryptor()
    if file_path and os.path.isfile(file_path):
        print(f"检测到文件: {file_path}")
        print("1. AES 加密")
        print("2. AES 解密")
        print("3. DES 加密")
        print("4. DES 解密")
        choice = input("请选择操作 (1-4): ")
        if choice == '1': encryptor.handle_file(file_path, 'AES', 'encrypt')
        elif choice == '2': encryptor.handle_file(file_path, 'AES', 'decrypt')
        elif choice == '3': encryptor.handle_file(file_path, 'DES', 'encrypt')
        elif choice == '4': encryptor.handle_file(file_path, 'DES', 'decrypt')
        return

    while True:
        print("\n=== 对称加密工具 (AES/DES) ===")
        print("1. AES 加密文件")
        print("2. AES 解密文件")
        print("3. DES 加密文件")
        print("4. DES 解密文件")
        print("5. AES 加密字符串")
        print("6. AES 解密字符串")
        print("7. DES 加密字符串")
        print("8. DES 解密字符串")
        print("0. 返回/退出")

        choice = input("请选择操作: ")
        if choice == '0': break
        elif choice == '1':
            path = input("输入文件路径: ")
            if os.path.isfile(path): encryptor.handle_file(path, 'AES', 'encrypt')
            else: print("文件不存在。")
        elif choice == '2':
            path = input("输入文件路径: ")
            if os.path.isfile(path): encryptor.handle_file(path, 'AES', 'decrypt')
            else: print("文件不存在。")
        elif choice == '3':
            path = input("输入文件路径: ")
            if os.path.isfile(path): encryptor.handle_file(path, 'DES', 'encrypt')
            else: print("文件不存在。")
        elif choice == '4':
            path = input("输入文件路径: ")
            if os.path.isfile(path): encryptor.handle_file(path, 'DES', 'decrypt')
            else: print("文件不存在。")
        elif choice == '5': encryptor.handle_string('AES', 'encrypt')
        elif choice == '6': encryptor.handle_string('AES', 'decrypt')
        elif choice == '7': encryptor.handle_string('DES', 'encrypt')
        elif choice == '8': encryptor.handle_string('DES', 'decrypt')
        else: print("无效选择。")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        run()
