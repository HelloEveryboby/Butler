#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import threading
import time
import webbrowser
import socket

# Add repository root to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set standalone env flag
os.environ["BUTLER_DOWNLOADER_STANDALONE"] = "1"

import downloader

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
    print("      Butler 资源下载器 - Motrix 蓝本 UI 独立模式")
    print("=" * 60)

    try:
        port = find_available_port()
    except OSError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

    downloader.streaming_server_port = port

    downloader.scheduler_thread = threading.Thread(target=downloader.run_scheduler_daemon, daemon=True)
    downloader.scheduler_thread.start()

    url = f"http://localhost:{port}/ui/index.html"
    print(f"🚀 服务已拉起，正在自动打开浏览器...")
    print(f"🔗 UI 面板地址: {url}")
    print(f"📂 默认下载路径: {downloader.get_downloads_dir()}")
    print("按下 Ctrl+C 可停止运行。")
    print("=" * 60)

    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    import http.server
    try:
        httpd = http.server.ThreadingHTTPServer(("", port), downloader.SafeHTTPRangeHandler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。感谢您的使用！")

if __name__ == "__main__":
    main()
