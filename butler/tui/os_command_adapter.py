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
    "chmod": {
        "linux":   ["chmod"],
        "windows": ["cmd", "/c", "icacls"],
        "macos":   ["chmod"],
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
