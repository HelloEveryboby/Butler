"""垃圾文件清理模块。

扫描并清理:系统临时目录、用户缓存、包管理器缓存、回收站/废纸篓、旧日志。
所有清理操作默认 dry-run,需显式确认后才真正删除。
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .utils import dir_size, expand_user, format_bytes, safe_remove


@dataclass
class JunkItem:
    """一个待清理的垃圾项。"""

    category: str       # temp / cache / package-cache / trash / logs
    path: str
    size: int = 0
    description: str = ""

    @property
    def size_text(self) -> str:
        return format_bytes(self.size) if self.size else "-"


@dataclass
class CleanReport:
    """清理结果报告。"""

    scanned: int = 0
    total_size: int = 0
    cleaned: int = 0
    freed_bytes: int = 0
    skipped: int = 0
    items: List[JunkItem] = field(default_factory=list)


class JunkCleaner:
    """垃圾文件扫描与清理器。"""

    def scan(self, categories: Optional[List[str]] = None) -> List[JunkItem]:
        """扫描所有垃圾文件,可指定只扫描某些类别。"""
        categories = categories or ["temp", "cache", "package-cache", "trash", "logs"]
        items: List[JunkItem] = []
        if "temp" in categories:
            items.extend(self._scan_temp())
        if "cache" in categories:
            items.extend(self._scan_user_cache())
        if "package-cache" in categories:
            items.extend(self._scan_package_caches())
        if "trash" in categories:
            items.extend(self._scan_trash())
        if "logs" in categories:
            items.extend(self._scan_logs())
        return items

    def _scan_temp(self) -> List[JunkItem]:
        items: List[JunkItem] = []
        temp_dirs = ["/tmp", "/var/tmp"] if sys.platform != "win32" else [
            expand_user("%TEMP%"), expand_user("%WINDIR%\\Temp"),
        ]
        if sys.platform != "win32":
            temp_dirs.append(expand_user("~/.local/share/tmp"))
        for d in temp_dirs:
            p = Path(d)
            if not p.is_dir():
                continue
            size = dir_size(p)
            if size > 0 or p.exists():
                items.append(JunkItem(
                    category="temp", path=str(p), size=size,
                    description="系统临时目录",
                ))
        return items

    def _scan_user_cache(self) -> List[JunkItem]:
        items: List[JunkItem] = []
        if sys.platform == "darwin":
            cache_dirs = [expand_user("~/Library/Caches")]
        elif sys.platform == "win32":
            cache_dirs = [expand_user("%LOCALAPPDATA%\\Microsoft\\Windows\\INetCache")]
        else:
            cache_dirs = [expand_user("~/.cache")]
        for d in cache_dirs:
            p = Path(d)
            if not p.is_dir():
                continue
            items.append(JunkItem(
                category="cache", path=str(p), size=dir_size(p),
                description="用户缓存目录",
            ))
        return items

    def _scan_package_caches(self) -> List[JunkItem]:
        items: List[JunkItem] = []
        # 各包管理器缓存路径
        candidates = {
            "linux": [
                ("pip 缓存", expand_user("~/.cache/pip")),
                ("npm 缓存", expand_user("~/.npm")),
                ("yarn 缓存", expand_user("~/.cache/yarn")),
                ("apt 缓存", "/var/cache/apt/archives"),
                ("dnf 缓存", "/var/cache/dnf"),
                ("pacman 缓存", "/var/cache/pacman/pkg"),
                ("cargo 缓存", expand_user("~/.cargo/registry")),
                ("go 缓存", expand_user("~/go/pkg/mod")),
            ],
            "darwin": [
                ("pip 缓存", expand_user("~/Library/Caches/pip")),
                ("npm 缓存", expand_user("~/.npm")),
                ("Homebrew 缓存", expand_user("~/Library/Caches/Homebrew")),
                ("cargo 缓存", expand_user("~/.cargo/registry")),
            ],
            "win32": [
                ("pip 缓存", expand_user(r"%LOCALAPPDATA%\pip\cache")),
                ("npm 缓存", expand_user(r"%APPDATA%\npm-cache")),
                ("cargo 缓存", expand_user(r"%USERPROFILE%\.cargo\registry")),
            ],
        }
        key = "darwin" if sys.platform == "darwin" else ("win32" if sys.platform == "win32" else "linux")
        for desc, path in candidates[key]:
            p = Path(path)
            if not p.exists():
                continue
            size = dir_size(p) if p.is_dir() else (p.stat().st_size if p.is_file() else 0)
            items.append(JunkItem(
                category="package-cache", path=str(p), size=size,
                description=desc,
            ))
        return items

    def _scan_trash(self) -> List[JunkItem]:
        items: List[JunkItem] = []
        if sys.platform == "darwin":
            trash = expand_user("~/.Trash")
        elif sys.platform == "win32":
            # 回收站通常无法直接统计,跳过
            return items
        else:
            trash = expand_user("~/.local/share/Trash/files")
        p = Path(trash)
        if not p.is_dir():
            return items
        size = dir_size(p)
        items.append(JunkItem(
            category="trash", path=str(p), size=size,
            description="回收站/废纸篓",
        ))
        return items

    def _scan_logs(self) -> List[JunkItem]:
        items: List[JunkItem] = []
        if sys.platform == "win32":
            return items
        log_dirs = ["/var/log"]
        for d in log_dirs:
            p = Path(d)
            if not p.is_dir():
                continue
            # 只统计可读的旧日志文件,不删目录本身
            old_files = self._collect_old_logs(p, days=7)
            total = sum(f["size"] for f in old_files)
            items.append(JunkItem(
                category="logs", path=str(p), size=total,
                description=f"旧日志文件({len(old_files)} 个,>7天)",
            ))
        return items

    def _collect_old_logs(self, log_dir: Path, days: int = 7) -> List[dict]:
        """收集超过 N 天的日志文件。"""
        threshold = time.time() - days * 86400
        files: List[dict] = []
        try:
            for entry in log_dir.rglob("*"):
                if not entry.is_file():
                    continue
                try:
                    st = entry.stat()
                except (OSError, PermissionError):
                    continue
                if st.st_mtime < threshold:
                    files.append({"path": str(entry), "size": st.st_size})
        except (OSError, PermissionError):
            pass
        return files

    def clean(self, items: List[JunkItem], dry_run: bool = True) -> CleanReport:
        """清理给定的垃圾项。

        dry_run=True 时只统计不删除。
        注意:对目录类缓存,清理的是目录内容而非目录本身。
        """
        report = CleanReport()
        report.scanned = len(items)
        report.items = items
        report.total_size = sum(i.size for i in items)

        for item in items:
            p = Path(item.path)
            # 日志类:只删旧日志文件,保留目录
            if item.category == "logs":
                old_files = self._collect_old_logs(p, days=7)
                for f in old_files:
                    if safe_remove(f["path"], dry_run=dry_run):
                        report.cleaned += 1
                        report.freed_bytes += f["size"]
                    else:
                        report.skipped += 1
                continue

            # 回收站/缓存目录:清空内容但保留目录
            if p.is_dir() and item.category in ("trash", "cache", "temp", "package-cache"):
                self._clear_dir_contents(p, dry_run=dry_run, report=report)
                continue

            # 其他:直接删除
            if safe_remove(item.path, dry_run=dry_run):
                report.cleaned += 1
                report.freed_bytes += item.size
            else:
                report.skipped += 1

        return report

    def _clear_dir_contents(self, directory: Path, dry_run: bool, report: CleanReport) -> None:
        """清空目录内容但保留目录本身。"""
        try:
            entries = list(directory.iterdir())
        except (OSError, PermissionError):
            report.skipped += 1
            return
        for entry in entries:
            size = dir_size(entry) if entry.is_dir() else (
                entry.stat().st_size if entry.is_file() else 0
            )
            if safe_remove(entry, dry_run=dry_run):
                report.cleaned += 1
                report.freed_bytes += size
            else:
                report.skipped += 1
