#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import threading
import time
import webbrowser
import socket

# Ensure dependencies are satisfied
def ensure_dependencies():
    missing = []
    try:
        import yaml
    except ImportError:
        missing.append("pyyaml")
    try:
        import requests
    except ImportError:
        missing.append("requests")
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        missing.append("beautifulsoup4")

    if missing:
        print(f"检测到缺少以下依赖: {', '.join(missing)}")
        print("正在为您自动安装必要依赖，请稍等...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
            print("依赖安装成功！")
        except subprocess.CalledProcessError as e:
            print(f"自动安装依赖失败: {e}")
            print("您可能需要手动运行: pip install " + " ".join(missing))
            print("继续尝试启动...")

ensure_dependencies()

# Add repository root to sys.path to allow correct module resolution
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set standalone env flag
os.environ["BUTLER_DOWNLOADER_STANDALONE"] = "1"

# Import downloader skill
try:
    import skills.downloader as downloader
except ImportError:
    # Fallback absolute path import if sys.path resolves differently
    sys.path.insert(0, os.path.dirname(script_dir))
    import downloader

# Explicitly flag standalone inside module
downloader.IS_STANDALONE = True

def find_available_port(start_port=8329, max_port=8340):
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise OSError("未找到可用的端口！")

def main():
    print("=" * 60)
    print("      Butler 资源下载器 - 独立运行模式 (Standalone)")
    print("=" * 60)

    # Find available port
    try:
        port = find_available_port()
    except OSError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

    # Initialize downloader settings & daemon threads
    downloader.streaming_server_port = port

    # Start scheduler daemon
    downloader.scheduler_thread = threading.Thread(target=downloader.run_scheduler_daemon, daemon=True)
    downloader.scheduler_thread.start()

    url = f"http://localhost:{port}/ui/index.html"
    print(f"🚀 服务已拉起，正在自动打开浏览器...")
    print(f"🔗 UI 面板地址: {url}")
    print(f"📂 默认下载路径: {downloader.get_downloads_dir()}")
    print("按下 Ctrl+C 可停止运行。")
    print("=" * 60)

    # Open browser automatically with a slight delay
    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    # Launch server blockingly
    import http.server
    try:
        httpd = http.server.ThreadingHTTPServer(("", port), downloader.SafeHTTPRangeHandler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。感谢您的使用！")
    except Exception as e:
        print(f"服务异常终止: {e}")

if __name__ == "__main__":
    main()
