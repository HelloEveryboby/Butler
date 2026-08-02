# -*- coding: utf-8 -*-
"""跨平台 OS 命令适配器.

支持在 Butler TUI/GUI 中直接输入 Linux/Windows/macOS 原生命令,
自动检测操作系统并路由到对应实现。

设计理念:
  - Linux 命令 (ls, cat, grep, find...) 在所有平台上可用
  - Windows 命令 (dir, type, findstr...) 在 Windows 上原生执行
  - macOS 专属命令 (open, pbcopy, say...) 在 macOS 上原生执行
  - 统一映射: 输入 ls 在 Windows 上自动转为 dir, 反之亦然
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import platform
from dataclasses import dataclass
from typing import Optional


# ── 操作系统检测 ─────────────────────────────────────────────

def detect_os() -> str:
    """返回当前操作系统: 'linux', 'windows', 'macos'."""
    s = platform.system().lower()
    if s == "windows":
        return "windows"
    elif s == "darwin":
        return "macos"
    return "linux"


CURRENT_OS = detect_os()


# ── 跨平台命令映射表 ──────────────────────────────────────────
# 逻辑命令名 → 各平台的实际命令
# 用户输入逻辑名, 适配器自动转为当前平台的命令

COMMAND_MAP: dict[str, dict[str, list[str]]] = {
    # ── 文件操作 ──
    "ls": {
        "linux":   ["ls"],
        "windows": ["cmd", "/c", "dir"],
        "macos":   ["ls"],
    },
    "ll": {  # ls -l 的别名
        "linux":   ["ls", "-la"],
        "windows": ["cmd", "/c", "dir"],
        "macos":   ["ls", "-la"],
    },
    "cat": {
        "linux":   ["cat"],
        "windows": ["cmd", "/c", "type"],
        "macos":   ["cat"],
    },
    "cp": {
        "linux":   ["cp"],
        "windows": ["cmd", "/c", "copy"],
        "macos":   ["cp"],
    },
    "mv": {
        "linux":   ["mv"],
        "windows": ["cmd", "/c", "move"],
        "macos":   ["mv"],
    },
    "rm": {
        "linux":   ["rm"],
        "windows": ["cmd", "/c", "del"],
        "macos":   ["rm"],
    },
    "rmdir": {
        "linux":   ["rmdir"],
        "windows": ["cmd", "/c", "rmdir", "/s", "/q"],
        "macos":   ["rmdir"],
    },
    "mkdir": {
        "linux":   ["mkdir", "-p"],
        "windows": ["cmd", "/c", "mkdir"],
        "macos":   ["mkdir", "-p"],
    },
    "touch": {
        "linux":   ["touch"],
        "windows": ["cmd", "/c", "type", "nul"],
        "macos":   ["touch"],
    },
    "pwd": {
        "linux":   ["pwd"],
        "windows": ["cmd", "/c", "cd"],
        "macos":   ["pwd"],
    },
    "cd": {
        "linux":   ["cd"],
        "windows": ["cmd", "/c", "cd"],
        "macos":   ["cd"],
    },
    "chmod": {
        "linux":   ["chmod"],
        "windows": ["cmd", "/c", "icacls"],  # Windows 近似
        "macos":   ["chmod"],
    },
    "chown": {
        "linux":   ["chown"],
        "windows": ["cmd", "/c", "icacls"],
        "macos":   ["chown"],
    },
    "ln": {
        "linux":   ["ln", "-s"],
        "windows": ["cmd", "/c", "mklink"],
        "macos":   ["ln", "-s"],
    },

    # ── 文件查看/编辑 ──
    "head": {
        "linux":   ["head"],
        "windows": ["cmd", "/c", "more"],  # 近似
        "macos":   ["head"],
    },
    "tail": {
        "linux":   ["tail"],
        "windows": ["cmd", "/c", "more"],
        "macos":   ["tail"],
    },
    "less": {
        "linux":   ["less"],
        "windows": ["cmd", "/c", "more"],
        "macos":   ["less"],
    },
    "wc": {
        "linux":   ["wc"],
        "windows": ["cmd", "/c", "find", "/c", "/v", ""],  # 行数近似
        "macos":   ["wc"],
    },
    "diff": {
        "linux":   ["diff"],
        "windows": ["cmd", "/c", "fc"],
        "macos":   ["diff"],
    },
    "file": {
        "linux":   ["file"],
        "windows": ["cmd", "/c", "dir"],  # 近似
        "macos":   ["file"],
    },
    "stat": {
        "linux":   ["stat"],
        "windows": ["cmd", "/c", "dir"],
        "macos":   ["stat"],
    },
    "du": {
        "linux":   ["du", "-sh"],
        "windows": ["cmd", "/c", "dir"],
        "macos":   ["du", "-sh"],
    },
    "df": {
        "linux":   ["df", "-h"],
        "windows": ["cmd", "/c", "wmic", "logicaldisk", "get"],
        "macos":   ["df", "-h"],
    },

    # ── 搜索 ──
    "find": {
        "linux":   ["find"],
        "windows": ["cmd", "/c", "dir", "/s", "/b"],
        "macos":   ["find"],
    },
    "locate": {
        "linux":   ["locate"],
        "windows": ["cmd", "/c", "where"],
        "macos":   ["mdfind"],  # macOS 用 mdfind
    },
    "which": {
        "linux":   ["which"],
        "windows": ["cmd", "/c", "where"],
        "macos":   ["which"],
    },
    "whereis": {
        "linux":   ["whereis"],
        "windows": ["cmd", "/c", "where"],
        "macos":   ["whereis"],
    },
    "grep": {
        "linux":   ["grep"],
        "windows": ["cmd", "/c", "findstr"],
        "macos":   ["grep"],
    },
    "rg": {  # ripgrep (如果安装了)
        "linux":   ["rg"],
        "windows": ["rg"],
        "macos":   ["rg"],
    },

    # ── 进程管理 ──
    "ps": {
        "linux":   ["ps", "aux"],
        "windows": ["cmd", "/c", "tasklist"],
        "macos":   ["ps", "aux"],
    },
    "top": {
        "linux":   ["top", "-b", "-n", "1"],
        "windows": ["cmd", "/c", "tasklist"],
        "macos":   ["top", "-l", "1"],
    },
    "kill": {
        "linux":   ["kill"],
        "windows": ["cmd", "/c", "taskkill", "/pid"],
        "macos":   ["kill"],
    },
    "killall": {
        "linux":   ["killall"],
        "windows": ["cmd", "/c", "taskkill", "/im"],
        "macos":   ["killall"],
    },
    "jobs": {
        "linux":   ["jobs"],
        "windows": ["cmd", "/c", "tasklist"],
        "macos":   ["jobs"],
    },

    # ── 网络工具 ──
    "ping": {
        "linux":   ["ping", "-c", "4"],
        "windows": ["cmd", "/c", "ping", "-n", "4"],
        "macos":   ["ping", "-c", "4"],
    },
    "ifconfig": {
        "linux":   ["ifconfig"],
        "windows": ["cmd", "/c", "ipconfig"],
        "macos":   ["ifconfig"],
    },
    "ipconfig": {  # Windows 命令, 但在 Linux 上也支持
        "linux":   ["ip", "addr"],
        "windows": ["cmd", "/c", "ipconfig"],
        "macos":   ["ifconfig"],
    },
    "netstat": {
        "linux":   ["netstat", "-tlnp"],
        "windows": ["cmd", "/c", "netstat", "-ano"],
        "macos":   ["netstat", "-an"],
    },
    "ss": {  # 现代 Linux 替代 netstat
        "linux":   ["ss", "-tlnp"],
        "windows": ["cmd", "/c", "netstat", "-ano"],
        "macos":   ["netstat", "-an"],
    },
    "curl": {
        "linux":   ["curl"],
        "windows": ["curl"],
        "macos":   ["curl"],
    },
    "wget": {
        "linux":   ["wget"],
        "windows": ["cmd", "/c", "curl", "-O"],  # 近似
        "macos":   ["curl", "-O"],
    },
    "ssh": {
        "linux":   ["ssh"],
        "windows": ["ssh"],
        "macos":   ["ssh"],
    },
    "scp": {
        "linux":   ["scp"],
        "windows": ["scp"],
        "macos":   ["scp"],
    },
    "nslookup": {
        "linux":   ["nslookup"],
        "windows": ["cmd", "/c", "nslookup"],
        "macos":   ["nslookup"],
    },
    "dig": {
        "linux":   ["dig"],
        "windows": ["cmd", "/c", "nslookup"],  # Windows 无 dig
        "macos":   ["dig"],
    },
    "traceroute": {
        "linux":   ["traceroute"],
        "windows": ["cmd", "/c", "tracert"],
        "macos":   ["traceroute"],
    },
    "arp": {
        "linux":   ["arp", "-a"],
        "windows": ["cmd", "/c", "arp", "-a"],
        "macos":   ["arp", "-a"],
    },

    # ── 系统信息 ──
    "uname": {
        "linux":   ["uname", "-a"],
        "windows": ["cmd", "/c", "ver"],
        "macos":   ["uname", "-a"],
    },
    "uptime": {
        "linux":   ["uptime"],
        "windows": ["cmd", "/c", "net", "statistics", "workstation"],
        "macos":   ["uptime"],
    },
    "free": {
        "linux":   ["free", "-h"],
        "windows": ["cmd", "/c", "wmic", "OS", "get", "FreePhysicalMemory"],
        "macos":   ["vm_stat"],
    },
    "lscpu": {
        "linux":   ["lscpu"],
        "windows": ["cmd", "/c", "wmic", "cpu", "get"],
        "macos":   ["sysctl", "-n", "machdep.cpu.brand_string"],
    },
    "lspci": {
        "linux":   ["lspci"],
        "windows": ["cmd", "/c", "wmic", "path", "win32_pnpentity"],
        "macos":   ["system_profiler", "SPHardwareDataType"],
    },
    "lsusb": {
        "linux":   ["lsusb"],
        "windows": ["cmd", "/c", "wmic", "path", "Win32_USBHub"],
        "macos":   ["system_profiler", "SPUSBDataType"],
    },
    "dmesg": {
        "linux":   ["dmesg"],
        "windows": ["cmd", "/c", "wevtutil", "qe", "System"],
        "macos":   ["log", "show"],
    },
    "whoami": {
        "linux":   ["whoami"],
        "windows": ["cmd", "/c", "whoami"],
        "macos":   ["whoami"],
    },
    "who": {
        "linux":   ["who"],
        "windows": ["cmd", "/c", "query", "user"],
        "macos":   ["who"],
    },
    "env": {
        "linux":   ["env"],
        "windows": ["cmd", "/c", "set"],
        "macos":   ["env"],
    },
    "hostname": {
        "linux":   ["hostname"],
        "windows": ["cmd", "/c", "hostname"],
        "macos":   ["hostname"],
    },
    "date": {
        "linux":   ["date"],
        "windows": ["cmd", "/c", "date", "/t"],
        "macos":   ["date"],
    },
    "cal": {
        "linux":   ["cal"],
        "windows": ["cmd", "/c", "date", "/t"],  # Windows 无 cal
        "macos":   ["cal"],
    },
    "time": {
        "linux":   ["time"],
        "windows": ["cmd", "/c", "time", "/t"],
        "macos":   ["time"],
    },
    "history": {
        "linux":   ["history"],
        "windows": ["cmd", "/c", "doskey", "/history"],
        "macos":   ["history"],
    },

    # ── 包管理 ──
    "apt": {
        "linux":   ["apt"],
        "windows": ["cmd", "/c", "winget"],
        "macos":   ["brew"],
    },
    "brew": {
        "linux":   ["brew"],  # Linuxbrew
        "windows": ["cmd", "/c", "winget"],
        "macos":   ["brew"],
    },
    "pip": {
        "linux":   ["pip"],
        "windows": ["pip"],
        "macos":   ["pip3"],
    },

    # ── 压缩/归档 ──
    "tar": {
        "linux":   ["tar"],
        "windows": ["tar"],  # Win10+ 自带
        "macos":   ["tar"],
    },
    "zip": {
        "linux":   ["zip"],
        "windows": ["cmd", "/c", "tar", "-a", "-c", "-f"],  # 近似
        "macos":   ["zip"],
    },
    "unzip": {
        "linux":   ["unzip"],
        "windows": ["cmd", "/c", "tar", "-x", "-f"],
        "macos":   ["unzip"],
    },
    "gzip": {
        "linux":   ["gzip"],
        "windows": ["cmd", "/c", "tar", "-a", "-c", "-f"],
        "macos":   ["gzip"],
    },

    # ── macOS 专属 ──
    "open": {
        "linux":   ["xdg-open"],
        "windows": ["cmd", "/c", "start"],
        "macos":   ["open"],
    },
    "pbcopy": {
        "linux":   ["xclip", "-selection", "clipboard"],
        "windows": ["cmd", "/c", "clip"],
        "macos":   ["pbcopy"],
    },
    "pbpaste": {
        "linux":   ["xclip", "-selection", "clipboard", "-o"],
        "windows": ["cmd", "/c", "powershell", "-command", "Get-Clipboard"],
        "macos":   ["pbpaste"],
    },
    "say": {
        "linux":   ["espeak"],
        "windows": ["cmd", "/c", "powershell", "-command",
                     "Add-Type", "-AssemblyName", "System.Speech"],
        "macos":   ["say"],
    },
    "defaults": {
        "linux":   ["echo", "(macOS only)"],
        "windows": ["echo", "(macOS only)"],
        "macos":   ["defaults"],
    },

    # ── Windows 专属 (也支持在 Linux 上用) ──
    "dir": {
        "linux":   ["ls", "-la"],
        "windows": ["cmd", "/c", "dir"],
        "macos":   ["ls", "-la"],
    },
    "type": {
        "linux":   ["cat"],
        "windows": ["cmd", "/c", "type"],
        "macos":   ["cat"],
    },
    "copy": {
        "linux":   ["cp"],
        "windows": ["cmd", "/c", "copy"],
        "macos":   ["cp"],
    },
    "move": {
        "linux":   ["mv"],
        "windows": ["cmd", "/c", "move"],
        "macos":   ["mv"],
    },
    "del": {
        "linux":   ["rm"],
        "windows": ["cmd", "/c", "del"],
        "macos":   ["rm"],
    },
    "tasklist": {
        "linux":   ["ps", "aux"],
        "windows": ["cmd", "/c", "tasklist"],
        "macos":   ["ps", "aux"],
    },
    "taskkill": {
        "linux":   ["kill"],
        "windows": ["cmd", "/c", "taskkill"],
        "macos":   ["kill"],
    },
    "ipconfig": {
        "linux":   ["ip", "addr"],
        "windows": ["cmd", "/c", "ipconfig"],
        "macos":   ["ifconfig"],
    },
    "systeminfo": {
        "linux":   ["uname", "-a"],
        "windows": ["cmd", "/c", "systeminfo"],
        "macos":   ["system_profiler"],
    },
    "where": {
        "linux":   ["which"],
        "windows": ["cmd", "/c", "where"],
        "macos":   ["which"],
    },
    "findstr": {
        "linux":   ["grep"],
        "windows": ["cmd", "/c", "findstr"],
        "macos":   ["grep"],
    },
    "clip": {
        "linux":   ["xclip", "-selection", "clipboard"],
        "windows": ["cmd", "/c", "clip"],
        "macos":   ["pbcopy"],
    },

    # ── 文本处理 ──
    "echo": {
        "linux":   ["echo"],
        "windows": ["cmd", "/c", "echo"],
        "macos":   ["echo"],
    },
    "printf": {
        "linux":   ["printf"],
        "windows": ["cmd", "/c", "echo"],
        "macos":   ["printf"],
    },
    "sed": {
        "linux":   ["sed"],
        "windows": ["cmd", "/c", "powershell", "-command"],  # 近似
        "macos":   ["sed"],
    },
    "awk": {
        "linux":   ["awk"],
        "windows": ["cmd", "/c", "powershell", "-command"],
        "macos":   ["awk"],
    },
    "sort": {
        "linux":   ["sort"],
        "windows": ["cmd", "/c", "sort"],
        "macos":   ["sort"],
    },
    "uniq": {
        "linux":   ["uniq"],
        "windows": ["cmd", "/c", "powershell", "-command", "Get-Unique"],
        "macos":   ["uniq"],
    },
    "cut": {
        "linux":   ["cut"],
        "windows": ["cmd", "/c", "powershell", "-command"],
        "macos":   ["cut"],
    },
    "tr": {
        "linux":   ["tr"],
        "windows": ["cmd", "/c", "powershell", "-command"],
        "macos":   ["tr"],
    },
    "tee": {
        "linux":   ["tee"],
        "windows": ["cmd", "/c", "powershell", "-command", "Tee-Object"],
        "macos":   ["tee"],
    },
    "xargs": {
        "linux":   ["xargs"],
        "windows": ["cmd", "/c", "powershell", "-command"],
        "macos":   ["xargs"],
    },
    "jq": {
        "linux":   ["jq"],
        "windows": ["jq"],
        "macos":   ["jq"],
    },

    # ── Git ──
    "git": {
        "linux":   ["git"],
        "windows": ["git"],
        "macos":   ["git"],
    },

    # ── 其他 ──
    "man": {
        "linux":   ["man"],
        "windows": ["cmd", "/c", "help"],
        "macos":   ["man"],
    },
    "clear": {
        "linux":   ["clear"],
        "windows": ["cmd", "/c", "cls"],
        "macos":   ["clear"],
    },
    "exit": {
        "linux":   ["exit"],
        "windows": ["cmd", "/c", "exit"],
        "macos":   ["exit"],
    },
    "sleep": {
        "linux":   ["sleep"],
        "windows": ["cmd", "/c", "timeout"],
        "macos":   ["sleep"],
    },
    "watch": {
        "linux":   ["watch"],
        "windows": ["cmd", "/c", "powershell", "-command"],
        "macos":   ["watch"],
    },
    "nohup": {
        "linux":   ["nohup"],
        "windows": ["cmd", "/c", "start", "/b"],
        "macos":   ["nohup"],
    },
    "sudo": {
        "linux":   ["sudo"],
        "windows": ["cmd", "/c", "runas"],  # 近似
        "macos":   ["sudo"],
    },
    "systemctl": {
        "linux":   ["systemctl"],
        "windows": ["cmd", "/c", "sc"],  # Windows 服务
        "macos":   ["launchctl"],
    },
    "crontab": {
        "linux":   ["crontab"],
        "windows": ["cmd", "/c", "schtasks"],
        "macos":   ["crontab"],
    },
}


@dataclass
class OSCommandResult:
    """OS 命令执行结果."""
    success: bool
    output: str
    command_used: str       # 实际执行的命令
    original_input: str     # 用户原始输入
    os_detected: str        # 检测到的操作系统


def is_os_command(cmd_name: str) -> bool:
    """判断给定的命令名是否是已知的 OS 命令."""
    return cmd_name.lower() in COMMAND_MAP


def resolve_command(cmd_name: str) -> list[str] | None:
    """将逻辑命令名解析为当前平台的实际命令列表.

    返回 None 表示未知命令。
    """
    entry = COMMAND_MAP.get(cmd_name.lower())
    if not entry:
        return None
    platform_cmds = entry.get(CURRENT_OS) or entry.get("linux")
    if not platform_cmds:
        return None
    return platform_cmds


def execute_os_command(
    cmd_name: str,
    args: list[str],
    cwd: str | None = None,
    timeout: int = 30,
) -> OSCommandResult:
    """执行 OS 原生命令.

    Args:
        cmd_name: 逻辑命令名 (如 "ls", "cat", "dir")
        args: 额外参数
        cwd: 工作目录
        timeout: 超时秒数

    Returns:
        OSCommandResult
    """
    base_cmd = resolve_command(cmd_name)
    if base_cmd is None:
        return OSCommandResult(
            success=False,
            output=f"未知命令: {cmd_name}",
            command_used="",
            original_input=cmd_name,
            os_detected=CURRENT_OS,
        )

    # 合并基础命令和用户参数
    full_cmd = base_cmd + args
    cmd_str = " ".join(full_cmd)

    # 检查命令是否存在 (跳过 Windows cmd 内置命令)
    check_cmd = full_cmd[0] if full_cmd[0] not in ("cmd",) else None
    if check_cmd and not shutil.which(check_cmd) and CURRENT_OS != "windows":
        return OSCommandResult(
            success=False,
            output=f"命令未安装: {full_cmd[0]}\n尝试安装: apt install {full_cmd[0]} 或 brew install {full_cmd[0]}",
            command_used=cmd_str,
            original_input=cmd_name,
            os_detected=CURRENT_OS,
        )

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            shell=False,
        )
        output = result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        if not output.strip():
            output = "(无输出)"
        return OSCommandResult(
            success=result.returncode == 0,
            output=output.rstrip(),
            command_used=cmd_str,
            original_input=f"{cmd_name} {' '.join(args)}".strip(),
            os_detected=CURRENT_OS,
        )
    except subprocess.TimeoutExpired:
        return OSCommandResult(
            success=False,
            output=f"命令超时 ({timeout}s): {cmd_str}",
            command_used=cmd_str,
            original_input=cmd_name,
            os_detected=CURRENT_OS,
        )
    except FileNotFoundError:
        return OSCommandResult(
            success=False,
            output=f"命令未找到: {full_cmd[0]}\n在 {CURRENT_OS} 上可能需要安装。",
            command_used=cmd_str,
            original_input=cmd_name,
            os_detected=CURRENT_OS,
        )
    except Exception as e:
        return OSCommandResult(
            success=False,
            output=f"执行错误: {e}",
            command_used=cmd_str,
            original_input=cmd_name,
            os_detected=CURRENT_OS,
        )


def list_os_commands(category: str | None = None) -> str:
    """列出所有支持的 OS 命令, 按分类."""
    categories = {
        "📁 文件操作": ["ls", "ll", "cat", "cp", "mv", "rm", "mkdir", "rmdir",
                       "touch", "pwd", "cd", "ln", "chmod", "chown"],
        "🔍 搜索": ["find", "locate", "which", "whereis", "grep", "rg",
                    "findstr", "where", "dir"],
        "📊 进程": ["ps", "top", "kill", "killall", "tasklist", "taskkill", "jobs"],
        "🌐 网络": ["ping", "ifconfig", "ipconfig", "netstat", "ss", "curl",
                    "wget", "ssh", "scp", "nslookup", "dig", "traceroute", "arp"],
        "💻 系统": ["uname", "uptime", "free", "lscpu", "lspci", "lsusb",
                    "dmesg", "whoami", "who", "env", "hostname", "date", "cal",
                    "systeminfo", "ver"],
        "📝 文本": ["echo", "printf", "sed", "awk", "sort", "uniq", "cut",
                    "tr", "tee", "xargs", "jq", "wc", "diff", "head", "tail"],
        "📦 包管理": ["apt", "brew", "pip", "winget"],
        "🗜️ 压缩": ["tar", "zip", "unzip", "gzip"],
        "🍎 macOS": ["open", "pbcopy", "pbpaste", "say", "defaults"],
        "🪟 Windows": ["dir", "type", "copy", "move", "del", "tasklist",
                       "taskkill", "ipconfig", "systeminfo", "where", "findstr", "clip"],
        "⚙️ 服务": ["systemctl", "crontab", "sudo", "nohup", "watch", "sleep"],
        "🔧 其他": ["git", "man", "clear", "exit", "history"],
    }

    lines = [f"支持 {len(COMMAND_MAP)} 个跨平台 OS 命令 (当前系统: {CURRENT_OS})\n"]

    for cat, cmds in categories.items():
        if category and category.lower() not in cat.lower():
            continue
        lines.append(f"\n{cat}:")
        for cmd in cmds:
            if cmd in COMMAND_MAP:
                resolved = resolve_command(cmd)
                resolved_str = " ".join(resolved) if resolved else "N/A"
                lines.append(f"  {cmd:<14} → {resolved_str}")

    lines.append(f"\n提示: 这些命令支持管道 | 和重定向 >")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  命令解释器 / 翻译器
# ══════════════════════════════════════════════════════════════════

# ── 常见参数跨平台翻译表 ──
#   参数语义 → {linux: 写法, windows: 写法, macos: 写法}
ARG_TRANSLATIONS: dict[str, dict[str, str]] = {
    "show_hidden": {
        "linux": "-a",
        "windows": "/a",
        "macos": "-a",
    },
    "long_format": {
        "linux": "-l",
        "windows": "/q",
        "macos": "-l",
    },
    "human_readable": {
        "linux": "-h",
        "windows": "",
        "macos": "-h",
    },
    "recursive": {
        "linux": "-r / -R",
        "windows": "/s",
        "macos": "-R",
    },
    "force": {
        "linux": "-f",
        "windows": "/f",
        "macos": "-f",
    },
    "verbose": {
        "linux": "-v",
        "windows": "/v",
        "macos": "-v",
    },
    "count": {
        "linux": "-n",
        "windows": "/n",
        "macos": "-c",
    },
    "portable": {
        "linux": "-p",
        "windows": "",
        "macos": "-p",
    },
}

# ── 命令参数映射: cmd_name → {常见参数选项} ──
COMMAND_ARG_HINTS: dict[str, dict[str, dict[str, str]]] = {
    "ls": {
        "-a":   {"desc": "显示隐藏文件",   "semantic": "show_hidden"},
        "-l":   {"desc": "详细格式",       "semantic": "long_format"},
        "-h":   {"desc": "人类可读大小",   "semantic": "human_readable"},
        "-la":  {"desc": "所有文件+详细",  "semantic": "show_hidden+long_format"},
        "-R":   {"desc": "递归子目录",     "semantic": "recursive"},
    },
    "grep": {
        "-i":   {"desc": "忽略大小写",     "semantic": "ignore_case"},
        "-r":   {"desc": "递归搜索",       "semantic": "recursive"},
        "-v":   {"desc": "反向匹配",       "semantic": "invert_match"},
        "-n":   {"desc": "显示行号",       "semantic": "show_line_num"},
        "-l":   {"desc": "仅显示文件名",   "semantic": "files_with_match"},
    },
    "find": {
        "-name":  {"desc": "按名称搜索",   "semantic": "by_name"},
        "-type":  {"desc": "按类型搜索",   "semantic": "by_type"},
        "-size":  {"desc": "按大小搜索",   "semantic": "by_size"},
        "-mtime": {"desc": "按修改时间",   "semantic": "by_mtime"},
    },
    "ps": {
        "aux":   {"desc": "所有进程+用户+资源", "semantic": "list_all"},
        "-ef":   {"desc": "全格式列表",     "semantic": "list_all"},
    },
    "kill": {
        "-9":   {"desc": "强制终止",       "semantic": "force"},
        "-TERM":{"desc": "优雅终止",       "semantic": "term"},
    },
    "ping": {
        "-c":   {"desc": "发送包数",       "semantic": "count"},
        "-n":   {"desc": "发送包数(Win)",  "semantic": "count"},
    },
    "curl": {
        "-O":   {"desc": "下载保存",       "semantic": "output_file"},
        "-o":   {"desc": "指定输出文件",   "semantic": "output_file"},
        "-s":   {"desc": "静默模式",       "semantic": "silent"},
        "-I":   {"desc": "仅请求头",       "semantic": "head_only"},
    },
    "tar": {
        "-c":   {"desc": "创建归档",       "semantic": "create"},
        "-x":   {"desc": "提取归档",       "semantic": "extract"},
        "-z":   {"desc": "gzip 压缩",      "semantic": "gzip"},
        "-f":   {"desc": "指定文件名",     "semantic": "file"},
        "-v":   {"desc": "显示详情",       "semantic": "verbose"},
        "-czf": {"desc": "创建 gzip 归档", "semantic": "create+gzip+file"},
        "-xzf": {"desc": "提取 gzip 归档", "semantic": "extract+gzip+file"},
    },
    "rm": {
        "-r":   {"desc": "递归删除目录",   "semantic": "recursive"},
        "-f":   {"desc": "强制不提示",     "semantic": "force"},
        "-rf":  {"desc": "递归强制删除",   "semantic": "recursive+force"},
    },
    "cp": {
        "-r":   {"desc": "递归拷贝目录",   "semantic": "recursive"},
        "-v":   {"desc": "显示详情",       "semantic": "verbose"},
    },
    "mv": {
        "-f":   {"desc": "强制覆盖",       "semantic": "force"},
        "-v":   {"desc": "显示详情",       "semantic": "verbose"},
    },
    "mkdir": {
        "-p":   {"desc": "递归创建父目录", "semantic": "parents"},
    },
    "chmod": {
        "-R":   {"desc": "递归修改",       "semantic": "recursive"},
        "+x":   {"desc": "添加执行权限",   "semantic": "exec"},
        "755":  {"desc": "rwxr-xr-x 权限", "semantic": "mode_755"},
    },
    "ssh": {
        "-p":   {"desc": "指定端口",       "semantic": "port"},
        "-i":   {"desc": "指定私钥",       "semantic": "identity"},
    },
    "scp": {
        "-r":   {"desc": "递归拷贝目录",   "semantic": "recursive"},
        "-P":   {"desc": "指定端口",       "semantic": "port"},
    },
    "head": {
        "-n":   {"desc": "指定行数",       "semantic": "count"},
    },
    "tail": {
        "-n":   {"desc": "指定行数",       "semantic": "count"},
        "-f":   {"desc": "实时追踪",       "semantic": "follow"},
    },
    "wc": {
        "-l":   {"desc": "统计行数",       "semantic": "lines"},
        "-w":   {"desc": "统计词数",       "semantic": "words"},
        "-c":   {"desc": "统计字节数",     "semantic": "bytes"},
    },
    "netstat": {
        "-tlnp":{"desc": "TCP监听+进程号", "semantic": "listening_tcp"},
        "-ano": {"desc": "全部连接+进程号(Win)", "semantic": "listening_all_win"},
    },
    "du": {
        "-sh":  {"desc": "当前目录总大小",  "semantic": "sum_human"},
        "-h":   {"desc": "人类可读",       "semantic": "human_readable"},
    },
    "df": {
        "-h":   {"desc": "人类可读",       "semantic": "human_readable"},
    },
}

# ── Windows 命令参数映射 ──
WIN_COMMAND_ARG_HINTS: dict[str, dict[str, dict[str, str]]] = {
    "dir": {
        "/a":   {"desc": "显示隐藏文件",    "semantic": "show_hidden"},
        "/s":   {"desc": "递归子目录",      "semantic": "recursive"},
        "/b":   {"desc": "仅文件名",        "semantic": "bare_format"},
        "/q":   {"desc": "显示所有者",      "semantic": "owner"},
    },
    "findstr": {
        "/i":   {"desc": "忽略大小写",      "semantic": "ignore_case"},
        "/s":   {"desc": "递归搜索",        "semantic": "recursive"},
        "/n":   {"desc": "显示行号",        "semantic": "show_line_num"},
        "/v":   {"desc": "反向匹配",        "semantic": "invert_match"},
    },
    "taskkill": {
        "/f":   {"desc": "强制终止",        "semantic": "force"},
        "/im":  {"desc": "按镜像名终止",    "semantic": "by_image_name"},
        "/pid": {"desc": "按 PID 终止",     "semantic": "by_pid"},
    },
    "tasklist": {
        "/v":   {"desc": "详细信息",        "semantic": "verbose"},
        "/svc": {"desc": "显示服务",        "semantic": "services"},
        "/fi":  {"desc": "过滤器",         "semantic": "filter"},
    },
    "ipconfig": {
        "/all": {"desc": "完整信息",        "semantic": "all_info"},
        "/flushdns": {"desc": "刷新 DNS",   "semantic": "flush_dns"},
        "/release": {"desc": "释放 IP",     "semantic": "release_ip"},
        "/renew":   {"desc": "续租 IP",     "semantic": "renew_ip"},
    },
    "systeminfo": {
        "/fo":  {"desc": "输出格式",        "semantic": "format"},
    },
    "copy": {
        "/y":   {"desc": "不提示覆盖",      "semantic": "force"},
        "/v":   {"desc": "校验",           "semantic": "verify"},
    },
    "move": {
        "/y":   {"desc": "不提示覆盖",      "semantic": "force"},
    },
    "del": {
        "/f":   {"desc": "强制删除只读",    "semantic": "force"},
        "/s":   {"desc": "递归删除子目录",  "semantic": "recursive"},
        "/q":   {"desc": "静默模式",        "semantic": "silent"},
    },
    "rmdir": {
        "/s":   {"desc": "递归删除目录树",  "semantic": "recursive"},
        "/q":   {"desc": "静默模式",        "semantic": "silent"},
    },
    "netstat": {
        "-ano": {"desc": "所有连接+PID",   "semantic": "listening_all"},
        "-a":   {"desc": "所有连接",        "semantic": "all"},
        "-n":   {"desc": "数字格式",        "semantic": "numeric"},
        "-o":   {"desc": "显示 PID",        "semantic": "show_pid"},
    },
}

# ── 命令功能描述字典 ──
COMMAND_DESCRIPTIONS: dict[str, str] = {
    "ls": "列出目录内容",
    "dir": "列出目录内容 (Windows 风格)",
    "cat": "查看文件内容",
    "type": "查看文件内容 (Windows 风格)",
    "cp": "复制文件或目录",
    "copy": "复制文件 (Windows 风格)",
    "mv": "移动/重命名文件",
    "move": "移动文件 (Windows 风格)",
    "rm": "删除文件或目录",
    "del": "删除文件 (Windows 风格)",
    "mkdir": "创建目录",
    "touch": "创建空文件或更新时间戳",
    "pwd": "显示当前工作目录",
    "cd": "切换目录",
    "ln": "创建链接",
    "chmod": "修改文件权限",
    "chown": "修改文件所有者",
    "grep": "文本/正则搜索",
    "findstr": "文本搜索 (Windows 风格)",
    "find": "按名称/类型/大小等搜索文件",
    "which": "查找命令所在路径",
    "where": "查找命令所在路径 (Windows 风格)",
    "whereis": "查找命令二进制+源码+man页",
    "locate": "快速在数据库中查找文件",
    "rg": "ripgrep 快速递归搜索",
    "ps": "列出当前进程",
    "tasklist": "列出进程 (Windows 风格)",
    "top": "实时查看进程资源占用",
    "kill": "按 PID 终止进程",
    "taskkill": "终止进程 (Windows 风格)",
    "killall": "按名称终止所有相关进程",
    "ping": "测试网络连通性",
    "ifconfig": "查看/配置网络接口",
    "ipconfig": "查看 IP 配置 (Windows 风格)",
    "netstat": "查看网络连接和端口",
    "ss": "查看套接字统计 (现代 Linux)",
    "curl": "命令行 HTTP 客户端",
    "wget": "命令行下载工具",
    "ssh": "SSH 远程登录",
    "scp": "SSH 远程文件拷贝",
    "nslookup": "DNS 查询",
    "dig": "DNS 查询 (高级)",
    "traceroute": "路由追踪",
    "tracert": "路由追踪 (Windows 风格)",
    "arp": "查看 ARP 表",
    "uname": "显示系统信息",
    "uptime": "显示开机时长和负载",
    "free": "显示内存使用情况",
    "lscpu": "显示 CPU 架构信息",
    "lspci": "显示 PCI 设备列表",
    "lsusb": "显示 USB 设备列表",
    "dmesg": "显示内核消息",
    "whoami": "显示当前用户名",
    "who": "显示当前登录用户",
    "env": "显示/设置环境变量",
    "hostname": "显示/设置主机名",
    "date": "显示/设置日期时间",
    "cal": "显示日历",
    "systeminfo": "显示完整系统信息 (Windows)",
    "echo": "输出文本到终端",
    "printf": "格式化输出",
    "sed": "流编辑器 (文本替换/删除/插入)",
    "awk": "文本处理与字段提取",
    "sort": "对文本行排序",
    "uniq": "去重相邻行",
    "cut": "按分隔符切割列",
    "tr": "字符集替换/删除",
    "tee": "同时输出到终端和文件",
    "xargs": "从标准读入构造参数执行命令",
    "jq": "JSON 解析与处理",
    "wc": "统计行/词/字节数",
    "diff": "比较两个文件差异",
    "head": "取文件前几行",
    "tail": "取文件后几行 (可实时追踪)",
    "less": "分页查看大文件",
    "file": "判断文件类型",
    "stat": "显示文件 inode 元数据",
    "du": "统计目录大小",
    "df": "显示磁盘分区使用情况",
    "apt": "Debian/Ubuntu 包管理器",
    "brew": "Homebrew 包管理器",
    "pip": "Python 包管理器",
    "winget": "Windows 包管理器",
    "tar": "tar 归档/解档",
    "zip": "zip 压缩",
    "unzip": "zip 解压",
    "gzip": "gzip 压缩/解压",
    "open": "用默认程序打开文件/URL (macOS)",
    "xdg-open": "用默认程序打开文件/URL (Linux)",
    "pbcopy": "写入系统剪贴板 (macOS)",
    "pbpaste": "读取系统剪贴板 (macOS)",
    "clip": "写入剪贴板 (Windows)",
    "say": "文本转语音朗读 (macOS)",
    "espeak": "文本转语音 (Linux)",
    "defaults": "macOS 系统偏好设置",
    "systemctl": "Systemd 服务管理",
    "sc": "Windows 服务控制",
    "launchctl": "macOS Launchd 服务管理",
    "crontab": "定时任务管理",
    "schtasks": "Windows 定时任务",
    "sudo": "以 root 权限执行命令",
    "runas": "以其他用户身份运行 (Windows)",
    "nohup": "忽略挂起信号后台执行",
    "watch": "周期性重复执行命令",
    "sleep": "睡眠 N 秒",
    "git": "Git 版本控制",
    "man": "查看命令手册",
    "help": "查看帮助 (Windows 风格)",
    "clear": "清屏",
    "exit": "退出当前会话",
    "history": "查看命令历史",
}


def explain_command(
    cmd_name: str,
    args: list[str] | None = None,
) -> str:
    """解释一个命令: 显示三平台翻译 + 参数说明.

    Args:
        cmd_name: 命令名 (如 "ls", "grep", "dir")
        args: 用户额外输入的参数 (如 ["-la", "/home"])

    Returns:
        格式化后的解释文本
    """
    cmd_lower = cmd_name.lower()
    entry = COMMAND_MAP.get(cmd_lower)
    if not entry:
        # 尝试推荐相似命令
        all_names = list(COMMAND_MAP.keys()) + list(COMMAND_DESCRIPTIONS.keys())
        similar = [n for n in all_names if cmd_lower in n or n in cmd_lower]
        similar = list(dict.fromkeys(similar))[:6]  # 去重
        hint = ""
        if similar:
            hint = f"\n相似命令: {', '.join(similar)}"
        return (
            f"❓ 未注册的命令: {cmd_name}\n"
            f"运行 os_help 查看所有支持的命令。{hint}"
        )

    desc = COMMAND_DESCRIPTIONS.get(cmd_lower, "")

    lines = []
    lines.append(f"📖 命令解释: {cmd_name}")
    if desc:
        lines.append(f"   功能: {desc}")
    lines.append("")
    lines.append("━━━ 跨平台翻译 ━━━")

    for os_name in ("linux", "windows", "macos"):
        translated = entry.get(os_name) or entry.get("linux")
        if not translated:
            translated_cmd = "(不支持)"
        else:
            translated_cmd = " ".join(translated)

        # 附加 args 到翻译后命令 (简单拼接)
        if args:
            translated_full = f"{translated_cmd} {' '.join(args)}"
        else:
            translated_full = translated_cmd

        if os_name == CURRENT_OS:
            lines.append(f"  {os_name.upper():<9} 👉  {translated_full}  ✅ (当前系统)")
        else:
            lines.append(f"  {os_name.upper():<9} 👉  {translated_full}")

    # 参数解释
    args_to_check = args or []
    # 如果命令本身是组合形式 (如 ps aux, tar czf), 也检查命令部分
    if not args_to_check and cmd_lower in COMMAND_ARG_HINTS:
        hint_entries = COMMAND_ARG_HINTS[cmd_lower]
    elif cmd_lower in COMMAND_ARG_HINTS:
        hint_entries = COMMAND_ARG_HINTS[cmd_lower]
    elif cmd_lower in WIN_COMMAND_ARG_HINTS:
        hint_entries = WIN_COMMAND_ARG_HINTS[cmd_lower]
    else:
        hint_entries = {}

    param_helps: list[str] = []
    for arg in args_to_check:
        if arg in hint_entries:
            info = hint_entries[arg]
            param_helps.append(f"  {arg:<10} {info.get('desc', '')}")
            semantic = info.get("semantic")
            if semantic and semantic in ARG_TRANSLATIONS:
                translations = ARG_TRANSLATIONS[semantic]
                ptrans = []
                for o, v in translations.items():
                    if v:
                        ptrans.append(f"{o}={v}")
                if ptrans:
                    param_helps.append(f"             语义跨平台: " + "  ".join(ptrans))

    if not param_helps and hint_entries:
        lines.append("")
        lines.append("━━━ 常用参数速查 ━━━")
        for arg, info in sorted(hint_entries.items()):
            lines.append(f"  {arg:<10} {info.get('desc', '')}")
    elif param_helps:
        lines.append("")
        lines.append("━━━ 参数解释 ━━━")
        lines.extend(param_helps)

    # 等效命令示例 (给出常见用法)
    examples = _get_usage_examples(cmd_lower, translated=entry)
    if examples:
        lines.append("")
        lines.append("━━━ 常见用法 ━━━")
        for ex in examples:
            lines.append(f"  {ex}")

    return "\n".join(lines)


def _get_usage_examples(cmd: str, translated: dict | None = None) -> list[str]:
    """生成命令的常见使用示例 (三平台版本)."""
    examples_map: dict[str, list[str]] = {
        "ls": [
            "ls -la /tmp              # 详细列出 /tmp 所有文件",
            "ls *.py                  # 列出所有 .py 文件",
            "ls -lhR src              # 递归 src, 人类可读大小",
        ],
        "dir": [
            "dir C:\\Users           # 列出 C:\\Users",
            "dir /s /b *.log         # 递归查找 .log, 仅文件名",
        ],
        "cat": [
            "cat config.yml          # 查看配置文件",
            "cat a.txt b.txt > out.txt  # 拼接写入",
        ],
        "grep": [
            'grep -i "error" app.log  # 忽略大小写查错误',
            "grep -r 'TODO' src/      # 递归搜索源码",
            "grep -n 'def ' main.py   # 显示函数定义行号",
        ],
        "findstr": [
            'findstr /s /i "error" *.log',
        ],
        "find": [
            "find /var -name '*.log' -mtime -7  # /var 一周内 log",
            "find . -type f -size +10M          # 当前目录 10MB+ 文件",
            "find src -name '*.py' | xargs grep main",
        ],
        "ps": [
            "ps aux | grep python             # 找 Python 进程",
            "ps -ef                           # 全格式所有进程",
        ],
        "kill": [
            "kill 12345                       # 优雅终止 PID",
            "kill -9 12345                    # 强制终止 (SIGKILL)",
            "killall firefox                  # 所有 firefox 进程",
        ],
        "taskkill": [
            "taskkill /pid 12345",
            "taskkill /f /im chrome.exe",
        ],
        "ping": [
            "ping 8.8.8.8                     # Linux/macOS 无限 (Win 默认 4 次)",
            "ping -c 4 example.com            # 发送 4 个包",
        ],
        "curl": [
            'curl -s https://api.github.com   # 静默抓取',
            'curl -O https://x.com/file.zip   # 下载保存原名',
            'curl -I https://example.com      # 仅响应头',
        ],
        "tar": [
            "tar -czf out.tar.gz /src         # gzip 压缩",
            "tar -xzf out.tar.gz              # gzip 解压",
            "tar -tvzf out.tar.gz             # 查看归档内容",
        ],
        "zip": [
            "zip -r project.zip src/          # 递归打包",
            "unzip project.zip -d outdir      # 解压到目录",
        ],
        "ssh": [
            "ssh user@192.168.1.100           # 基本登录",
            "ssh -p 2222 user@host -i ~/.ssh/id_rsa  # 指定端口和私钥",
        ],
        "scp": [
            "scp local.txt user@host:/tmp/    # 上传",
            "scp user@host:/tmp/file.txt .    # 下载",
            "scp -r dir/ user@host:/tmp/      # 目录",
        ],
        "chmod": [
            "chmod +x script.sh               # 添加执行权限",
            "chmod 644 file.txt               # rw-r--r--",
            "chmod -R 755 bin/                # 递归目录",
        ],
        "rm": [
            "rm temp.log                      # 删除单文件",
            "rm -rf cache/                    # 递归强制删除目录",
        ],
        "cp": [
            "cp src.txt dst.txt               # 文件复制",
            "cp -r src_dir dst_dir            # 目录复制",
        ],
        "head": [
            "head -20 data.csv                # 前 20 行",
        ],
        "tail": [
            "tail -10 app.log                 # 后 10 行",
            "tail -f app.log                  # 实时追踪",
        ],
        "wc": [
            "wc -l data.txt                   # 行数统计",
            "wc -w doc.txt                    # 词数统计",
        ],
        "sort": [
            "sort names.txt                   # 按字母排序",
            "sort -rn scores.txt              # 按数字倒序",
        ],
        "netstat": [
            "netstat -tlnp                    # Linux 监听端口及进程",
            "netstat -ano | findstr LISTENING # Win 监听端口",
        ],
        "whoami": [
            "whoami                           # 当前用户",
        ],
        "uname": [
            "uname -a                         # 完整系统信息",
        ],
        "free": [
            "free -h                          # 人类可读内存",
        ],
        "df": [
            "df -h                            # 人类可读磁盘使用",
        ],
        "du": [
            "du -sh /var/log                  # 单目录汇总大小",
        ],
    }

    if cmd in examples_map:
        return examples_map[cmd]

    # Windows 风格别名: 用相应 Linux 版本示例
    aliases = {
        "type": "cat",
        "copy": "cp",
        "move": "mv",
        "del": "rm",
        "tasklist": "ps",
        "findstr": "grep",
        "where": "which",
    }
    if cmd in aliases:
        linux_examples = examples_map.get(aliases[cmd])
        if linux_examples:
            # 简单提示
            return linux_examples

    return []


def compare_commands(
    command_lines: list[str],
) -> str:
    """批量比较多个命令的三平台翻译.

    Args:
        command_lines: 命令列表, 如 ["ls -la", "grep pattern file"]

    Returns:
        格式化表格文本
    """
    if not command_lines:
        return ("用法:\n"
                "  cmd_compare 'ls -la' 'grep pattern file'\n"
                "或: cmd_compare ls, grep, ping, find")

    # 逗号分隔 → list
    if len(command_lines) == 1 and "," in command_lines[0]:
        command_lines = [s.strip() for s in command_lines[0].split(",")]

    rows: list[tuple[str, str, str, str]] = []
    for raw in command_lines:
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split()
        name = parts[0].lower()
        rest = parts[1:]
        rest_str = " ".join(rest)

        entry = COMMAND_MAP.get(name)
        if not entry:
            rows.append((raw, "❓未注册", "❓未注册", "❓未注册"))
            continue

        cols: list[str] = []
        for os_name in ("linux", "windows", "macos"):
            t = entry.get(os_name) or entry.get("linux")
            t_str = " ".join(t) if t else "(不支持)"
            if rest_str:
                t_str += f" {rest_str}"
            cols.append(t_str)

        orig = raw + ("  ✅" if name in entry and CURRENT_OS == (
            "linux" if "linux" in " ".join(entry.get("linux", [])) else (
                "windows" if "cmd" in " ".join(entry.get("windows", [])) else "macos"
            )) else "")
        rows.append((raw, cols[0], cols[1], cols[2]))

    # 格式化表格
    w0 = max([len(r[0]) for r in rows] + [10])
    w1 = max([len(r[1]) for r in rows] + [12])
    w2 = max([len(r[2]) for r in rows] + [20])
    w3 = max([len(r[3]) for r in rows] + [12])

    out_lines = []
    header = (f"  {'输入':<{w0}} │ {'LINUX':<{w1}} │ {'WINDOWS':<{w2}} │ {'macOS':<{w3}}")
    out_lines.append("📋 命令跨平台对比表")
    out_lines.append("")
    out_lines.append(header)
    out_lines.append("  " + "─" * (w0 + w1 + w2 + w3 + 9))
    for raw, l, w, m in rows:
        out_lines.append(f"  {raw:<{w0}} │ {l:<{w1}} │ {w:<{w2}} │ {m:<{w3}}")
    out_lines.append("")
    out_lines.append("💡 无论你使用哪个平台, 输入任一命令名, Butler 会自动翻译执行。")

    return "\n".join(out_lines)


def translate_command_line(command_line: str, target_os: str) -> str:
    """将一条命令翻译成指定目标平台.

    Args:
        command_line: 完整命令行, 如 "ls -la /home"
        target_os: 目标平台, 'linux' / 'windows' / 'macos'

    Returns:
        翻译后的命令字符串
    """
    target_os = target_os.lower()
    if target_os not in ("linux", "windows", "macos"):
        return f"❌ 未知目标平台: {target_os} (可选 linux/windows/macos)"

    parts = command_line.strip().split()
    if not parts:
        return "❌ 空命令"

    name = parts[0].lower()
    rest = parts[1:]

    entry = COMMAND_MAP.get(name)
    if not entry:
        # 未注册的命令: 原样返回 + 提示
        return f"{command_line}  ⚠️ 未注册跨平台映射, 原样返回"

    translated = entry.get(target_os) or entry.get("linux") or [name]
    t_str = " ".join(translated)
    if rest:
        t_str += " " + " ".join(rest)
    return t_str

