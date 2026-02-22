import os
import base64
from Crypto.Cipher import AES, DES, PKCS1_OAEP
from Crypto.PublicKey import RSA, ECC
from Crypto.Signature import pkcs1_15, DSS
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2

class SymmetricCrypto:
    """对称加密/解密类，支持 AES 和 DES，并具备流处理能力。"""

    @staticmethod
    def derive_key(password, salt, algorithm='AES'):
        """从密码和盐中派生密钥。"""
        dk_len = 16 if algorithm.upper() == 'AES' else 8
        return PBKDF2(password, salt, dkLen=dk_len, count=100000)

    @staticmethod
    def encrypt_data(data, key, algorithm='AES'):
        """加密字符串或字节数据。"""
        if isinstance(data, str):
            data = data.encode('utf-8')

        alg = algorithm.upper()
        if alg == 'AES':
            cipher = AES.new(key, AES.MODE_CBC)
            block_size = AES.block_size
        elif alg == 'DES':
            cipher = DES.new(key, DES.MODE_CBC)
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        ct_bytes = cipher.encrypt(pad(data, block_size))
        iv = base64.b64encode(cipher.iv).decode('utf-8')
        ct = base64.b64encode(ct_bytes).decode('utf-8')
        return iv, ct

    @staticmethod
    def decrypt_data(iv_b64, ct_b64, key, algorithm='AES'):
        """解密字符串数据。"""
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(ct_b64)

        alg = algorithm.upper()
        if alg == 'AES':
            cipher = AES.new(key, AES.MODE_CBC, iv)
            block_size = AES.block_size
        elif alg == 'DES':
            cipher = DES.new(key, DES.MODE_CBC, iv)
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        pt = unpad(cipher.decrypt(ct), block_size)
        return pt.decode('utf-8')

    @staticmethod
    def encrypt_file(input_file, output_file, key, algorithm='AES'):
        """使用流处理方式加密文件，以支持大文件。"""
        alg = algorithm.upper()
        if alg == 'AES':
            cipher = AES.new(key, AES.MODE_CBC)
            block_size = AES.block_size
        elif alg == 'DES':
            cipher = DES.new(key, DES.MODE_CBC)
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        chunk_size = 1024 * block_size
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            f_out.write(cipher.iv)
            while True:
                chunk = f_in.read(chunk_size)
                if len(chunk) < chunk_size:
                    # 最后一块，应用填充
                    f_out.write(cipher.encrypt(pad(chunk, block_size)))
                    break
                f_out.write(cipher.encrypt(chunk))
        return output_file

    @staticmethod
    def decrypt_file(input_file, output_file, key, algorithm='AES'):
        """使用流处理方式解密文件。"""
        alg = algorithm.upper()
        if alg == 'AES':
            iv_size = AES.block_size
            block_size = AES.block_size
        elif alg == 'DES':
            iv_size = DES.block_size
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        chunk_size = 1024 * block_size
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            iv = f_in.read(iv_size)
            if alg == 'AES':
                cipher = AES.new(key, AES.MODE_CBC, iv)
            else:
                cipher = DES.new(key, DES.MODE_CBC, iv)

            # 使用预读缓冲区来识别最后一块以便取消填充
            current_chunk = f_in.read(chunk_size)
            while True:
                next_chunk = f_in.read(chunk_size)
                if not next_chunk:
                    # current_chunk 是最后一块
                    f_out.write(unpad(cipher.decrypt(current_chunk), block_size))
                    break
                f_out.write(cipher.decrypt(current_chunk))
                current_chunk = next_chunk
        return output_file

class AsymmetricCrypto:
    """非对称加密和签名类，支持 RSA 和 ECC。"""

    # RSA 部分
    @staticmethod
    def rsa_generate_keypair(bits=2048):
        """生成 RSA 密钥对。"""
        key = RSA.generate(bits)
        return key.export_key(), key.publickey().export_key()

    @staticmethod
    def rsa_encrypt(data, public_key):
        """使用 RSA 公钥加密数据。"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        recipient_key = RSA.import_key(public_key)
        cipher_rsa = PKCS1_OAEP.new(recipient_key)
        enc_data = cipher_rsa.encrypt(data)
        return base64.b64encode(enc_data).decode('utf-8')

    @staticmethod
    def rsa_decrypt(enc_data_b64, private_key):
        """使用 RSA 私钥解密数据。"""
        enc_data = base64.b64decode(enc_data_b64)
        key = RSA.import_key(private_key)
        cipher_rsa = PKCS1_OAEP.new(key)
        data = cipher_rsa.decrypt(enc_data)
        return data.decode('utf-8')

    @staticmethod
    def rsa_sign(data, private_key):
        """使用 RSA 私钥对数据进行签名。"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        key = RSA.import_key(private_key)
        h = SHA256.new(data)
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def rsa_verify(data, signature_b64, public_key):
        """使用 RSA 公钥验证签名。"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        signature = base64.b64decode(signature_b64)
        key = RSA.import_key(public_key)
        h = SHA256.new(data)
        try:
            pkcs1_15.new(key).verify(h, signature)
            return True
        except (ValueError, TypeError):
            return False

    # ECC 部分
    @staticmethod
    def ecc_generate_keypair(curve='P-256'):
        """生成 ECC 密钥对。"""
        key = ECC.generate(curve=curve)
        return key.export_key(format='PEM'), key.public_key().export_key(format='PEM')

    @staticmethod
    def ecc_sign(data, private_key):
        """使用 ECC 私钥对数据进行签名。"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        key = ECC.import_key(private_key)
        h = SHA256.new(data)
        signer = DSS.new(key, 'fips-186-3')
        signature = signer.sign(h)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def ecc_verify(data, signature_b64, public_key):
        """使用 ECC 公钥验证签名。"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        signature = base64.b64decode(signature_b64)
        key = ECC.import_key(public_key)
        h = SHA256.new(data)
        verifier = DSS.new(key, 'fips-186-3')
        try:
            verifier.verify(h, signature)
            return True
        except (ValueError, TypeError):
            return False
