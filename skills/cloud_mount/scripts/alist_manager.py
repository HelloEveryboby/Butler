"""
AList 生命周期管理 — 下载、启动、停止、配置
AList 是一个开源的网盘聚合网关，支持 30+ 网盘服务
"""

import os
import sys
import json
import time
import shutil
import hashlib
import platform
import subprocess
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, Dict, Any

# ---------- 常量 ----------
ALIST_VERSION = "3.39.4"
BASE_DIR = Path(__file__).parent.parent / "runtime"
ALIST_DIR = BASE_DIR / "alist"
ALIST_DATA_DIR = ALIST_DIR / "data"
ALIST_CONFIG = ALIST_DIR / "config.json"
ALIST_BINARY = ALIST_DIR / ("alist.exe" if platform.system() == "Windows" else "alist")
ALIST_PID_FILE = ALIST_DIR / "alist.pid"
ALIST_LOG_FILE = ALIST_DIR / "alist.log"

DEFAULT_PORT = 5244
DEFAULT_ADMIN_USER = "admin"

# ---------- 平台检测 ----------
def get_platform_info() -> tuple[str, str]:
    """返回 (os, arch) 用于下载正确的二进制"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    os_map = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
    arch_map = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}

    os_name = os_map.get(system, "linux")
    arch = arch_map.get(machine, "amd64")
    return os_name, arch


def get_download_url(os_name: str, arch: str) -> str:
    """构建 AList 下载链接"""
    if os_name == "windows":
        ext = "zip"
        filename = f"alist-{os_name}-{arch}-v{ALIST_VERSION}.{ext}"
    else:
        ext = "tar.gz"
        filename = f"alist-{os_name}-{arch}-v{ALIST_VERSION}.{ext}"

    return f"https://github.com/alist-org/alist/releases/download/v{ALIST_VERSION}/{filename}"


# ---------- 下载 ----------
def download_alist() -> bool:
    """下载 AList 二进制文件"""
    if ALIST_BINARY.exists():
        print(f"[OK] AList 已存在: {ALIST_BINARY}")
        return True

    os_name, arch = get_platform_info()
    url = get_download_url(os_name, arch)
    print(f"[下载] AList v{ALIST_VERSION} ({os_name}/{arch})")
        print(f"[下载] {url}")

    ALIST_DIR.mkdir(parents=True, exist_ok=True)
    download_path = BASE_DIR / f"alist-download.{url.split('.')[-1]}"

    try:
        urllib.request.urlretrieve(url, download_path)
        print(f"[下载] 完成: {download_path}")

        # 解压
        if download_path.suffix == ".zip":
            with zipfile.ZipFile(download_path) as zf:
                for name in zf.namelist():
                    if name.endswith("alist") or name.endswith("alist.exe"):
                        with zf.open(name) as src, open(ALIST_BINARY, "wb") as dst:
                            dst.write(src.read())
        elif download_path.suffix == ".gz":
            with tarfile.open(download_path) as tf:
                for member in tf.getmembers():
                    if member.name.endswith("alist"):
                        src = tf.extractfile(member)
                        with open(ALIST_BINARY, "wb") as dst:
                            dst.write(src.read())

        # 清理下载文件
        download_path.unlink(missing_ok=True)

        # Linux/macOS 添加执行权限
        if platform.system() != "Windows":
            os.chmod(ALIST_BINARY, 0o755)

        print(f"[OK] AList 二进制就绪: {ALIST_BINARY}")
        return True

    except Exception as e:
        print(f"[错误] 下载失败: {e}")
        return False


# ---------- 密码管理 ----------
def get_admin_password() -> Optional[str]:
    """从 AList 数据库或配置获取管理员密码"""
    data_file = ALIST_DATA_DIR / "data.db"
    if data_file.exists():
        # AList 3.x 的密码存在 SQLite 中
        try:
            import sqlite3
            conn = sqlite3.connect(str(data_file))
            cursor = conn.execute("SELECT value FROM x_setting_items WHERE key = 'password'")
            row = cursor.fetchone()
            conn.close()
            if row:
                return row[0]
        except Exception:
            pass
    return None


def reset_admin_password(new_password: str) -> bool:
    """重置 AList 管理员密码"""
    if not ALIST_BINARY.exists():
        print("[错误] AList 未安装")
        return False

    try:
        result = subprocess.run(
            [str(ALIST_BINARY), "admin", "set", new_password],
            capture_output=True, text=True, cwd=str(ALIST_DIR)
        )
        if result.returncode == 0:
            print(f"[OK] 管理员密码已重置")
            return True
        else:
            print(f"[错误] {result.stderr}")
            return False
    except Exception as e:
        print(f"[错误] {e}")
        return False


# ---------- 服务管理 ----------
def start_alist(port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """启动 AList 服务"""
    # 检查是否已运行
    if is_running():
        return {"success": True, "message": "AList 已在运行中", "port": port}

    # 下载（如果需要）
    if not download_alist():
        return {"success": False, "message": "AList 下载失败"}

    ALIST_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 启动
    log_file = open(ALIST_LOG_FILE, "w")
    try:
        proc = subprocess.Popen(
            [str(ALIST_BINARY), "server", "--port", str(port)],
            cwd=str(ALIST_DIR),
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
        )

        # 保存 PID
        ALIST_PID_FILE.write_text(str(proc.pid))

        # 等待启动
        print(f"[启动] AList (PID: {proc.pid}, 端口: {port})")
        for i in range(15):
            time.sleep(1)
            if proc.poll() is not None:
                log_content = ALIST_LOG_FILE.read_text() if ALIST_LOG_FILE.exists() else ""
                return {"success": False, "message": f"AList 启动失败: {log_content[-200:]}"}
            try:
                urllib.request.urlopen(f"http://localhost:{port}/ping", timeout=2)
                break
            except Exception:
                continue

        # 获取初始密码
        password = get_admin_password() or "首次启动请查看日志"

        print(f"[OK] AList 已启动: http://localhost:{port}")
        print(f"[OK] 管理后台: http://localhost:{port}/manage")
        print(f"[OK] 用户名: {DEFAULT_ADMIN_USER}")
        print(f"[OK] 密码: {password}")

        return {
            "success": True,
            "message": "AList 启动成功",
            "port": port,
            "url": f"http://localhost:{port}",
            "manage_url": f"http://localhost:{port}/manage",
            "username": DEFAULT_ADMIN_USER,
            "password": password,
            "webdav_url": f"http://localhost:{port}/dav",
        }

    except Exception as e:
        log_file.close()
        return {"success": False, "message": f"启动失败: {e}"}


def stop_alist() -> Dict[str, Any]:
    """停止 AList 服务"""
    if not is_running():
        return {"success": True, "message": "AList 未在运行"}

    pid = get_pid()
    if pid:
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, 15)  # SIGTERM
            time.sleep(1)
            ALIST_PID_FILE.unlink(missing_ok=True)
            print(f"[OK] AList 已停止 (PID: {pid})")
            return {"success": True, "message": "AList 已停止"}
        except Exception as e:
            return {"success": False, "message": f"停止失败: {e}"}
    return {"success": False, "message": "无法获取 PID"}


def is_running() -> bool:
    """检查 AList 是否在运行"""
    pid = get_pid()
    if not pid:
        return False
    try:
        if platform.system() == "Windows":
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            return str(pid) in result.stdout
        else:
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, OSError):
        ALIST_PID_FILE.unlink(missing_ok=True)
        return False


def get_pid() -> Optional[int]:
    """获取 AList PID"""
    if ALIST_PID_FILE.exists():
        try:
            return int(ALIST_PID_FILE.read_text().strip())
        except ValueError:
            return None
    return None


def get_status() -> Dict[str, Any]:
    """获取 AList 状态"""
    running = is_running()
    return {
        "running": running,
        "pid": get_pid() if running else None,
        "port": DEFAULT_PORT,
        "url": f"http://localhost:{DEFAULT_PORT}" if running else None,
        "manage_url": f"http://localhost:{DEFAULT_PORT}/manage" if running else None,
        "webdav_url": f"http://localhost:{DEFAULT_PORT}/dav" if running else None,
        "binary": str(ALIST_BINARY),
        "data_dir": str(ALIST_DATA_DIR),
        "log_file": str(ALIST_LOG_FILE),
    }


# ---------- CLI ----------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AList 服务管理")
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "download", "reset-password"],
                        help="操作")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="端口号")
    parser.add_argument("--password", type=str, help="新密码（reset-password 时使用）")

    args = parser.parse_args()

    if args.action == "start":
        result = start_alist(args.port)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "stop":
        result = stop_alist()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "restart":
        stop_alist()
        time.sleep(2)
        result = start_alist(args.port)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "status":
        result = get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "download":
        download_alist()
    elif args.action == "reset-password":
        if not args.password:
            print("[错误] 请提供 --password 参数")
            sys.exit(1)
        reset_admin_password(args.password)
