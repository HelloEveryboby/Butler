"""
🚀 高性能加密工具 (High-Perf Crypto)
利用 Rust 编写的底层模块提供极速的文件哈希、加密和解密功能。
支持 ChaCha20 流加密算法和 SHA256 哈希算法。
"""

import os
from typing import Dict, Optional
from butler.core.hybrid_link import HybridLinkClient
from package.core_utils.log_manager import LogManager

# 初始化日志
logger = LogManager.get_logger(__name__)


class HighPerfCrypto:
    def __init__(self):
        # 获取项目根目录 (package/security/high_perf_crypto.py -> package/security -> package -> project_root)
        self.root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.exec_path = os.path.join(
            self.root_dir,
            "programs",
            "hybrid_crypto",
            "target",
            "release",
            "hybrid_crypto_exec",
        )

        if not os.path.exists(self.exec_path):
            logger.warning(
                f"Rust binary not found at {self.exec_path}. Attempting to run build script..."
            )
            self._build_binary()

        self.client = HybridLinkClient(self.exec_path)

    def _build_binary(self):
        build_script = os.path.join(
            self.root_dir, "programs", "hybrid_crypto", "build.sh"
        )
        if os.path.exists(build_script):
            import subprocess

            try:
                subprocess.run(
                    ["bash", build_script],
                    check=True,
                    cwd=os.path.dirname(build_script),
                )
                logger.info("Successfully built Rust crypto module.")
            except Exception as e:
                logger.error(f"Failed to build Rust crypto module: {e}")
        else:
            logger.error("Build script not found.")

    def hash_file(self, file_path: str) -> Optional[str]:
        """使用 Rust 计算文件的 SHA256 哈希值"""
        if not os.path.exists(file_path):
            return None

        with self.client as client:
            result = client.call("hash_file", {"path": os.path.abspath(file_path)})
            if result and "hash" in result:
                return result["hash"]
            return None

    def encrypt_file(
        self, input_path: str, output_path: str, key: str, nonce: str
    ) -> bool:
        """使用 Rust 加密文件"""
        if not os.path.exists(input_path):
            return False

        with self.client as client:
            result = client.call(
                "encrypt_file",
                {
                    "input": os.path.abspath(input_path),
                    "output": os.path.abspath(output_path),
                    "key": key,
                    "nonce": nonce,
                },
            )
            return result and result.get("status") == "success"

    def decrypt_file(
        self, input_path: str, output_path: str, key: str, nonce: str
    ) -> bool:
        """使用 Rust 解密文件 (ChaCha20 对称，与加密逻辑相同)"""
        return self.encrypt_file(input_path, output_path, key, nonce)

    def generate_key_pair(self) -> Dict[str, str]:
        """生成随机的 Key 和 Nonce"""
        with self.client as client:
            result = client.call("generate_key", {})
            return result if result else {}


def run(*args, **kwargs):
    """Butler 系统扩展调用入口"""
    crypto = HighPerfCrypto()

    print("\n" + "=" * 50)
    print("🚀 Rust 高性能加密工具")
    print("=" * 50)
    print(" 1. 计算文件 SHA256 哈希")
    print(" 2. 加密文件 (ChaCha20)")
    print(" 3. 解密文件 (ChaCha20)")
    print(" 4. 生成随机密钥对")
    print(" 0. 退出")
    print("=" * 50)

    try:
        choice = input("请选择操作 (0-4): ")
        if choice == "1":
            path = input("请输入文件路径: ").strip().strip('"')
            print("正在计算...")
            res = crypto.hash_file(path)
            print(f"SHA256: {res}" if res else "❌ 计算失败")
        elif choice == "2":
            input_p = input("源文件路径: ").strip().strip('"')
            output_p = input("输出加密文件路径: ").strip().strip('"')
            key_pair = crypto.generate_key_pair()
            if not key_pair:
                print("❌ 无法生成密钥")
                return

            print("🔑 自动生成密钥:")
            print(f"Key:   {key_pair['key']}")
            print(f"Nonce: {key_pair['nonce']}")
            print("⚠️ 请务必妥善保存上述密钥，否则无法解密！")

            if input("确认加密? (y/n): ").lower() == "y":
                if crypto.encrypt_file(
                    input_p, output_p, key_pair["key"], key_pair["nonce"]
                ):
                    print(f"✅ 加密成功: {output_p}")
                else:
                    print("❌ 加密失败")
        elif choice == "3":
            input_p = input("加密文件路径: ").strip().strip('"')
            output_p = input("解密后文件路径: ").strip().strip('"')
            key = input("Key (Hex): ").strip()
            nonce = input("Nonce (Hex): ").strip()
            if crypto.decrypt_file(input_p, output_p, key, nonce):
                print(f"✅ 解密成功: {output_p}")
            else:
                print("❌ 解密失败")
        elif choice == "4":
            kp = crypto.generate_key_pair()
            print(f"Key:   {kp.get('key')}")
            print(f"Nonce: {kp.get('nonce')}")
        elif choice == "0":
            print("退出。")
    except Exception as e:
        print(f"❌ 运行出错: {e}")


if __name__ == "__main__":
    run()
