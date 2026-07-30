"""软件列表与深度卸载模块。

跨平台支持:
- Linux: 解析 .desktop 文件 + dpkg/snap/flatpak 包信息
- Windows: 读取注册表 Uninstall 项
- macOS: 扫描 /Applications 与 ~/Applications

深度卸载流程:运行官方卸载程序 -> 扫描残留(配置/缓存/数据目录) -> 清理残留。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .utils import dir_size, expand_user, format_bytes, name_matches, normalize_name, safe_remove


@dataclass
class Software:
    """代表一个已安装的软件条目。"""

    name: str
    version: str = ""
    publisher: str = ""
    install_location: str = ""
    uninstall_string: str = ""
    install_date: str = ""
    size: int = 0
    source: str = ""  # 来源:desktop / dpkg / registry / apps
    package: str = ""  # 包管理器包名(若有)

    @property
    def size_text(self) -> str:
        return format_bytes(self.size) if self.size else "-"


@dataclass
class Leftover:
    """卸载后残留的文件或目录。"""

    path: str
    kind: str  # config / cache / data / registry
    size: int = 0

    @property
    def size_text(self) -> str:
        return format_bytes(self.size) if self.size else "-"


@dataclass
class UninstallResult:
    """卸载操作的结果汇总。"""

    name: str
    uninstalled: bool = False
    leftovers: List[Leftover] = field(default_factory=list)
    cleaned: int = 0
    freed_bytes: int = 0
    message: str = ""


class Uninstaller:
    """列出已安装软件、执行深度卸载、扫描残留。"""

    # 残留扫描的常见目录模板(支持 ~ 展开)
    LEFTOVER_DIRS = [
        "~/.config/{name}",
        "~/.cache/{name}",
        "~/.local/share/{name}",
        "~/.local/state/{name}",
    ]

    def list_software(self) -> List[Software]:
        """列出当前平台已安装的软件。"""
        if sys.platform == "win32":
            return self._list_windows()
        if sys.platform == "darwin":
            return self._list_macos()
        return self._list_linux()

    # ---------------- Linux ----------------

    def _list_linux(self) -> List[Software]:
        apps: dict[str, Software] = {}

        # 1) 解析 .desktop 文件(用户级 + 系统级)
        desktop_dirs = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path(expand_user("~/.local/share/applications")),
            Path("/var/lib/flatpak/exports/share/applications"),
            Path(expand_user("~/.local/share/flatpak/exports/share/applications")),
        ]
        for d in desktop_dirs:
            if not d.is_dir():
                continue
            for desktop_file in d.glob("*.desktop"):
                sw = self._parse_desktop(desktop_file)
                if sw and sw.name not in apps:
                    apps[sw.name] = sw

        # 2) 补充 dpkg 包信息(版本 + 大小)
        pkg_info = self._dpkg_info()
        for sw in list(apps.values()):
            if not sw.version and pkg_info:
                # 用 Exec 路径反查所属包
                pkg = self._dpkg_search(sw.install_location) if sw.install_location else None
                if pkg and pkg in pkg_info:
                    info = pkg_info[pkg]
                    sw.package = pkg
                    sw.version = sw.version or info.get("version", "")
                    sw.publisher = sw.publisher or info.get("maintainer", "")
                    sw.size = sw.size or info.get("size", 0)

        # 3) snap / flatpak 应用补全
        for sw in self._snap_apps():
            if sw.name not in apps:
                apps[sw.name] = sw
        for sw in self._flatpak_apps():
            if sw.name not in apps:
                apps[sw.name] = sw

        return sorted(apps.values(), key=lambda s: s.name.lower())

    def _parse_desktop(self, path: Path) -> Optional[Software]:
        """解析单个 .desktop 文件。"""
        name = version = publisher = ""
        exec_cmd = install_loc = ""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        if "[Desktop Entry]" not in content:
            return None
        for line in content.splitlines():
            if line.startswith("Name="):
                name = line.split("=", 1)[1].strip()
            elif line.startswith("X-AppInstall-Version=") or line.startswith("Version="):
                if not version:
                    version = line.split("=", 1)[1].strip()
            elif line.startswith("Exec="):
                exec_cmd = line.split("=", 1)[1].strip()
        if not name:
            name = path.stem
        if exec_cmd:
            # 取可执行路径作为 install_location 线索
            install_loc = exec_cmd.split()[0] if exec_cmd else ""
        return Software(
            name=name,
            version=version,
            publisher=publisher,
            install_location=install_loc,
            source="desktop",
        )

    def _dpkg_info(self) -> dict:
        """读取 dpkg 已装包的版本/大小/维护者。"""
        info: dict[str, dict] = {}
        try:
            out = subprocess.run(
                ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Installed-Size}\t${Maintainer}\n"],
                capture_output=True, text=True, timeout=30, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return info
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            pkg, ver, size, maint = parts[0], parts[1], parts[2], parts[3]
            try:
                size_bytes = int(size) * 1024  # dpkg 用 KB
            except ValueError:
                size_bytes = 0
            info[pkg] = {"version": ver, "size": size_bytes, "maintainer": maint}
        return info

    def _dpkg_search(self, path: str) -> Optional[str]:
        """通过文件路径反查 dpkg 包名。"""
        if not path or not os.path.exists(path):
            return None
        try:
            out = subprocess.run(
                ["dpkg", "-S", path], capture_output=True, text=True, timeout=10, check=False
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if out.returncode != 0 or not out.stdout:
            return None
        first = out.stdout.splitlines()[0]
        pkg = first.split(":")[0].strip()
        return pkg or None

    def _snap_apps(self) -> List[Software]:
        """列出 snap 安装的应用。"""
        apps: List[Software] = []
        try:
            out = subprocess.run(
                ["snap", "list"], capture_output=True, text=True, timeout=15, check=False
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return apps
        if out.returncode != 0:
            return apps
        lines = out.stdout.splitlines()[1:]
        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            apps.append(Software(name=parts[0], version=parts[1], source="snap", package=parts[0]))
        return apps

    def _flatpak_apps(self) -> List[Software]:
        """列出 flatpak 安装的应用。"""
        apps: List[Software] = []
        try:
            out = subprocess.run(
                ["flatpak", "list", "--columns=application,version"],
                capture_output=True, text=True, timeout=15, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return apps
        if out.returncode != 0:
            return apps
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 1 and parts[0]:
                name = parts[0].split(".")[-1]
                apps.append(Software(
                    name=name, version=parts[1] if len(parts) > 1 else "",
                    source="flatpak", package=parts[0],
                ))
        return apps

    # ---------------- Windows ----------------

    def _list_windows(self) -> List[Software]:
        """读取注册表 Uninstall 项(含 64/32 位与用户级)。"""
        apps: dict[str, Software] = {}
        try:
            import winreg  # type: ignore
        except ImportError:
            return []

        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", 0),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0),
        ]
        for root, subpath, flags in roots:
            try:
                with winreg.OpenKey(root, subpath, 0, winreg.KEY_READ | flags) as key:
                    for i in range(0, winreg.QueryInfoKey(key)[0]):
                        try:
                            subname = winreg.EnumKey(key, i)
                            sw = self._read_reg_subkey(root, f"{subpath}\\{subname}", flags)
                            if sw and sw.name and sw.name not in apps:
                                apps[sw.name] = sw
                        except OSError:
                            continue
            except OSError:
                continue
        return sorted(apps.values(), key=lambda s: s.name.lower())

    def _read_reg_subkey(self, root, path: str, flags: int) -> Optional[Software]:
        import winreg  # type: ignore
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_READ | flags) as key:
                def get(name):
                    try:
                        val, _ = winreg.QueryValueEx(key, name)
                        return str(val)
                    except OSError:
                        return ""
                name = get("DisplayName")
                if not name:
                    return None
                size_str = get("EstimatedSize")
                try:
                    size = int(size_str) * 1024 if size_str else 0
                except ValueError:
                    size = 0
                return Software(
                    name=name,
                    version=get("DisplayVersion"),
                    publisher=get("Publisher"),
                    install_location=get("InstallLocation"),
                    uninstall_string=get("UninstallString"),
                    install_date=get("InstallDate"),
                    size=size,
                    source="registry",
                )
        except OSError:
            return None

    # ---------------- macOS ----------------

    def _list_macos(self) -> List[Software]:
        apps: List[Software] = []
        for base in ("/Applications", expand_user("~/Applications")):
            base_path = Path(base)
            if not base_path.is_dir():
                continue
            for entry in base_path.glob("*.app"):
                info_plist = entry / "Contents" / "Info.plist"
                version = ""
                if info_plist.exists():
                    version = self._read_plist_version(info_plist)
                apps.append(Software(
                    name=entry.stem,
                    version=version,
                    install_location=str(entry),
                    uninstall_string=f"rm -rf '{entry}'",
                    size=dir_size(entry),
                    source="apps",
                ))
        return sorted(apps, key=lambda s: s.name.lower())

    def _read_plist_version(self, path: Path) -> str:
        try:
            import plistlib
            with path.open("rb") as f:
                data = plistlib.load(f)
            return str(data.get("CFBundleShortVersionString", "")
                       or data.get("CFBundleVersion", ""))
        except Exception:
            return ""

    # ---------------- 卸载与残留 ----------------

    def find(self, name: str, software_list: Optional[List[Software]] = None) -> Optional[Software]:
        """按名称模糊查找已安装软件。"""
        if software_list is None:
            software_list = self.list_software()
        for sw in software_list:
            if name_matches(sw.name, name):
                return sw
        return None

    def uninstall(self, sw: Software, dry_run: bool = True) -> UninstallResult:
        """执行卸载:先调用官方卸载程序,再扫描并清理残留。

        dry_run=True 时只报告将要做什么,不实际删除。
        """
        result = UninstallResult(name=sw.name)
        ran_uninstaller = False

        # 1) 调用官方卸载程序(若有)
        if sw.uninstall_string:
            ran_uninstaller = self._run_uninstall_string(sw.uninstall_string, dry_run)
            result.uninstalled = ran_uninstaller
        elif sw.package:
            # 没有卸载字符串但有包名 -> 用包管理器卸载
            ran_uninstaller = self._run_pkg_uninstall(sw, dry_run)
            result.uninstalled = ran_uninstaller

        if not ran_uninstaller and not sw.uninstall_string and not sw.package:
            result.message = "未找到卸载程序,仅执行残留扫描"

        # 2) 扫描残留
        result.leftovers = self.scan_leftovers(sw.name)

        # 3) 清理残留
        if result.leftovers and not dry_run:
            for lf in result.leftovers:
                if safe_remove(lf.path, dry_run=False):
                    result.cleaned += 1
                    result.freed_bytes += lf.size

        result.message = result.message or (
            "卸载完成" if ran_uninstaller else "未运行卸载程序"
        )
        return result

    def _run_uninstall_string(self, uninstall_string: str, dry_run: bool) -> bool:
        """执行注册表/桌面文件中的卸载命令。"""
        cmd = uninstall_string.strip()
        # 处理 MSI 安装包
        if cmd.lower().startswith("msiexec"):
            cmd = cmd.replace("/I", "/X").replace("/i", "/X")
            cmd = cmd + " /quiet /norestart"
        if dry_run:
            return True
        try:
            subprocess.run(cmd, shell=True, check=False, timeout=600)
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _run_pkg_uninstall(self, sw: Software, dry_run: bool) -> bool:
        """通过包管理器卸载(dpkg/snap/flatpak)。"""
        if dry_run:
            return True
        pkg = sw.package
        if sw.source == "snap":
            cmd = ["snap", "remove", pkg]
        elif sw.source == "flatpak":
            cmd = ["flatpak", "uninstall", "-y", pkg]
        elif pkg:
            cmd = ["dpkg", "--remove", pkg]
        else:
            return False
        try:
            subprocess.run(cmd, check=False, timeout=600)
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False

    def scan_leftovers(self, name: str) -> List[Leftover]:
        """扫描指定软件名在常见用户目录下的残留。"""
        leftovers: List[Leftover] = []
        if not name:
            return leftovers

        # 关键字变体:原名、归一化名、首词
        keywords = {name, normalize_name(name)}
        parts = re.split(r"[\s\-_.]+", name)
        if len(parts) > 1 and len(parts[0]) >= 3:
            keywords.add(parts[0])

        scan_roots = [
            ("config", expand_user("~/.config")),
            ("cache", expand_user("~/.cache")),
            ("data", expand_user("~/.local/share")),
            ("state", expand_user("~/.local/state")),
        ]
        if sys.platform == "darwin":
            scan_roots = [
                ("config", expand_user("~/Library/Application Support")),
                ("cache", expand_user("~/Library/Caches")),
                ("prefs", expand_user("~/Library/Preferences")),
                ("data", expand_user("~/Library/Application Support")),
            ]
        elif sys.platform == "win32":
            scan_roots = [
                ("config", expand_user(r"%APPDATA%")),
                ("cache", expand_user(r"%LOCALAPPDATA%")),
                ("data", expand_user(r"%LOCALAPPDATA%")),
            ]

        for kind, root in scan_roots:
            root_path = Path(root)
            if not root_path.is_dir():
                continue
            try:
                for entry in root_path.iterdir():
                    if not entry.name:
                        continue
                    if any(name_matches(entry.name, kw) for kw in keywords):
                        size = dir_size(entry) if entry.is_dir() else (
                            entry.stat().st_size if entry.is_file() else 0
                        )
                        leftovers.append(Leftover(path=str(entry), kind=kind, size=size))
            except (OSError, PermissionError):
                continue

        # Windows:额外扫描注册表残留项
        if sys.platform == "win32":
            leftovers.extend(self._scan_registry_leftovers(name))

        return leftovers

    def _scan_registry_leftovers(self, name: str) -> List[Leftover]:
        leftovers: List[Leftover] = []
        try:
            import winreg  # type: ignore
        except ImportError:
            return leftovers
        targets = [
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
        ]
        for root, sub in targets:
            try:
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subname = winreg.EnumKey(key, i)
                        except OSError:
                            break
                        if name_matches(subname, name):
                            leftovers.append(Leftover(
                                path=f"HKLM\\{sub}\\{subname}" if root == winreg.HKEY_LOCAL_MACHINE else f"HKCU\\{sub}\\{subname}",
                                kind="registry", size=0,
                            ))
            except OSError:
                continue
        return leftovers

    def clean_leftovers(self, leftovers: List[Leftover], dry_run: bool = True) -> tuple[int, int]:
        """清理残留项,返回 (清理数量, 释放字节数)。"""
        cleaned = 0
        freed = 0
        for lf in leftovers:
            if lf.kind == "registry":
                continue  # 注册表项需单独处理,这里跳过避免误删
            if safe_remove(lf.path, dry_run=dry_run):
                cleaned += 1
                freed += lf.size
        return cleaned, freed
