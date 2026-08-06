"""
会话模式系统 — 管理 Butler 会话的运行模式。

支持三种模式：
- Local: 直接在当前项目目录中工作
- Worktree: 在 Git 工作树中隔离变更
- Cloud: 在已配置的云环境中远程运行

每个会话都在选定的模式下运行，确保代码变更的隔离性。
"""

from __future__ import annotations

import enum
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from butler.core.security import (
    validate_branch_name,
    validate_path,
    validate_session_id,
)

logger = logging.getLogger(__name__)

_WORKTREE_NAME_RE = re.compile(r'^[a-zA-Z0-9][\w.\-]{1,63}$')
_MAX_SESSIONS = 64


class SessionMode(enum.StrEnum):
    """会话运行模式枚举。"""

    LOCAL = "local"
    WORKTREE = "worktree"
    CLOUD = "cloud"

    @property
    def display_name(self) -> str:
        return {
            "local": "本地",
            "worktree": "工作树",
            "cloud": "云端",
        }.get(self.value, self.value)

    @property
    def description(self) -> str:
        return {
            "local": "直接在当前项目目录中工作",
            "worktree": "在 Git 工作树中隔离变更",
            "cloud": "在已配置的云环境中远程运行",
        }.get(self.value, "")


@dataclass
class SessionConfig:
    """会话配置。"""

    mode: SessionMode = SessionMode.LOCAL
    project_path: str = ""
    worktree_path: Optional[str] = None
    cloud_endpoint: Optional[str] = None
    cloud_env: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "project_path": self.project_path,
            "worktree_path": self.worktree_path,
            "cloud_endpoint": self.cloud_endpoint,
            "cloud_env": self.cloud_env,
        }


@dataclass
class SessionState:
    """会话运行时状态。"""

    session_id: str
    config: SessionConfig
    is_active: bool = False
    created_at: float = 0.0
    worktree_name: Optional[str] = None


class SessionModeManager:
    """
    会话模式管理器。

    负责：
    - 根据选定模式设置会话环境
    - 管理模式切换
    - Worktree 创建/清理
    - 云环境连接
    - 线程安全的会话操作
    """

    def __init__(self):
        self._sessions: dict[str, SessionState] = {}
        self._active_session_id: Optional[str] = None
        self._lock = threading.RLock()
        self._cloud_available = self._check_cloud_availability()

    def _check_cloud_availability(self) -> bool:
        """检查云环境可用性。"""
        try:
            endpoint = os.getenv("BUTLER_CLOUD_ENDPOINT", "")
            return bool(endpoint)
        except Exception:
            return False

    def create_session(
        self,
        session_id: str,
        mode: SessionMode,
        project_path: str,
        **kwargs: Any,
    ) -> SessionState:
        """
        创建新会话。

        线程安全，包含输入校验和会话数量限制。
        """
        session_id = validate_session_id(session_id)
        safe_path = validate_path(project_path)

        with self._lock:
            if len(self._sessions) >= _MAX_SESSIONS:
                raise RuntimeError(f"会话数量已达上限 ({_MAX_SESSIONS})")

            config = SessionConfig(
                mode=mode,
                project_path=safe_path,
            )

            if mode == SessionMode.WORKTREE:
                worktree_name = kwargs.get("worktree_name") or f"butler-{session_id[:8]}"
                if not _WORKTREE_NAME_RE.match(worktree_name):
                    raise ValueError("Worktree 名称包含非法字符")
                wt_path = self._create_worktree(safe_path, worktree_name)
                config.worktree_path = wt_path
                config.project_path = wt_path

            elif mode == SessionMode.CLOUD:
                config.cloud_endpoint = kwargs.get("cloud_endpoint") or os.getenv(
                    "BUTLER_CLOUD_ENDPOINT", ""
                )
                config.cloud_env = kwargs.get("cloud_env", "default")

            state = SessionState(
                session_id=session_id,
                config=config,
                is_active=True,
                created_at=time.time(),
                worktree_name=kwargs.get("worktree_name"),
            )

            self._sessions[session_id] = state
            self._active_session_id = session_id

        logger.info(f"会话已创建: {session_id}, 模式: {mode.display_name}, 路径: {config.project_path}")
        return state

    def _create_worktree(self, project_path: str, worktree_name: str) -> str:
        """
        在 Git 仓库中创建 worktree。

        参数:
            project_path: 主项目路径（已验证）
            worktree_name: worktree 分支名称（已验证）
        """
        project = Path(project_path).resolve()
        if not project.is_dir():
            raise ValueError(f"项目路径不存在: {project_path}")

        safe_branch = validate_branch_name(worktree_name)

        wt_dir = Path(tempfile.gettempdir()) / f"butler-wt-{safe_branch}"

        if wt_dir.exists():
            logger.warning(f"Worktree 目录已存在，移除中: {wt_dir}")
            import shutil
            shutil.rmtree(wt_dir, ignore_errors=True)

        try:
            result = subprocess.run(
                ["git", "-C", str(project), "worktree", "add", str(wt_dir), safe_branch],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git worktree 创建失败: {result.stderr[:200]}")
            logger.info(f"Worktree 已创建: {wt_dir} (分支: {safe_branch})")
            return str(wt_dir)
        except FileNotFoundError:
            logger.warning("Git 未找到。Worktree 功能需要 Git 安装。")
            return str(project)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Worktree 创建超时")

    def remove_session(self, session_id: str) -> bool:
        """移除会话并清理资源。"""
        session_id = validate_session_id(session_id)

        with self._lock:
            state = self._sessions.pop(session_id, None)
            if not state:
                return False

            if state.config.mode == SessionMode.WORKTREE and state.config.worktree_path:
                self._remove_worktree(state.config.project_path, state.worktree_name)

            if self._active_session_id == session_id:
                self._active_session_id = None

        logger.info(f"会话已移除: {session_id}")
        return True

    def _remove_worktree(self, project_path: str, worktree_name: Optional[str]):
        """移除 worktree。"""
        if not worktree_name:
            return

        try:
            wt_path = Path(project_path)
            if wt_path.exists():
                result = subprocess.run(
                    ["git", "-C", str(Path(project_path).parent), "worktree", "remove", str(wt_path), "--force"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode != 0:
                    logger.warning(f"Worktree 移除警告: {result.stderr[:200]}")
        except Exception as e:
            logger.error(f"Worktree 清理失败: {e}")

    def switch_mode(self, session_id: str, new_mode: SessionMode) -> SessionState:
        """切换会话模式。线程安全。"""
        session_id = validate_session_id(session_id)

        with self._lock:
            state = self._sessions.get(session_id)
            if not state:
                raise ValueError(f"会话不存在: {session_id}")

            old_mode = state.config.mode
            if old_mode == new_mode:
                return state

            if old_mode == SessionMode.WORKTREE and state.config.worktree_path:
                self._remove_worktree(state.config.project_path, state.worktree_name)

            state.config.mode = new_mode
            state.config.worktree_path = None
            state.worktree_name = None

            if new_mode == SessionMode.WORKTREE:
                wt_name = f"butler-{session_id[:8]}"
                wt_path = self._create_worktree(state.config.project_path, wt_name)
                state.config.worktree_path = wt_path
                state.worktree_name = wt_name

            elif new_mode == SessionMode.CLOUD:
                state.config.cloud_endpoint = os.getenv("BUTLER_CLOUD_ENDPOINT", "")

        logger.info(f"会话 {session_id} 模式已切换: {old_mode} -> {new_mode}")
        return state

    def get_active_session(self) -> Optional[SessionState]:
        """获取当前活跃会话。"""
        with self._lock:
            if self._active_session_id:
                return self._sessions.get(self._active_session_id)
        return None

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取指定会话。"""
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[SessionState]:
        """列出所有会话。"""
        with self._lock:
            return list(self._sessions.values())

    def list_modes(self) -> list[dict[str, str]]:
        """列出可用模式。"""
        modes = [
            {
                "value": m.value,
                "name": m.display_name,
                "description": m.description,
                "available": True,
            }
            for m in SessionMode
        ]
        modes[2]["available"] = self._cloud_available
        return modes


session_mode_manager = SessionModeManager()
