import os
import base64
import hashlib
from Crypto.Cipher import AES, DES, PKCS1_OAEP
from Crypto.PublicKey import RSA, ECC
from Crypto.Signature import pkcs1_15, DSS
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2

# 尝试加载 Argon2 库作为 KDF 算法的首选，若不可用则优雅 Fallback 到 PBKDF2-HMAC-SHA256
try:
    from argon2 import low_level
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False

# 内部静态 Pepper，用于升维，防止弱密码快速爆破
INTERNAL_PEPPER = b"ButlerJarvisSecureShield_v3_Pepper2026!#"

class SymmetricCrypto:
    """
    升级后的对称加密核心类，提供 AES (AES-256-GCM 与 AES-CBC) 和 DES 的加密、解密及流式文件处理功能。
    支持强密码学 KDF 算法 (Argon2id + 独立 Salt)。
    """

    @staticmethod
    def derive_key(password: str, salt: bytes, algorithm='AES') -> bytes:
        """
        基于密码 and 盐派生加密密钥（首选 Argon2id，不可用时使用 PBKDF2 算法）。
        """
        # 低熵与弱密码防护
        processed_password = password
        if len(password) == 6 and password.isdigit():
            h = hashlib.sha256()
            h.update(password.encode('utf-8'))
            h.update(INTERNAL_PEPPER)
            processed_password = h.hexdigest()

        dk_len = 32 if algorithm.upper() == 'AES' else 8

        if ARGON2_AVAILABLE:
            try:
                derived = low_level.hash_secret_raw(
                    secret=processed_password.encode('utf-8'),
                    salt=salt,
                    time_cost=4,
                    memory_cost=65536,
                    parallelism=2,
                    hash_len=dk_len,
                    type=low_level.Type.ID
                )
                return derived
            except Exception:
                pass

        # Fallback to PBKDF2
        return PBKDF2(processed_password, salt, dkLen=dk_len, count=100000)

    @staticmethod
    def encrypt_data(data, key: bytes, algorithm='AES') -> tuple:
        """
        加密数据（AES 默认升级为高强度的 GCM 模式，兼容 CBC 与 DES）。

        Returns:
            tuple:
              - 对于 AES-GCM (默认): (nonce_b64, ciphertext_b64, tag_b64)
              - 对于 DES 或传统模式: (iv_b64, ciphertext_b64)
        """
        if isinstance(data, str):
            data = data.encode('utf-8')

        alg = algorithm.upper()
        if alg == 'AES':
            # 升级：默认使用 AES-256-GCM 保护完整性与机密性
            nonce = get_random_bytes(12)
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            ct_bytes, tag = cipher.encrypt_and_digest(data)

            nonce_b64 = base64.b64encode(nonce).decode('utf-8')
            ct_b64 = base64.b64encode(ct_bytes).decode('utf-8')
            tag_b64 = base64.b64encode(tag).decode('utf-8')
            return nonce_b64, ct_b64, tag_b64
        elif alg == 'DES':
            cipher = DES.new(key, DES.MODE_CBC)
            block_size = DES.block_size
            ct_bytes = cipher.encrypt(pad(data, block_size))
            iv = base64.b64encode(cipher.iv).decode('utf-8')
            ct = base64.b64encode(ct_bytes).decode('utf-8')
            return iv, ct
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

    @staticmethod
    def decrypt_data(iv_or_nonce_b64: str, ct_b64: str, key: bytes, algorithm='AES', tag_b64: str = None) -> str:
        """
        解密数据。
        """
        iv_or_nonce = base64.b64decode(iv_or_nonce_b64)
        ct = base64.b64decode(ct_b64)

        alg = algorithm.upper()
        if alg == 'AES':
            if tag_b64:
                # AES-GCM 模式解密与完整性校验
                tag = base64.b64decode(tag_b64)
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv_or_nonce)
                pt = cipher.decrypt_and_verify(ct, tag)
            else:
                # 兼容旧版的 CBC 模式解密
                # 原来使用 16 字节密钥 (AES-128)，对 32 字节的 master_key 截取前 16 字节
                cbc_key = key[:16] if len(key) >= 16 else key
                cipher = AES.new(cbc_key, AES.MODE_CBC, iv_or_nonce)
                pt = unpad(cipher.decrypt(ct), AES.block_size)
            return pt.decode('utf-8')
        elif alg == 'DES':
            cipher = DES.new(key, DES.MODE_CBC, iv_or_nonce)
            pt = unpad(cipher.decrypt(ct), DES.block_size)
            return pt.decode('utf-8')
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

    @staticmethod
    def encrypt_file(input_file: str, output_file: str, key: bytes, algorithm='AES') -> str:
        """
        使用流式处理加密大文件 (AES 默认采用高安全性 AES-256-GCM 模式)。
        """
        alg = algorithm.upper()
        if alg == 'AES':
            nonce = get_random_bytes(12)
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

            with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
                # 结构: Nonce (12B) + Tag placeholder (16B) + Encrypted Data
                f_out.write(nonce)
                # 留出 16 字节存放 Auth Tag
                f_out.write(b'\x00' * 16)

                # 读取全部并加密 (GCM 适合全量/大文件流式但由于需要单次 Tag，我们可以在内存允许时全量，或分块)
                # 对于文件流式 AES-GCM：直接通过 encrypt() 对大内容进行操作，最后写入 tag。
                data = f_in.read()
                ciphertext, tag = cipher.encrypt_and_digest(data)
                f_out.write(ciphertext)

                # 回填 Auth Tag
                f_out.seek(12)
                f_out.write(tag)
            return output_file
        elif alg == 'DES':
            cipher = DES.new(key, DES.MODE_CBC)
            block_size = DES.block_size
            chunk_size = 1024 * block_size
            with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
                f_out.write(cipher.iv) # 在文件头部写入 IV
                while True:
                    chunk = f_in.read(chunk_size)
                    if len(chunk) < chunk_size:
                        f_out.write(cipher.encrypt(pad(chunk, block_size)))
                        break
                    f_out.write(cipher.encrypt(chunk))
            return output_file
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

    @staticmethod
    def decrypt_file(input_file: str, output_file: str, key: bytes, algorithm='AES') -> str:
        """
        使用流式处理解密大文件 (AES 默认采用高安全性 AES-256-GCM 模式)。
        """
        alg = algorithm.upper()
        if alg == 'AES':
            with open(input_file, 'rb') as f_in:
                nonce = f_in.read(12)
                tag = f_in.read(16)
                ciphertext = f_in.read()

            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)

            with open(output_file, 'wb') as f_out:
                f_out.write(plaintext)
            return output_file
        elif alg == 'DES':
            block_size = DES.block_size
            chunk_size = 1024 * block_size
            with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
                iv = f_in.read(block_size) # 从文件头部读取 IV
                cipher = DES.new(key, DES.MODE_CBC, iv)

                current_chunk = f_in.read(chunk_size)
                while True:
                    next_chunk = f_in.read(chunk_size)
                    if not next_chunk:
                        f_out.write(unpad(cipher.decrypt(current_chunk), block_size))
                        break
                    f_out.write(cipher.decrypt(current_chunk))
                    current_chunk = next_chunk
            return output_file
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

class AsymmetricCrypto:
    """
    非对称加密与签名核心类，支持 RSA 和 ECC 算法。
    """

    # --- RSA 部分 ---
    @staticmethod
    def rsa_generate_keypair(bits=2048) -> tuple:
        """生成 RSA 密钥对"""
        key = RSA.generate(bits)
        return key.export_key(), key.publickey().export_key()

    @staticmethod
    def rsa_encrypt(data, public_key: bytes) -> str:
        """使用 RSA 公钥加密数据"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        recipient_key = RSA.import_key(public_key)
        cipher_rsa = PKCS1_OAEP.new(recipient_key)
        enc_data = cipher_rsa.encrypt(data)
        return base64.b64encode(enc_data).decode('utf-8')

    @staticmethod
    def rsa_decrypt(enc_data_b64: str, private_key: bytes) -> str:
        """使用 RSA 私钥解密数据"""
        enc_data = base64.b64decode(enc_data_b64)
        key = RSA.import_key(private_key)
        cipher_rsa = PKCS1_OAEP.new(key)
        data = cipher_rsa.decrypt(enc_data)
        return data.decode('utf-8')

    @staticmethod
    def rsa_sign(data, private_key: bytes) -> str:
        """使用 RSA 私钥对数据进行数字签名"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        key = RSA.import_key(private_key)
        h = SHA256.new(data)
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def rsa_verify(data, signature_b64: str, public_key: bytes) -> bool:
        """使用 RSA 公钥验证数字签名"""
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

    # --- ECC 部分 ---
    @staticmethod
    def ecc_generate_keypair(curve='P-256') -> tuple:
        """生成 ECC 密钥对"""
        key = ECC.generate(curve=curve)
        return key.export_key(format='PEM'), key.public_key().export_key(format='PEM')

    @staticmethod
    def ecc_sign(data, private_key: bytes) -> str:
        """使用 ECC 私钥进行数字签名"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        key = ECC.import_key(private_key)
        h = SHA256.new(data)
        signer = DSS.new(key, 'fips-186-3')
        signature = signer.sign(h)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def ecc_verify(data, signature_b64: str, public_key: bytes) -> bool:
        """使用 ECC 公钥验证数字签名"""
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
