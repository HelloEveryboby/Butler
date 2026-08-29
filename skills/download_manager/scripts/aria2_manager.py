"""
Aria2 生命周期管理 — 自动下载、启动、停止、配置
Aria2 是高性能下载引擎，支持 HTTP/FTP/BT/Magnet
"""

import os
import sys
import json
import time
import shutil
import platform
import subprocess
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, Dict, Any

# ---------- 常量 ----------
ARIA2_VERSION = "1.37.0"
BASE_DIR = Path(__file__).parent.parent / "runtime"
ARIA2_DIR = BASE_DIR / "aria2"
ARIA2_BINARY = ARIA2_DIR / ("aria2c.exe" if platform.system() == "Windows" else "aria2c")
ARIA2_PID_FILE = ARIA2_DIR / "aria2.pid"
ARIA2_LOG_FILE = ARIA2_DIR / "aria2.log"
ARIA2_CONF = ARIA2_DIR / "aria2.conf"
ARIA2_SESSION = ARIA2_DIR / "aria2.session"

DEFAULT_RPC_PORT = 6800
DEFAULT_RPC_SECRET = "butler_download"

# ---------- 平台检测 ----------
def get_platform_info() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_map = {"linux": "linux", "darwin": "osx", "windows": "win"}
    arch_map = {"x86_64": "64", "amd64": "64", "aarch64": "arm64", "arm64": "arm64"}
    return os_map.get(system, "linux"), arch_map.get(machine, "64")


def get_download_url(os_name: str, arch: str) -> str:
    if os_name == "win":
        return f"https://github.com/aria2/aria2/releases/download/release-{ARIA2_VERSION}/aria2-{ARIA2_VERSION}-{os_name}-{arch}bit-build1.zip"
    elif os_name == "osx":
        return f"https://github.com/aria2/aria2/releases/download/release-{ARIA2_VERSION}/aria2-{ARIA2_VERSION}-{os_name}-darwin{arch}.tar.gz"
    else:
        return f"https://github.com/aria2/aria2/releases/download/release-{ARIA2_VERSION}/aria2-{ARIA2_VERSION}-{os_name}-{arch}bit-build1.tar.gz"


# ---------- 下载 ----------
def download_aria2() -> bool:
    if ARIA2_BINARY.exists():
        return True

    os_name, arch = get_platform_info()
    url = get_download_url(os_name, arch)
    print(f"[下载] Aria2 {ARIA2_VERSION}: {url}")

    ARIA2_DIR.mkdir(parents=True, exist_ok=True)
    ext = "zip" if url.endswith(".zip") else "tar.gz"
    download_path = BASE_DIR / f"aria2-download.{ext}"

    try:
        urllib.request.urlretrieve(url, download_path)

        if ext == "zip":
            with zipfile.ZipFile(download_path) as zf:
                for name in zf.namelist():
                    if name.endswith("aria2c") or name.endswith("aria2c.exe"):
                        with zf.open(name) as src, open(ARIA2_BINARY, "wb") as dst:
                            dst.write(src.read())
        else:
            with tarfile.open(download_path) as tf:
                for member in tf.getmembers():
                    if member.name.endswith("aria2c"):
                        src = tf.extractfile(member)
                        if src:
                            with open(ARIA2_BINARY, "wb") as dst:
                                dst.write(src.read())

        download_path.unlink(missing_ok=True)
        if platform.system() != "Windows":
            os.chmod(ARIA2_BINARY, 0o755)

        print(f"[OK] Aria2 就绪: {ARIA2_BINARY}")
        return True
    except Exception as e:
        print(f"[错误] 下载 Aria2 失败: {e}")
        return False


# ---------- 配置 ----------
def write_config(
    rpc_port: int = DEFAULT_RPC_PORT,
    rpc_secret: str = DEFAULT_RPC_SECRET,
    max_concurrent: int = 10,
    max_connection: int = 16,
    download_dir: str = "",
    max_overall_speed: str = "0",
    max_per_task_speed: str = "0",
) -> str:
    """生成 Aria2 配置文件"""
    if not download_dir:
        download_dir = str(Path.home() / "Downloads" / "Butler")

    os.makedirs(download_dir, exist_ok=True)

    config = f"""# Butler Download Manager — Aria2 配置
# RPC 设置
enable-rpc=true
rpc-listen-port={rpc_port}
rpc-secret={rpc_secret}
rpc-allow-origin-all=true

# 下载设置
dir={download_dir}
max-concurrent-downloads={max_concurrent}
max-connection-per-server={max_connection}
min-split-size=1M
split=16
max-overall-download-limit={max_overall_speed}
max-download-limit={max_per_task_speed}

# 断点续传
continue=true
auto-file-renaming=true
allow-overwrite=false

# HTTP/FTP 设置
check-integrity=true
retry-wait=3
max-tries=5
timeout=60
connect-timeout=60

# BT 设置
enable-dht=true
enable-peer-exchange=true
bt-enable-lpd=true
bt-max-peers=128
bt-request-peer-speed-limit=10M
bt-tracker=
listen-port=51413
dht-listen-port=51414

# 会话保存
input-file={ARIA2_SESSION}
save-session={ARIA2_SESSION}
save-session-interval=1

# 日志
log={ARIA2_LOG_FILE}
log-level=warn
"""

    ARIA2_CONF.write_text(config)
    # 创建空会话文件
    if not ARIA2_SESSION.exists():
        ARIA2_SESSION.touch()

    return str(ARIA2_CONF)


# ---------- 启动/停止 ----------
def start_aria2(
    rpc_port: int = DEFAULT_RPC_PORT,
    rpc_secret: str = DEFAULT_RPC_SECRET,
    max_concurrent: int = 10,
    max_connection: int = 16,
    download_dir: str = "",
) -> Dict[str, Any]:
    if is_running():
        return {"success": True, "message": "Aria2 已在运行", "rpc_port": rpc_port}

    if not download_aria2():
        return {"success": False, "message": "Aria2 下载失败"}

    write_config(rpc_port, rpc_secret, max_concurrent, max_connection, download_dir)

    log_file = open(ARIA2_LOG_FILE, "w")
    try:
        proc = subprocess.Popen(
            [str(ARIA2_BINARY), f"--conf-path={ARIA2_CONF}"],
            stdout=log_file, stderr=log_file, stdin=subprocess.DEVNULL,
        )
        ARIA2_PID_FILE.write_text(str(proc.pid))
        time.sleep(2)

        if proc.poll() is not None:
            log_content = ARIA2_LOG_FILE.read_text() if ARIA2_LOG_FILE.exists() else ""
            return {"success": False, "message": f"Aria2 启动失败: {log_content[-200:]}"}

        return {
            "success": True,
            "message": "Aria2 启动成功",
            "pid": proc.pid,
            "rpc_port": rpc_port,
            "rpc_url": f"http://localhost:{rpc_port}/jsonrpc",
            "download_dir": download_dir or str(Path.home() / "Downloads" / "Butler"),
        }
    except Exception as e:
        log_file.close()
        return {"success": False, "message": f"启动失败: {e}"}


def stop_aria2() -> Dict[str, Any]:
    if not is_running():
        return {"success": True, "message": "Aria2 未在运行"}
    pid = get_pid()
    if pid:
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, 15)
            time.sleep(1)
            ARIA2_PID_FILE.unlink(missing_ok=True)
            return {"success": True, "message": "Aria2 已停止"}
        except Exception as e:
            return {"success": False, "message": f"停止失败: {e}"}
    return {"success": False, "message": "无法获取 PID"}


def is_running() -> bool:
    pid = get_pid()
    if not pid:
        return False
    try:
        if platform.system() == "Windows":
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            return str(pid) in r.stdout
        else:
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, OSError):
        ARIA2_PID_FILE.unlink(missing_ok=True)
        return False


def get_pid() -> Optional[int]:
    if ARIA2_PID_FILE.exists():
        try:
            return int(ARIA2_PID_FILE.read_text().strip())
        except ValueError:
            return None
    return None


def get_status() -> Dict[str, Any]:
    running = is_running()
    return {
        "running": running,
        "pid": get_pid() if running else None,
        "rpc_port": DEFAULT_RPC_PORT,
        "rpc_url": f"http://localhost:{DEFAULT_RPC_PORT}/jsonrpc" if running else None,
        "binary": str(ARIA2_BINARY),
        "config": str(ARIA2_CONF),
        "log": str(ARIA2_LOG_FILE),
    }
