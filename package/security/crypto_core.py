import base64
from Crypto.Cipher import AES, DES, PKCS1_OAEP
from Crypto.PublicKey import RSA, ECC
from Crypto.Signature import pkcs1_15, DSS
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad, unpad
from Crypto.Protocol.KDF import PBKDF2


class SymmetricCrypto:
    """
    对称加密核心类，提供 AES 和 DES 的加密、解密及流式文件处理功能。

    支持模式：
    - CBC (Cipher Block Chaining)
    - PKCS7 填充 (Padding)
    - 自动密钥派生 (PBKDF2)
    """

    @staticmethod
    def derive_key(password: str, salt: bytes, algorithm="AES") -> bytes:
        """
        基于密码和盐派生加密密钥（使用 PBKDF2 算法）。

        Args:
            password: 用户输入的原始密码。
            salt: 随机盐值。
            algorithm: 目标算法 ('AES' 或 'DES')。

        Returns:
            bytes: 派生出的固定长度密钥。
        """
        dk_len = 16 if algorithm.upper() == "AES" else 8
        return PBKDF2(password, salt, dkLen=dk_len, count=100000)

    @staticmethod
    def encrypt_data(data, key: bytes, algorithm="AES") -> tuple:
        """
        加密字符串或字节数据。

        Args:
            data: 要加密的数据 (str 或 bytes)。
            key: 加密密钥。
            algorithm: 算法 ('AES' 或 'DES')。

        Returns:
            tuple: (iv_b64, ciphertext_b64) 均为 Base64 编码的字符串。
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        alg = algorithm.upper()
        if alg == "AES":
            cipher = AES.new(key, AES.MODE_CBC)
            block_size = AES.block_size
        elif alg == "DES":
            cipher = DES.new(key, DES.MODE_CBC)
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        ct_bytes = cipher.encrypt(pad(data, block_size))
        iv = base64.b64encode(cipher.iv).decode("utf-8")
        ct = base64.b64encode(ct_bytes).decode("utf-8")
        return iv, ct

    @staticmethod
    def decrypt_data(iv_b64: str, ct_b64: str, key: bytes, algorithm="AES") -> str:
        """
        解密 Base64 格式的加密数据。

        Args:
            iv_b64: Base64 编码的初始化向量。
            ct_b64: Base64 编码的密文。
            key: 解密密钥。
            algorithm: 算法 ('AES' 或 'DES')。

        Returns:
            str: 解密后的原始字符串。
        """
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(ct_b64)

        alg = algorithm.upper()
        if alg == "AES":
            cipher = AES.new(key, AES.MODE_CBC, iv)
            block_size = AES.block_size
        elif alg == "DES":
            cipher = DES.new(key, DES.MODE_CBC, iv)
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        pt = unpad(cipher.decrypt(ct), block_size)
        return pt.decode("utf-8")

    @staticmethod
    def encrypt_file(
        input_file: str, output_file: str, key: bytes, algorithm="AES"
    ) -> str:
        """
        使用流式处理加密大文件。

        Args:
            input_file: 源文件路径。
            output_file: 加密后的目标文件路径。
            key: 加密密钥。
            algorithm: 算法 ('AES' 或 'DES')。

        Returns:
            str: 目标文件路径。
        """
        alg = algorithm.upper()
        if alg == "AES":
            cipher = AES.new(key, AES.MODE_CBC)
            block_size = AES.block_size
        elif alg == "DES":
            cipher = DES.new(key, DES.MODE_CBC)
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        chunk_size = 1024 * block_size
        with open(input_file, "rb") as f_in, open(output_file, "wb") as f_out:
            f_out.write(cipher.iv)  # 在文件头部写入 IV
            while True:
                chunk = f_in.read(chunk_size)
                if len(chunk) < chunk_size:
                    # 最后一块数据，进行填充
                    f_out.write(cipher.encrypt(pad(chunk, block_size)))
                    break
                f_out.write(cipher.encrypt(chunk))
        return output_file

    @staticmethod
    def decrypt_file(
        input_file: str, output_file: str, key: bytes, algorithm="AES"
    ) -> str:
        """
        使用流式处理解密大文件。

        Args:
            input_file: 加密的源文件路径。
            output_file: 解密后的目标文件路径。
            key: 解密密钥。
            algorithm: 算法 ('AES' 或 'DES')。

        Returns:
            str: 目标文件路径。
        """
        alg = algorithm.upper()
        if alg == "AES":
            iv_size = AES.block_size
            block_size = AES.block_size
        elif alg == "DES":
            iv_size = DES.block_size
            block_size = DES.block_size
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        chunk_size = 1024 * block_size
        with open(input_file, "rb") as f_in, open(output_file, "wb") as f_out:
            iv = f_in.read(iv_size)  # 从文件头部读取 IV
            if alg == "AES":
                cipher = AES.new(key, AES.MODE_CBC, iv)
            else:
                cipher = DES.new(key, DES.MODE_CBC, iv)

            # 使用缓冲区处理，以便正确识别最后一块并去除填充
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
            data = data.encode("utf-8")
        recipient_key = RSA.import_key(public_key)
        cipher_rsa = PKCS1_OAEP.new(recipient_key)
        enc_data = cipher_rsa.encrypt(data)
        return base64.b64encode(enc_data).decode("utf-8")

    @staticmethod
    def rsa_decrypt(enc_data_b64: str, private_key: bytes) -> str:
        """使用 RSA 私钥解密数据"""
        enc_data = base64.b64decode(enc_data_b64)
        key = RSA.import_key(private_key)
        cipher_rsa = PKCS1_OAEP.new(key)
        data = cipher_rsa.decrypt(enc_data)
        return data.decode("utf-8")

    @staticmethod
    def rsa_sign(data, private_key: bytes) -> str:
        """使用 RSA 私钥对数据进行数字签名"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        key = RSA.import_key(private_key)
        h = SHA256.new(data)
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def rsa_verify(data, signature_b64: str, public_key: bytes) -> bool:
        """使用 RSA 公钥验证数字签名"""
        if isinstance(data, str):
            data = data.encode("utf-8")
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
    def ecc_generate_keypair(curve="P-256") -> tuple:
        """生成 ECC 密钥对"""
        key = ECC.generate(curve=curve)
        return key.export_key(format="PEM"), key.public_key().export_key(format="PEM")

    @staticmethod
    def ecc_sign(data, private_key: bytes) -> str:
        """使用 ECC 私钥进行数字签名"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        key = ECC.import_key(private_key)
        h = SHA256.new(data)
        signer = DSS.new(key, "fips-186-3")
        signature = signer.sign(h)
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def ecc_verify(data, signature_b64: str, public_key: bytes) -> bool:
        """使用 ECC 公钥验证数字签名"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        signature = base64.b64decode(signature_b64)
        key = ECC.import_key(public_key)
        h = SHA256.new(data)
        verifier = DSS.new(key, "fips-186-3")
        try:
            verifier.verify(h, signature)
            return True
        except (ValueError, TypeError):
            return False
