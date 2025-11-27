import os
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2
import hashlib

class SimpleFileEncryptor:
    def __init__(self):
        self.key_file = "encryption_key.bin"
        self.audit_log = "encryption_log.txt"
    
    def log_operation(self, operation, file_path, status):
        """记录操作日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {operation}: {file_path} -> {status}\n"
        
        try:
            with open(self.audit_log, "a") as f:
                f.write(log_entry)
            return True
        except Exception:
            return False
    
    def generate_key(self, password=None):
        """生成或派生加密密钥"""
        try:
            if password:
                # 使用密码派生密钥
                salt = get_random_bytes(16)
                key = PBKDF2(password, salt, dkLen=16, count=100000)
                
                # 保存salt和密钥
                with open(self.key_file, 'wb') as f:
                    f.write(salt + key)
                return key
            else:
                # 生成随机密钥
                key = get_random_bytes(16)
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                return key
        except Exception as e:
            print(f"生成密钥时出错: {str(e)}")
            return None
    
    def load_key(self, password=None):
        """从文件加载密钥"""
        try:
            with open(self.key_file, 'rb') as f:
                key_data = f.read()
                
            if password:
                # 从文件读取salt和密钥
                salt = key_data[:16]
                stored_key = key_data[16:]
                # 重新派生密钥
                derived_key = PBKDF2(password, salt, dkLen=16, count=100000)
                
                # 验证派生密钥是否匹配
                if derived_key == stored_key:
                    return derived_key
                else:
                    print("密码错误，请重试")
                    return None
            else:
                # 直接返回随机密钥
                return key_data
        except FileNotFoundError:
            print("找不到密钥文件")
            return None
        except Exception as e:
            print(f"加载密钥失败: {str(e)}")
            return None
    
    def encrypt_file(self, file_path, key):
        """加密文件"""
        try:
            # 创建加密器
            cipher = AES.new(key, AES.MODE_CBC)
            iv = cipher.iv
            
            # 读取文件内容
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # 加密数据
            ciphertext = cipher.encrypt(pad(data, AES.block_size))
            
            # 写入加密文件
            encrypted_file = file_path + '.enc'
            with open(encrypted_file, 'wb') as f:
                f.write(iv)
                f.write(ciphertext)
            
            # 记录日志
            self.log_operation("加密", file_path, "成功")
            
            print(f"文件加密成功: {encrypted_file}")
            return encrypted_file
        except Exception as e:
            self.log_operation("加密", file_path, f"失败: {str(e)}")
            print(f"加密文件时出错: {str(e)}")
            return None
    
    def decrypt_file(self, file_path, key):
        """解密文件"""
        try:
            # 检查文件扩展名
            if not file_path.endswith('.enc'):
                print("注意: 文件扩展名不是.enc，可能不是加密文件")
            
            # 读取加密文件
            with open(file_path, 'rb') as f:
                iv = f.read(16)  # AES块大小是16字节
                ciphertext = f.read()
            
            # 创建解密器
            cipher = AES.new(key, AES.MODE_CBC, iv)
            
            # 解密数据
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
            
            # 生成解密文件名
            if file_path.endswith('.enc'):
                decrypted_file = file_path[:-4]
            else:
                decrypted_file = file_path + '.dec'
            
            # 避免覆盖已有文件
            if os.path.exists(decrypted_file):
                base, ext = os.path.splitext(decrypted_file)
                counter = 1
                while os.path.exists(f"{base}_{counter}{ext}"):
                    counter += 1
                decrypted_file = f"{base}_{counter}{ext}"
            
            # 写入解密文件
            with open(decrypted_file, 'wb') as f:
                f.write(plaintext)
            
            # 记录日志
            self.log_operation("解密", file_path, "成功")
            
            print(f"文件解密成功: {decrypted_file}")
            return decrypted_file
        except Exception as e:
            self.log_operation("解密", file_path, f"失败: {str(e)}")
            print(f"解密文件时出错: {str(e)}")
            return None

def run(file_path):
    """
    Main function to encrypt or decrypt a file based on its extension.
    """
    if not os.path.isfile(file_path):
        print(f"Error: File not found at '{file_path}'")
        return

    encryptor = SimpleFileEncryptor()
    key = None
    
    # Check if the key file exists
    if not os.path.exists(encryptor.key_file):
        print("No encryption key found. Let's create one.")
        while True:
            password = input("Enter a strong password to protect your key: ").strip()
            if password:
                confirm_password = input("Confirm your password: ").strip()
                if password == confirm_password:
                    key = encryptor.generate_key(password)
                    if key:
                        print("Encryption key created and saved successfully.")
                        break
                    else:
                        print("Failed to generate the key. Please try again.")
                        return
                else:
                    print("Passwords do not match. Please try again.")
            else:
                print("Password cannot be empty.")
    else:
        # Load existing key
        while True:
            password = input("Enter your password to unlock the key: ").strip()
            if not password:
                print("Password cannot be empty.")
                continue
            key = encryptor.load_key(password)
            if key:
                print("Key loaded successfully.")
                break
            else:
                # The load_key method already prints an error, but we can add a retry mechanism
                retry = input("Would you like to try again? (y/n): ").lower()
                if retry != 'y':
                    return

    if not key:
        print("Could not obtain a valid key. Aborting operation.")
        return

    # Determine action based on file extension
    if file_path.endswith('.enc'):
        print(f"Decrypting '{file_path}'...")
        encryptor.decrypt_file(file_path, key)
    else:
        print(f"Encrypting '{file_path}'...")
        encryptor.encrypt_file(file_path, key)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python encrypt.py <file_path>")
    else:
        file_path = sys.argv[1]
        run(file_path)
