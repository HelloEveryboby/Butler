"""增强的 Butler 启动文件 - 集成新的设置和配置系统

这个文件是对原 butler_app.py 的改进，添加了：
1. 启动向导（首次运行）
2. 增强的配置系统
3. 更好的错误处理
4. 配置验证
"""

import os
import sys
import time
import datetime
import json
import re
import threading
import logging
from typing import Dict, Any, List
import tempfile
import shutil
import tkinter as tk
from pathlib import Path
from dotenv import load_dotenv

# 添加项目路径支持
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

lib_path = project_root / "lib_external"
if lib_path.exists():
    import site
    site.addsitedir(str(lib_path))

# 导入增强的模块
from butler.core.environment import run_preflight_check
from butler.gui.startup_wizard import show_startup_wizard_if_needed
from butler.gui.config_wizard_enhanced import show_config_wizard_if_needed
from butler.core.config_manager import config_manager

# 运行环境检查
run_preflight_check()

# 加载 .env
load_dotenv()

from package.core_utils.log_manager import LogManager
logger = LogManager.get_logger(__name__)


def initialize_butler_environment():
    """初始化 Butler 环境

    这个函数处理：
    1. 首次��动检查和设置
    2. 配置验证
    3. 依赖验证
    """
    logger.info("="*60)
    logger.info("Butler 应用启动")
    logger.info("="*60)

    # 步骤 1: 检查是否首次运行
    if show_startup_wizard_if_needed():
        logger.info("首次运行设置向导已完成")

    # 步骤 2: 验证配置
    is_valid, missing_keys = config_manager.validate_required_keys()

    if not is_valid:
        logger.warning(f"缺失必需的 API 密钥: {missing_keys}")

        # 显示配置向导
        if show_config_wizard_if_needed():
            logger.info("配置向导已完成")
            # 重新加载配置
            config_manager.reload()
        else:
            logger.warning("用户跳过配置，某些功能将不可用")

    logger.info("环境初始化完成")


def main():
    """主入口点"""
    import argparse

    parser = argparse.ArgumentParser(description="Butler - 智能助手系统")
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    parser.add_argument("--classic", "--admin", action="store_true", dest="classic",
                       help="使用经典 Tkinter 模式")
    parser.add_argument("--skip-setup", action="store_true", help="跳过初始化向导")
    args = parser.parse_args()

    # 初始化环境（除非明确跳过）
    if not args.skip_setup:
        initialize_butler_environment()

    # 导入原始的 Jarvis 类
    from butler.butler_app import Jarvis, USBScreen, CommandPanel
    from butler.core.extension_manager import extension_manager

    # 启动应用
    usb_screen = USBScreen(40, 8)

    if args.headless:
        logger.info("以无头模式启动")
        jarvis = Jarvis(None, usb_screen, headless=True)
        jarvis.main()
        while jarvis.running:
            time.sleep(1)
        return

    # 尝试启动现代 Web UI
    if not args.classic:
        try:
            from frontend.program import modern_app
            logger.info("启动现代 Web UI 模式")
            modern_app.main()
            return
        except Exception as e:
            logger.warning(f"现代模式启动失败，回退到经典模式: {e}")

    # 启动经典 Tkinter 模式
    logger.info("启动经典 Tkinter 模式")
    root = tk.Tk()
    root.title("Jarvis 助手")

    jarvis = Jarvis(root, usb_screen, headless=False)
    all_tools = {t['name']: t.get('path', t.get('module')) for t in extension_manager.get_all_tools()}
    panel = CommandPanel(root, program_mapping=jarvis.program_mapping, programs=all_tools,
                        command_callback=jarvis.panel_command_handler)
    panel.pack(fill=tk.BOTH, expand=True)

    jarvis.main()
    root.mainloop()


if __name__ == "__main__":
    main()
