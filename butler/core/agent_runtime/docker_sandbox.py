"""
Docker Sandbox — 容器级隔离执行环境。

参考架构：OpenHands V1 的 DockerWorkspace（可选隔离）。

核心特性：
    1. 每个会话独立 Docker 容器，完全隔离
    2. 可选启用（V1 默认本地运行，需要安全隔离时才切换）
    3. 支持文件挂载、资源限制、网络隔离
    4. 容器生命周期管理

注意：需要 Docker 环境支持。如果 Docker 不可用，自动降级到本地执行。
"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 追踪所有活跃的沙箱实例，用于进程退出时清理
_active_sandboxes: list["DockerSandbox"] = []


def _cleanup_all_sandboxes() -> None:
    """进程退出时清理所有活跃的 Docker 沙箱容器。"""
    for sandbox in _active_sandboxes:
        try:
            if sandbox._container_name:
                sandbox.stop()
        except Exception:
            pass


atexit.register(_cleanup_all_sandboxes)

# 默认容器镜像
_DEFAULT_IMAGE = "python:3.11-slim"

# 默认资源限制
_DEFAULT_MEMORY_LIMIT = "512m"
_DEFAULT_CPU_LIMIT = "1.0"
_DEFAULT_TIMEOUT = 120


class DockerSandbox:
    """
    Docker 容器级隔离执行环境。

    参考 OpenHands V1 的可选隔离原则：
        - 代理默认本地运行
        - 需要安全隔离时才切换到沙箱环境
        - 代理和工具统一在单进程内执行（V1）

    使用方式::

        sandbox = DockerSandbox(
            workspace_root="/path/to/project",
            image="python:3.11-slim",
        )

        # 启动容器
        sandbox.start()

        # 执行命令
        result = sandbox.execute("python -m pytest")

        # 执行 Python 代码
        result = sandbox.execute_python("print('hello')")

        # 停止容器
        sandbox.stop()
    """

    def __init__(
        self,
        workspace_root: str | None = None,
        image: str = _DEFAULT_IMAGE,
        memory_limit: str = _DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = _DEFAULT_CPU_LIMIT,
        network_disabled: bool = False,
    ):
        self._workspace = Path(workspace_root or os.getcwd()).resolve()
        self._image = image
        self._memory = memory_limit
        self._cpu = cpu_limit
        self._network_disabled = network_disabled
        self._container_id: str | None = None
        self._container_name: str | None = None

    @property
    def is_running(self) -> bool:
        """检查容器是否在运行。"""
        if not self._container_id:
            return False
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", self._container_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception:
            return False

    @property
    def container_id(self) -> str | None:
        return self._container_id

    @staticmethod
    def is_docker_available() -> bool:
        """检查 Docker 是否可用。"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def start(self) -> bool:
        """
        启动 Docker 容器。

        返回:
            是否成功启动
        """
        if not self.is_docker_available():
            logger.warning("Docker not available, cannot start sandbox")
            return False

        if self.is_running:
            logger.info("Sandbox container already running")
            return True

        self._container_name = f"butler-sandbox-{uuid.uuid4().hex[:8]}"

        # 构建 docker run 命令
        cmd = [
            "docker", "run", "-d",
            "--name", self._container_name,
            "-v", f"{self._workspace}:/workspace",
            "-w", "/workspace",
            "--memory", self._memory,
            "--cpus", self._cpu,
        ]

        if self._network_disabled:
            cmd.append("--network none")

        cmd.append(self._image)
        cmd.append("sleep infinity")  # 保持容器运行

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                logger.error(f"Failed to start container: {result.stderr}")
                return False

            self._container_id = result.stdout.strip()
            if self not in _active_sandboxes:
                _active_sandboxes.append(self)
            logger.info(
                f"Started sandbox container: {self._container_name} "
                f"(id={self._container_id[:12]})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start Docker sandbox: {e}")
            return False

    def stop(self) -> bool:
        """停止并移除容器。"""
        if not self._container_name:
            return True

        try:
            # 停止容器
            subprocess.run(
                ["docker", "stop", self._container_name],
                capture_output=True,
                timeout=30,
            )

            # 移除容器
            subprocess.run(
                ["docker", "rm", "-f", self._container_name],
                capture_output=True,
                timeout=30,
            )

            logger.info(f"Stopped sandbox container: {self._container_name}")
            self._container_id = None
            self._container_name = None
            if self in _active_sandboxes:
                _active_sandboxes.remove(self)
            return True

        except Exception as e:
            logger.error(f"Failed to stop sandbox: {e}")
            return False

    def execute(
        self,
        command: str,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """
        在容器中执行命令。

        参数:
            command: 要执行的命令
            timeout: 超时（秒）

        返回:
            dict: {
                "stdout": 标准输出,
                "stderr": 标准错误,
                "returncode": 返回码,
            }
        """
        if not self.is_running:
            return {
                "stdout": "",
                "stderr": "Sandbox container not running",
                "returncode": -1,
            }

        try:
            result = subprocess.run(
                [
                    "docker", "exec",
                    self._container_name,
                    "bash", "-c", command,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }

    def execute_python(
        self,
        code: str,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """
        在容器中执行 Python 代码。

        参数:
            code: Python 代码
            timeout: 超时（秒）

        返回:
            执行结果
        """
        # 将代码写入临时文件并执行
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=str(self._workspace)
        ) as f:
            f.write(code)
            script_name = f.name

        script_path = Path(script_name).name  # 容器内路径
        result = self.execute(f"python {script_path}", timeout)

        # 清理临时文件
        try:
            Path(script_name).unlink()
        except Exception:
            pass

        return result

    def copy_to_container(self, local_path: str, container_path: str) -> bool:
        """从主机复制文件到容器。"""
        if not self.is_running:
            return False

        try:
            result = subprocess.run(
                ["docker", "cp", local_path, f"{self._container_name}:{container_path}"],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to copy file to container: {e}")
            return False

    def copy_from_container(self, container_path: str, local_path: str) -> bool:
        """从容器复制文件到主机。"""
        if not self.is_running:
            return False

        try:
            result = subprocess.run(
                ["docker", "cp", f"{self._container_name}:{container_path}", local_path],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to copy file from container: {e}")
            return False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
