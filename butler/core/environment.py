import sys
import os
import platform
import shutil
from pathlib import Path
from typing import List, Tuple
from package.core_utils.log_manager import LogManager
from butler.core.constants import PROJECT_ROOT

logger = LogManager.get_logger("EnvironmentCheck")

class EnvironmentChecker:
    """
    Butler 启动前环境自检器 (Pre-flight Environment Check)
    验证 Python 版本、核心依赖、文件系统权限及关键路径。
    """

    REQUIRED_PYTHON = (3, 8)
    REQUIRED_LIBS = [
        "pydantic", "yaml", "dotenv", "requests"
    ]

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def check_all(self) -> bool:
        """运行所有检查，返回 True 表示可以启动。"""
        logger.info("Starting Butler Pre-flight Environment Check...")

        self._check_python_version()
        self._check_essential_libs()
        self._check_filesystem_permissions()
        self._check_critical_paths()

        if self.warnings:
            for warning in self.warnings:
                logger.warning(f"[ENV] {warning}")

        if self.errors:
            for error in self.errors:
                logger.error(f"[ENV] {error}")
            return False

        logger.info("Pre-flight check passed.")
        return True

    def _check_python_version(self):
        current = sys.version_info
        if current[:2] < self.REQUIRED_PYTHON:
            self.errors.append(f"Python version {self.REQUIRED_PYTHON[0]}.{self.REQUIRED_PYTHON[1]}+ required. Current: {current.major}.{current.minor}")

    def _check_essential_libs(self):
        import importlib
        for lib in self.REQUIRED_LIBS:
            try:
                importlib.import_module(lib if lib != "yaml" else "yaml")
            except ImportError:
                self.errors.append(f"Missing essential library: {lib}")

    def _check_filesystem_permissions(self):
        paths_to_check = [
            PROJECT_ROOT / "data",
            PROJECT_ROOT / "logs",
            PROJECT_ROOT / "config"
        ]

        for p in paths_to_check:
            if p.exists():
                if not os.access(p, os.W_OK):
                    self.errors.append(f"Directory not writable: {p}")
            else:
                try:
                    p.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self.errors.append(f"Could not create directory {p}: {e}")

    def _check_critical_paths(self):
        # Check if .env.example exists if .env is missing
        if not (PROJECT_ROOT / ".env").exists() and not (PROJECT_ROOT / ".env.example").exists():
            self.warnings.append("Neither .env nor .env.example found in project root.")

def run_preflight_check():
    checker = EnvironmentChecker()
    if not checker.check_all():
        print("\n" + "!" * 60)
        print("  CRITICAL ERROR: Butler environment check failed!")
        for err in checker.errors:
            print(f"  - {err}")
        print("!" * 60 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    run_preflight_check()
