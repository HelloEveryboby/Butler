"""
Butler 统一启动脚本
作用：自动安装依赖、初始化环境并启动 Jarvis。
"""

import os
import sys
import subprocess

def run_command(command):
    print(f"执行命令: {command}")
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e}")
        return False
    return True

def main():
    print("=== Jarvis 智能助手启动器 ===")

    # 1. 检查虚拟环境
    if not hasattr(sys, 'real_prefix') and not (has_venv := os.path.exists("venv")):
        print("建议在虚拟环境中运行。")

    # 2. 安装核心依赖
    print("\n[1/3] 检查并更新依赖...")
    run_command("pip install -r requirements.txt")
    run_command("pip install flask-socketio eventlet paho-mqtt pyserial python-dotenv")

    # 3. 初始化语音环境
    print("\n[2/3] 初始化语音环境...")
    from package import voice_setup
    voice_setup.run()

    # 4. 启动主程序
    print("\n[3/3] 启动 Jarvis...")
    from butler.main import main as start_butler
    start_butler()

if __name__ == "__main__":
    main()
