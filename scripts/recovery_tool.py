"""
Butler 紧急恢复工具 (Standalone Recovery Tool)
用于在系统自毁（乱码化）后通过 6 位核心码还原文件。
"""
import os
import hashlib

def recover_file(file_path, core_code):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()

        key = hashlib.sha256(core_code.encode()).digest()
        recovered = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))

        original_path = file_path.replace(".garbled", "")
        with open(original_path, 'wb') as f:
            f.write(recovered)

        os.remove(file_path)
        print(f"已恢复: {original_path}")
    except Exception as e:
        print(f"恢复失败 {file_path}: {e}")

def main():
    print("=== Butler 紧急恢复工具 ===")
    core_code = input("请输入 6 位全局核心码: ").strip()
    if len(core_code) != 6:
        print("错误: 核心码必须为 6 位")
        return

    # 扫描当前目录下所有 .garbled 文件
    found = False
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".garbled"):
                found = True
                recover_file(os.path.join(root, file), core_code)

    if not found:
        print("未发现需要恢复的乱码文件 (.garbled)。")
    else:
        print("恢复操作已完成。")

if __name__ == "__main__":
    main()
