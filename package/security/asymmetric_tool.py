"""
非对称加密工具，支持 RSA 和 ECC 算法。
支持 RSA 加密/解密、签名/验证，以及 ECC 签名/验证。
"""
import os
import sys
from package.crypto_core import AsymmetricCrypto

class AsymmetricTool:
    def __init__(self):
        self.rsa_private_file = "rsa_private.pem"
        self.rsa_public_file = "rsa_public.pem"
        self.ecc_private_file = "ecc_private.pem"
        self.ecc_public_file = "ecc_public.pem"

    def ensure_rsa_keys(self):
        if not os.path.exists(self.rsa_private_file):
            print("未找到 RSA 密钥。正在生成 2048 位密钥对...")
            priv, pub = AsymmetricCrypto.rsa_generate_keypair()
            with open(self.rsa_private_file, 'wb') as f: f.write(priv)
            with open(self.rsa_public_file, 'wb') as f: f.write(pub)
            print("RSA 密钥对已生成。")

        with open(self.rsa_private_file, 'rb') as f: priv = f.read()
        with open(self.rsa_public_file, 'rb') as f: pub = f.read()
        return priv, pub

    def ensure_ecc_keys(self):
        if not os.path.exists(self.ecc_private_file):
            print("未找到 ECC 密钥。正在生成 P-256 密钥对...")
            priv, pub = AsymmetricCrypto.ecc_generate_keypair()
            with open(self.ecc_private_file, 'wb') as f: f.write(priv)
            with open(self.ecc_public_file, 'wb') as f: f.write(pub)
            print("ECC 密钥对已生成。")

        with open(self.ecc_private_file, 'rb') as f: priv = f.read()
        with open(self.ecc_public_file, 'rb') as f: pub = f.read()
        return priv, pub

    def run_rsa(self):
        priv, pub = self.ensure_rsa_keys()
        while True:
            print("\n--- RSA 操作 ---")
            print("1. 加密字符串 (使用公钥)")
            print("2. 解密字符串 (使用私钥)")
            print("3. 签名字符串 (使用私钥)")
            print("4. 验证签名 (使用公钥)")
            print("0. 返回")
            choice = input("请选择: ")

            if choice == '0': break
            elif choice == '1':
                data = input("输入要加密的文本: ")
                try:
                    enc = AsymmetricCrypto.rsa_encrypt(data, pub)
                    print(f"密文 (Base64): {enc}")
                except Exception as e: print(f"加密失败: {e}")
            elif choice == '2':
                enc = input("输入密文 (Base64): ")
                try:
                    dec = AsymmetricCrypto.rsa_decrypt(enc, priv)
                    print(f"解密结果: {dec}")
                except Exception as e: print(f"解密失败: {e}")
            elif choice == '3':
                data = input("输入要签名的文本: ")
                try:
                    sig = AsymmetricCrypto.rsa_sign(data, priv)
                    print(f"签名 (Base64): {sig}")
                except Exception as e: print(f"签名失败: {e}")
            elif choice == '4':
                data = input("输入原始文本: ")
                sig = input("输入签名 (Base64): ")
                try:
                    valid = AsymmetricCrypto.rsa_verify(data, sig, pub)
                    print("验证结果: " + ("有效" if valid else "无效"))
                except Exception as e: print(f"验证失败: {e}")

    def run_ecc(self):
        priv, pub = self.ensure_ecc_keys()
        while True:
            print("\n--- ECC 操作 (仅支持签名/验证) ---")
            print("1. 签名字符串 (使用私钥)")
            print("2. 验证签名 (使用公钥)")
            print("0. 返回")
            choice = input("请选择: ")

            if choice == '0': break
            elif choice == '1':
                data = input("输入要签名的文本: ")
                try:
                    sig = AsymmetricCrypto.ecc_sign(data, priv)
                    print(f"签名 (Base64): {sig}")
                except Exception as e: print(f"签名失败: {e}")
            elif choice == '2':
                data = input("输入原始文本: ")
                sig = input("输入签名 (Base64): ")
                try:
                    valid = AsymmetricCrypto.ecc_verify(data, sig, pub)
                    print("验证结果: " + ("有效" if valid else "无效"))
                except Exception as e: print(f"验证失败: {e}")

def run():
    tool = AsymmetricTool()
    while True:
        print("\n=== 非对称加密工具 (RSA/ECC) ===")
        print("1. RSA 操作")
        print("2. ECC 操作")
        print("0. 退出")
        choice = input("请选择: ")
        if choice == '0': break
        elif choice == '1': tool.run_rsa()
        elif choice == '2': tool.run_ecc()

if __name__ == "__main__":
    run()
