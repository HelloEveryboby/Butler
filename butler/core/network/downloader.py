"""资源下载器（原 ``downloader``）。

原技能只是对顶层 ``downloader`` 包的代理，而该包不在本仓库内；
这里保持同样的惰性导入语义：后端缺失时返回明确错误，而不是在导入期崩溃。
日常下载请使用 ``network.download``（Aria2 下载管理器）。
"""

from __future__ import annotations

import contextlib
import socket
import sys
import threading
import time
import webbrowser
from typing import Any


def _impl():
    try:
        import downloader  # noqa: PLC0415 - 可选后端，延迟导入
    except ImportError as exc:
        raise RuntimeError(
            "资源下载器后端 (downloader) 未安装；请安装该独立包，"
            "或改用 network.download（Aria2 下载管理器）"
        ) from exc
    return downloader


def available() -> bool:
    """后端是否可用。"""
    try:
        _impl()
    except RuntimeError:
        return False
    return True


def handle_request(action: str, **kwargs: Any) -> Any:
    try:
        impl = _impl()
    except RuntimeError as exc:
        return {"error": str(exc)}
    handler = getattr(impl, "handle_request", None)
    if handler is None:
        return {"error": "downloader 包未暴露 handle_request"}
    return handler(action, **kwargs)


def find_available_port(start_port: int = 8329, max_port: int = 8340) -> int:
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("", port))
                return port
            except OSError:
                continue
    raise OSError("未找到可用的端口！")


def main() -> None:
    """独立启动（原 ``run.py``）：拉起 UI 与流式下载服务。"""
    try:
        impl = _impl()
    except RuntimeError as exc:
        print(f"❌ 启动失败: {exc}")
        sys.exit(1)

    port = find_available_port()
    impl.streaming_server_port = port
    impl.scheduler_thread = threading.Thread(target=impl.run_scheduler_daemon, daemon=True)
    impl.scheduler_thread.start()

    url = f"http://localhost:{port}/ui/index.html"
    print(f"🚀 服务已拉起，UI 面板地址: {url}")

    def _open_browser() -> None:
        time.sleep(1.2)
        with contextlib.suppress(Exception):
            webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    import http.server  # noqa: PLC0415 - 仅独立启动时需要

    httpd = http.server.ThreadingHTTPServer(("", port), impl.SafeHTTPRangeHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
