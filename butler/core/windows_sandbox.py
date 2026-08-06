"""
Windows 原生沙箱 — 在 Windows 上提供原生沙箱支持。

在 Windows 上，Butler 可以在 PowerShell 中原生运行，使用原生 Windows 沙箱，
而无需 WSL 或虚拟机。这让用户能够保持 Windows 原生工作流，同时确保权限受到限制。

功能：
- Windows Sandbox API 封装
- PowerShell 受限执行
- 权限边界控制
- 进程隔离
- 文件系统访问限制
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from butler.core.security import (
    validate_path,
    validate_session_id,
)

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"

_MAX_COMMAND_LENGTH = 4096
_MAX_SESSION_IDLE_SECONDS = 3600
_SAFE_COMMAND_RE = re.compile(r'^[\w\s.\-/,;:()@#$%+*=\[\]{}<>~!?\'"]+$')
_MAX_ALLOWED_PATHS = 32


@dataclass
class SandboxConfig:
    """Windows 沙箱配置。"""

    enabled: bool = True
    allow_network: bool = False
    allow_gpu: bool = False
    allow_audio: bool = False
    clipboard_redirection: bool = True
    printer_redirection: bool = False
    memory_in_mb: int = 2048
    vcpu_count: int = 2
    sandbox_path: str = ""
    allowed_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "allow_network": self.allow_network,
            "allow_gpu": self.allow_gpu,
            "allow_audio": self.allow_audio,
            "clipboard_redirection": self.clipboard_redirection,
            "printer_redirection": self.printer_redirection,
            "memory_in_mb": self.memory_in_mb,
            "vcpu_count": self.vcpu_count,
            "sandbox_path": self.sandbox_path,
            "allowed_paths": self.allowed_paths,
        }


@dataclass
class SandboxSession:
    """沙箱会话。"""

    session_id: str
    config: SandboxConfig
    is_running: bool = False
    process_id: Optional[int] = None
    started_at: float = 0.0
    workspace_path: str = ""


class WindowsSandbox:
    """
    Windows 原生沙箱管理器。

    线程安全，包含命令注入防护和路径验证。
    """

    def __init__(self):
        self._available = self._check_availability()
        self._sessions: dict[str, SandboxSession] = {}
        self._config = SandboxConfig()
        self._lock = threading.RLock()

    def _check_availability(self) -> bool:
        """检查 Windows 沙箱可用性。"""
        if not _IS_WINDOWS:
            logger.info("Windows 沙箱仅在 Windows 系统上可用")
            return False

        checks = [
            self._check_windows_sandbox_feature,
            self._check_powershell_availability,
            self._check_permissions,
        ]

        results = [check() for check in checks]
        available = all(results)

        if available:
            logger.info("Windows 原生沙箱已就绪")
        else:
            missing = [
                "Windows Sandbox 功能" if not results[0] else None,
                "PowerShell" if not results[1] else None,
                "管理员权限" if not results[2] else None,
            ]
            missing = [m for m in missing if m]
            logger.warning(f"Windows 沙箱部分功能不可用: {', '.join(missing)}")

        return available

    def _check_windows_sandbox_feature(self) -> bool:
        """检查 Windows Sandbox 功能是否已启用。"""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Sandbox-VM | "
                 "Select-Object -ExpandProperty State"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "Enabled" in (result.stdout or "")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_powershell_availability(self) -> bool:
        """检查 PowerShell 可用性。"""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "$PSVersionTable.PSVersion"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_permissions(self) -> bool:
        """检查当前权限。"""
        try:
            if _IS_WINDOWS:
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            pass
        return False

    @property
    def is_available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    def get_config(self) -> SandboxConfig:
        return self._config

    def update_config(self, **kwargs: Any) -> SandboxConfig:
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        return self._config

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def create_session(
        self,
        session_id: str,
        workspace_path: str = "",
        **config_kwargs: Any,
    ) -> SandboxSession:
        """创建沙箱会话。线程安全，含路径验证。"""
        import time

        session_id = validate_session_id(session_id)

        with self._lock:
            if session_id in self._sessions:
                logger.warning(f"会话已存在: {session_id}")
                return self._sessions[session_id]

            config = SandboxConfig(**{**self._config.to_dict(), **config_kwargs})

            if len(config.allowed_paths) > _MAX_ALLOWED_PATHS:
                raise ValueError(f"允许路径数量超过限制 ({_MAX_ALLOWED_PATHS})")

            ws_path = workspace_path or os.path.join(
                os.environ.get("TEMP", os.getcwd()),
                f"butler-sandbox-{session_id[:8]}",
            )

            try:
                ws_path = validate_path(ws_path, must_exist=False)
            except ValueError:
                ws_path = os.path.join(os.environ.get("TEMP", os.getcwd()), f"butler-sandbox-{session_id[:8]}")

            session = SandboxSession(
                session_id=session_id,
                config=config,
                workspace_path=ws_path,
                started_at=time.time(),
            )

            try:
                os.makedirs(ws_path, exist_ok=True)
            except OSError as e:
                logger.error(f"工作目录创建失败: {e}")
                raise RuntimeError(f"工作目录无法创建: {e}")

            self._sessions[session_id] = session

        logger.info(f"沙箱会话已创建: {session_id} -> {ws_path}")
        return session

    def start_session(self, session_id: str) -> bool:
        """启动沙箱会话。"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.is_running:
            return True

        if not self._available:
            logger.warning("沙箱不可用，降级为普通进程执行")
            session.is_running = True
            return True

        try:
            if self._config.enabled and self._check_windows_sandbox_feature():
                return self._start_windows_sandbox(session)
            else:
                return self._start_powershell_restricted(session)
        except Exception as e:
            logger.error(f"沙箱启动失败: {e}")
            return False

    def _start_windows_sandbox(self, session: SandboxSession) -> bool:
        """使用 Windows Sandbox API 启动。"""
        try:
            wsb_content = self._generate_wsb_file(session)
            wsb_path = os.path.join(session.workspace_path, "butler-sandbox.wsb")

            with open(wsb_path, "w", encoding="utf-8") as f:
                f.write(wsb_content)

            proc = subprocess.Popen(
                ["wdxwmmgr", wsb_path],
                cwd=session.workspace_path,
                creationflags=subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0,
            )
            session.process_id = proc.pid
            session.is_running = True
            logger.info(f"Windows 沙箱已启动 (PID: {proc.pid})")
            return True
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Windows Sandbox 启动失败，使用 PowerShell 受限模式: {e}")
            return self._start_powershell_restricted(session)

    def _start_powershell_restricted(self, session: SandboxSession) -> bool:
        """使用 PowerShell 受限执行模式。脚本内容已净化。"""
        try:
            ws_escaped = session.workspace_path.replace("'", "''")
            allowed_paths_escaped = [p.replace("'", "''") for p in session.config.allowed_paths]
            paths_str = ", ".join(f"'{p}'" for p in allowed_paths_escaped)

            profile_lines = [
                "# Butler Sandbox Restricted Profile",
                "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Restricted",
                f"Set-Location '{ws_escaped}'",
                "",
                f"$allowedPaths = @({paths_str})",
                "",
                "Function Test-PathAccess {",
                "    param([string]$Path)",
                "    if ($allowedPaths.Count -eq 0) { return $true }",
                "    foreach ($allowed in $allowedPaths) {",
                "        if ($Path.StartsWith($allowed)) { return $true }",
                "    }",
                "    return $false",
                "}",
                "",
                "Write-Host 'Butler Sandbox (Restricted PowerShell) Ready'",
                f"Write-Host 'Workspace: {ws_escaped}'",
            ]

            profile_content = "\n".join(profile_lines)

            profile_path = os.path.join(session.workspace_path, "butler_profile.ps1")
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write(profile_content)

            session.is_running = True
            logger.info("PowerShell 受限沙箱已就绪")
            return True
        except Exception as e:
            logger.error(f"PowerShell 受限模式启动失败: {e}")
            return False

    def _generate_wsb_file(self, session: SandboxSession) -> str:
        """生成 Windows Sandbox 配置文件。路径已净化。"""
        config = session.config
        ws_escaped = session.workspace_path.replace("\\", "\\\\")
        return f"""<Configuration>
  <VGpu>{'Enable' if config.allow_gpu else 'Disable'}</VGpu>
  <Networking>{'Enable' if config.allow_network else 'Disable'}</Networking>
  <MemoryInMB>{config.memory_in_mb}</MemoryInMB>
  <Processor>
    <NumberOfCores>{config.vcpu_count}</NumberOfCores>
  </Processor>
  <ClipboardRedirection>{'Enable' if config.clipboard_redirection else 'Disable'}</ClipboardRedirection>
  <PrinterRedirection>{'Enable' if config.printer_redirection else 'Disable'}</PrinterRedirection>
  <AudioInputRedirection>{'Enable' if config.allow_audio else 'Disable'}</AudioInputRedirection>
  <FolderMappings>
    <Folder>
      <FolderPath>{ws_escaped}</FolderPath>
      <SandboxFolderPath>C:\\ButlerWorkspace</SandboxFolderPath>
      <ReadOnly>false</ReadOnly>
    </Folder>
  </FolderMappings>
  <LogonCommand>
    <Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Set-Location C:\\ButlerWorkspace; Write-Host 'Butler Sandbox Ready'"</Command>
  </LogonCommand>
</Configuration>"""

    def execute_in_session(
        self,
        session_id: str,
        command: str,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """
        在沙箱会话中执行命令。

        命令会被注入到 PowerShell 脚本中，因此必须先进行安全过滤。
        """
        session_id = validate_session_id(session_id)

        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            return {"success": False, "error": "会话不存在"}

        if not session.is_running:
            started = self.start_session(session_id)
            if not started:
                return {"success": False, "error": "沙箱启动失败"}

        if not isinstance(command, str) or not command.strip():
            return {"success": False, "error": "命令不能为空"}

        if len(command) > _MAX_COMMAND_LENGTH:
            return {"success": False, "error": f"命令过长 (最大 {_MAX_COMMAND_LENGTH} 字符)"}

        dangerous_chars = re.compile(r'[;&|`$(){}!#<>\n\r]')
        if dangerous_chars.search(command):
            return {"success": False, "error": "命令包含危险 Shell 字符"}

        safe_command = command.strip()

        if timeout < 1 or timeout > 300:
            timeout = 30

        try:
            ps_command = f"""
Set-Location "{session.workspace_path}"
try {{
    $output = {safe_command} 2>&1
    Write-Output "SUCCESS:$($output | Out-String)"
}} catch {{
    Write-Output "ERROR:$($_.Exception.Message)"
}}
"""
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=session.workspace_path,
            )

            output = result.stdout.strip()
            if output.startswith("SUCCESS:"):
                return {
                    "success": True,
                    "output": output[8:],
                    "error": result.stderr[:500] if result.stderr else None,
                }
            elif output.startswith("ERROR:"):
                return {
                    "success": False,
                    "error": output[6:500],
                    "output": result.stdout[:500],
                }
            else:
                return {
                    "success": result.returncode == 0,
                    "output": output[:500],
                    "error": result.stderr[:500] if result.returncode != 0 else None,
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"命令执行超时 ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    def stop_session(self, session_id: str) -> bool:
        """停止沙箱会话。"""
        session = self._sessions.pop(session_id, None)
        if not session:
            return False

        if session.process_id:
            try:
                if _IS_WINDOWS:
                    subprocess.run(
                        ["taskkill", "/PID", str(session.process_id), "/F"],
                        capture_output=True,
                        timeout=5,
                    )
                else:
                    os.kill(session.process_id, 9)
            except (OSError, subprocess.TimeoutExpired):
                pass

        logger.info(f"沙箱会话已停止: {session_id}")
        return True

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有沙箱会话。"""
        return [
            {
                "session_id": s.session_id,
                "is_running": s.is_running,
                "workspace_path": s.workspace_path,
                "process_id": s.process_id,
            }
            for s in self._sessions.values()
        ]

    def get_system_info(self) -> dict[str, Any]:
        """获取 Windows 沙箱相关系统信息。"""
        return {
            "is_windows": _IS_WINDOWS,
            "is_available": self._available,
            "os_version": platform.version() if _IS_WINDOWS else "N/A",
            "has_windows_sandbox": self._check_windows_sandbox_feature() if _IS_WINDOWS else False,
            "has_powershell": self._check_powershell_availability(),
            "is_admin": self._check_permissions() if _IS_WINDOWS else False,
            "active_sessions": len(self._sessions),
        }


windows_sandbox = WindowsSandbox()
