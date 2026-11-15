#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Butler 统一命令入口调度器 (Cross-platform front door).

用法 (通常经由 ``bin/butler`` / ``bin/butler.bat`` 或安装器注册的 ``butler`` 命令):
    butler                    # 默认进入 TUI 交互界面
    butler start / doctor ... # 界面与管理命令 -> python -m butler
    butler crawl / email ...  # 功能型命令      -> butler_cli.py

设计目标: 用户只需要记住 ``butler`` 一个词，不再需要分辨
``butler.py`` / ``butler_cli.py`` / ``python -m butler`` 该用哪个。
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# 属于 ``python -m butler`` (界面 / 服务 / 管理) 的命令
MODE_COMMANDS = {
    "", "help", "guide",
    "tui", "gui", "web", "headless",
    "start", "api",
    "agent", "package", "config", "doctor", "download",
    "init",
    # 兼容旧写法
    "legacy", "下载",
}


def main() -> None:
    argv = sys.argv[1:]
    first = argv[0] if argv else ""

    if first in MODE_COMMANDS or first.startswith("-"):
        target = [sys.executable, "-m", "butler", *argv]
    else:
        target = [sys.executable, str(PROJECT_ROOT / "butler_cli.py"), *argv]

    # 保证 butler 包 / package 包可被导入
    import os
    env = dict(os.environ)
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + pp if pp else "")

    sys.exit(subprocess.call(target, cwd=str(PROJECT_ROOT), env=env))


if __name__ == "__main__":
    main()
