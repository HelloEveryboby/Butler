"""通用工具函数:字节格式化、目录大小统计、安全删除等。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def format_bytes(num: float) -> str:
    """把字节数格式化为人类可读字符串。"""
    sign = "-" if num < 0 else ""
    num = abs(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024.0:
            return f"{sign}{num:.1f} {unit}"
        num /= 1024.0
    return f"{sign}{num:.1f} PB"


def format_size_short(num: float) -> str:
    """紧凑版字节格式化(无小数,用于表格)。"""
    num = abs(num)
    for unit in ("B", "K", "M", "G", "T"):
        if num < 1024.0:
            return f"{num:.0f}{unit}"
        num /= 1024.0
    return f"{num:.0f}P"


def dir_size(path: str | Path) -> int:
    """递归统计目录大小,遇到权限错误自动跳过。"""
    total = 0
    try:
        for entry in Path(path).rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def safe_remove(path: str | Path, dry_run: bool = True) -> bool:
    """安全删除文件或目录,返回是否成功(或 dry_run 下是否可删除)。"""
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return False
    if dry_run:
        return True
    try:
        if p.is_symlink() or p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        return True
    except (OSError, PermissionError):
        return False


def expand_user(path: str) -> str:
    """扩展 ~ 和环境变量。"""
    return os.path.expanduser(os.path.expandvars(path))


def normalize_name(name: str) -> str:
    """把软件名归一化,便于残留匹配:小写、去除空格与常见分隔符。"""
    low = name.lower()
    out = []
    for ch in low:
        if ch.isalnum():
            out.append(ch)
    return "".join(out)


def name_matches(candidate: str, target: str) -> bool:
    """判断候选名是否匹配目标软件名(归一化后子串包含)。"""
    c = normalize_name(candidate)
    t = normalize_name(target)
    if not c or not t:
        return False
    return t in c or c in t
