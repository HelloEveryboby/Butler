"""
本地磁盘挂载管理 — 通过 Rclone 将 AList WebDAV 挂载为本地磁盘
支持 Windows (WinFSP) / macOS (macFUSE) / Linux (FUSE)
"""

import os
import sys
import json
import time
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

# ---------- 常量 ----------
BASE_DIR = Path(__file__).parent.parent / "runtime"
RCLONE_DIR = BASE_DIR / "rclone"
RCLONE_BINARY = RCLONE_DIR / ("rclone.exe" if platform.system() == "Windows" else "rclone")
RCLONE_CONFIG = RCLONE_DIR / "rclone.conf"
RCLONE_PID_FILE = RCLONE_DIR / "mount.pid"
RCLONE_LOG_FILE = RCLONE_DIR / "mount.log"

# AList 默认 WebDAV 地址
ALIST_WEBDAV_URL = "http://localhost:5244/dav"
ALIST_REMOTE_NAME = "butler-alist"

# ---------- 平台检测 ----------
def get_rclone_download_url() -> str:
    """获取 Rclone 下载链接"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "https://downloads.rclone.org/current/rclone-current-windows-amd64.zip"
    elif system == "darwin":
        if machine == "arm64":
            return "https://downloads.rclone.org/current/rclone-current-osx-arm64.zip"
        return "https://downloads.rclone.org/current/rclone-current-osx-amd64.zip"
    else:
        if machine in ("aarch64", "arm64"):
            return "https://downloads.rclone.org/current/rclone-current-linux-arm64.zip"
        return "https://downloads.rclone.org/current/rclone-current-linux-amd64.zip"


# ---------- 下载 ----------
def download_rclone() -> bool:
    """下载 Rclone"""
    if RCLONE_BINARY.exists():
        print(f"[OK] Rclone 已存在: {RCLONE_BINARY}")
        return True

    url = get_rclone_download_url()
    print(f"[下载] Rclone: {url}")

    RCLONE_DIR.mkdir(parents=True, exist_ok=True)
    download_path = BASE_DIR / "rclone-download.zip"

    try:
        import urllib.request
        urllib.request.urlretrieve(url, download_path)

        import zipfile
        with zipfile.ZipFile(download_path) as zf:
            for name in zf.namelist():
                basename = name.split("/")[-1]
                if basename == "rclone" or basename == "rclone.exe":
                    with zf.open(name) as src, open(RCLONE_BINARY, "wb") as dst:
                        dst.write(src.read())

        download_path.unlink(missing_ok=True)

        if platform.system() != "Windows":
            os.chmod(RCLONE_BINARY, 0o755)

        print(f"[OK] Rclone 就绪: {RCLONE_BINARY}")
        return True

    except Exception as e:
        print(f"[错误] 下载 Rclone 失败: {e}")
        return False


# ---------- 配置 ----------
def write_rclone_config(
    webdav_url: str = ALIST_WEBDAV_URL,
    username: str = "",
    password: str = ""
) -> bool:
    """写入 Rclone 配置，连接 AList WebDAV"""
    RCLONE_DIR.mkdir(parents=True, exist_ok=True)

    config_content = f"""[{ALIST_REMOTE_NAME}]
type = webdav
url = {webdav_url}
vendor = other
user = {username}
pass = {password}
"""

    RCLONE_CONFIG.write_text(config_content)
    print(f"[OK] Rclone 配置已写入: {RCLONE_CONFIG}")
    return True


# ---------- 挂载 ----------
def get_mount_command(mount_point: str) -> list[str]:
    """构建挂载命令"""
    remote = f"{ALIST_REMOTE_NAME}:"
    system = platform.system()

    base_cmd = [str(RCLONE_BINARY), "mount", remote, mount_point]

    if system == "Windows":
        # Windows 使用 WinFSP
        base_cmd.extend([
            "--vfs-cache-mode", "writes",
            "--vfs-cache-max-age", "1h",
            "--volname", "Butler Cloud",
        ])
    elif system == "Darwin":
        # macOS 使用 macFUSE
        base_cmd.extend([
            "--vfs-cache-mode", "writes",
            "--vfs-cache-max-age", "1h",
            "--volname", "Butler Cloud",
            "--allow-other",
        ])
    else:
        # Linux 使用 FUSE
        base_cmd.extend([
            "--vfs-cache-mode", "writes",
            "--vfs-cache-max-age", "1h",
            "--allow-other",
            "--daemon",
        ])

    return base_cmd


def mount(
    mount_point: str,
    letter: Optional[str] = None,
    webdav_url: str = ALIST_WEBDAV_URL,
    username: str = "",
    password: str = ""
) -> Dict[str, Any]:
    """挂载网盘为本地磁盘"""
    # 检查是否已挂载
    if is_mounted():
        return {"success": True, "message": "已挂载", "mount_point": str(get_mount_point())}

    # 下载 Rclone
    if not download_rclone():
        return {"success": False, "message": "Rclone 下载失败"}

    # 写入配置
    write_rclone_config(webdav_url, username, password)

    # 确定挂载点
    system = platform.system()
    if system == "Windows":
        if letter:
            mount_point = f"{letter}:"
        elif not mount_point:
            mount_point = "Z:"
    else:
        if not mount_point:
            mount_point = str(Path.home() / "butler-cloud")
        Path(mount_point).mkdir(parents=True, exist_ok=True)

    # 构建挂载命令
    cmd = get_mount_command(mount_point)

    print(f"[挂载] {webdav_url} → {mount_point}")
    print(f"[命令] {' '.join(cmd)}")

    try:
        log_file = open(RCLONE_LOG_FILE, "w")

        if system == "Linux":
            # Linux: rclone mount --daemon 会自动后台化
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return {"success": False, "message": f"挂载失败: {result.stderr}"}
            # 查找 daemon PID
            time.sleep(2)
            # rclone daemon 模式不直接给 PID，通过进程查找
            ps = subprocess.run(["pgrep", "-f", f"rclone.*{mount_point}"], capture_output=True, text=True)
            if ps.stdout.strip():
                RCLONE_PID_FILE.write_text(ps.stdout.strip().split("\n")[0])
        else:
            # Windows/macOS: 前台启动后后台化
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.DEVNULL,
            )
            RCLONE_PID_FILE.write_text(str(proc.pid))
            time.sleep(3)

            if proc.poll() is not None:
                log_content = RCLONE_LOG_FILE.read_text() if RCLONE_LOG_FILE.exists() else ""
                return {"success": False, "message": f"挂载失败: {log_content[-300:]}"}

        print(f"[OK] 已挂载到 {mount_point}")
        return {
            "success": True,
            "message": "挂载成功",
            "mount_point": mount_point,
            "remote": ALIST_REMOTE_NAME,
        }

    except Exception as e:
        return {"success": False, "message": f"挂载失败: {e}"}


def unmount() -> Dict[str, Any]:
    """卸载网盘"""
    if not is_mounted():
        return {"success": True, "message": "未挂载"}

    mount_point = get_mount_point()
    system = platform.system()

    try:
        if system == "Windows":
            # Windows: 终止 rclone 进程
            pid = get_mount_pid()
            if pid:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        elif system == "Darwin":
            # macOS: umount
            subprocess.run(["umount", str(mount_point)], capture_output=True)
            pid = get_mount_pid()
            if pid:
                os.kill(pid, 15)
        else:
            # Linux: fusermount
            subprocess.run(["fusermount", "-u", str(mount_point)], capture_output=True)

        time.sleep(1)
        RCLONE_PID_FILE.unlink(missing_ok=True)
        print(f"[OK] 已卸载 {mount_point}")
        return {"success": True, "message": "已卸载", "mount_point": str(mount_point)}

    except Exception as e:
        return {"success": False, "message": f"卸载失败: {e}"}


def is_mounted() -> bool:
    """检查是否已挂载"""
    pid = get_mount_pid()
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
        RCLONE_PID_FILE.unlink(missing_ok=True)
        return False


def get_mount_pid() -> Optional[int]:
    if RCLONE_PID_FILE.exists():
        try:
            return int(RCLONE_PID_FILE.read_text().strip())
        except ValueError:
            return None
    return None


def get_mount_point() -> Optional[Path]:
    """获取当前挂载点"""
    system = platform.system()
    if system == "Windows":
        # 通过 rclone 进程参数查找
        return Path("Z:")  # 默认
    else:
        return Path.home() / "butler-cloud"


def get_status() -> Dict[str, Any]:
    """获取挂载状态"""
    mounted = is_mounted()
    return {
        "mounted": mounted,
        "pid": get_mount_pid() if mounted else None,
        "mount_point": str(get_mount_point()) if mounted else None,
        "rclone_binary": str(RCLONE_BINARY),
        "rclone_config": str(RCLONE_CONFIG),
        "log_file": str(RCLONE_LOG_FILE),
    }


# ---------- 检查前置条件 ----------
def check_fuse() -> Dict[str, Any]:
    """检查 FUSE 是否可用"""
    system = platform.system()

    if system == "Windows":
        # 检查 WinFSP
        winfsp_path = Path("C:/Program Files (x86)/WinFsp")
        if winfsp_path.exists():
            return {"available": True, "name": "WinFSP", "path": str(winfsp_path)}
        return {
            "available": False,
            "name": "WinFSP",
            "message": "请安装 WinFSP: https://winfsp.dev/rel/",
            "download_url": "https://github.com/winfsp/winfsp/releases/latest",
        }

    elif system == "Darwin":
        # 检查 macFUSE
        macfuse_path = Path("/Library/Filesystems/macfuse.fs")
        if macfuse_path.exists():
            return {"available": True, "name": "macFUSE", "path": str(macfuse_path)}
        return {
            "available": False,
            "name": "macFUSE",
            "message": "请安装 macFUSE: https://osxfuse.github.io/",
            "download_url": "https://github.com/osxfuse/osxfuse/releases/latest",
        }

    else:
        # Linux: 检查 FUSE
        fuse_path = Path("/dev/fuse")
        if fuse_path.exists():
            return {"available": True, "name": "FUSE", "path": str(fuse_path)}
        return {
            "available": False,
            "name": "FUSE",
            "message": "请安装 FUSE: sudo apt install fuse (Debian/Ubuntu) 或 sudo yum install fuse (CentOS)",
        }


# ---------- CLI ----------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="网盘挂载管理")
    parser.add_argument("action", choices=["mount", "unmount", "status", "check", "download"],
                        help="操作")
    parser.add_argument("--mount-point", type=str, help="挂载目录路径")
    parser.add_argument("--letter", type=str, help="Windows 盘符 (如 Z)")
    parser.add_argument("--webdav-url", type=str, default=ALIST_WEBDAV_URL, help="WebDAV 地址")
    parser.add_argument("--username", type=str, default="", help="WebDAV 用户名")
    parser.add_argument("--password", type=str, default="", help="WebDAV 密码")

    args = parser.parse_args()

    if args.action == "mount":
        result = mount(args.mount_point or "", args.letter, args.webdav_url, args.username, args.password)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "unmount":
        result = unmount()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "status":
        result = get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "check":
        result = check_fuse()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "download":
        download_rclone()
