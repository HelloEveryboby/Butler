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
    """Symmetric encryption/decryption for AES and DES with streaming support."""

    @staticmethod
    def derive_key(password, salt, algorithm='AES'):
        """Derive a key from a password and salt."""
        dk_len = 16 if algorithm.upper() == 'AES' else 8
        return PBKDF2(password, salt, dkLen=dk_len, count=100000)

    @staticmethod
    def encrypt_data(data, key, algorithm='AES'):
        """Encrypt string/bytes data."""
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
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        ct_bytes = cipher.encrypt(pad(data, block_size))
        iv = base64.b64encode(cipher.iv).decode('utf-8')
        ct = base64.b64encode(ct_bytes).decode('utf-8')
        return iv, ct

    @staticmethod
    def decrypt_data(iv_b64, ct_b64, key, algorithm='AES'):
        """Decrypt string data."""
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
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        pt = unpad(cipher.decrypt(ct), block_size)
        return pt.decode('utf-8')

    @staticmethod
    def encrypt_file(input_file, output_file, key, algorithm='AES'):
        """Encrypt a file using streaming to handle large files."""
        alg = algorithm.upper()
        if alg == 'AES':
            cipher = AES.new(key, AES.MODE_CBC)
            block_size = AES.block_size
        elif alg == 'DES':
            cipher = DES.new(key, DES.MODE_CBC)
            block_size = DES.block_size
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        chunk_size = 1024 * block_size
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            f_out.write(cipher.iv)
            while True:
                chunk = f_in.read(chunk_size)
                if len(chunk) < chunk_size:
                    # Last chunk, apply padding
                    f_out.write(cipher.encrypt(pad(chunk, block_size)))
                    break
                f_out.write(cipher.encrypt(chunk))
        return output_file

    @staticmethod
    def decrypt_file(input_file, output_file, key, algorithm='AES'):
        """Decrypt a file using streaming."""
        alg = algorithm.upper()
        if alg == 'AES':
            iv_size = AES.block_size
            block_size = AES.block_size
        elif alg == 'DES':
            iv_size = DES.block_size
            block_size = DES.block_size
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        chunk_size = 1024 * block_size
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            iv = f_in.read(iv_size)
            if alg == 'AES':
                cipher = AES.new(key, AES.MODE_CBC, iv)
            else:
                cipher = DES.new(key, DES.MODE_CBC, iv)

            # Use a lookahead buffer to identify the last chunk for unpadding
            current_chunk = f_in.read(chunk_size)
            while True:
                next_chunk = f_in.read(chunk_size)
                if not next_chunk:
                    # current_chunk is the last one
                    f_out.write(unpad(cipher.decrypt(current_chunk), block_size))
                    break
                f_out.write(cipher.decrypt(current_chunk))
                current_chunk = next_chunk
        return output_file

class AsymmetricCrypto:
    """Asymmetric encryption and signing for RSA and ECC."""

    # RSA Section
    @staticmethod
    def rsa_generate_keypair(bits=2048):
        key = RSA.generate(bits)
        return key.export_key(), key.publickey().export_key()

    @staticmethod
    def rsa_encrypt(data, public_key):
        if isinstance(data, str):
            data = data.encode('utf-8')
        recipient_key = RSA.import_key(public_key)
        cipher_rsa = PKCS1_OAEP.new(recipient_key)
        enc_data = cipher_rsa.encrypt(data)
        return base64.b64encode(enc_data).decode('utf-8')

    @staticmethod
    def rsa_decrypt(enc_data_b64, private_key):
        enc_data = base64.b64decode(enc_data_b64)
        key = RSA.import_key(private_key)
        cipher_rsa = PKCS1_OAEP.new(key)
        data = cipher_rsa.decrypt(enc_data)
        return data.decode('utf-8')

    @staticmethod
    def rsa_sign(data, private_key):
        if isinstance(data, str):
            data = data.encode('utf-8')
        key = RSA.import_key(private_key)
        h = SHA256.new(data)
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def rsa_verify(data, signature_b64, public_key):
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

    # ECC Section
    @staticmethod
    def ecc_generate_keypair(curve='P-256'):
        key = ECC.generate(curve=curve)
        return key.export_key(format='PEM'), key.public_key().export_key(format='PEM')

    @staticmethod
    def ecc_sign(data, private_key):
        if isinstance(data, str):
            data = data.encode('utf-8')
        key = ECC.import_key(private_key)
        h = SHA256.new(data)
        signer = DSS.new(key, 'fips-186-3')
        signature = signer.sign(h)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def ecc_verify(data, signature_b64, public_key):
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
