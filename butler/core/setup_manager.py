"""设置管理器 - 处理首次启动、依赖安装、验证等

This module provides comprehensive setup and initialization management.
"""

import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)


class SetupManager:
    """系统设置管理器"""
    
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.env_file = self.project_root / ".env"
        self.env_ready_flag = self.project_root / ".env_ready"
        self.lib_external = self.project_root / "lib_external"
        self.venv_dir = self.project_root / "venv"
        self.setup_log = self.project_root / "logs" / "setup.log"
        self.setup_log.parent.mkdir(parents=True, exist_ok=True)
    
    def check_first_run(self) -> bool:
        """检查是否是首次运行"""
        return not self.env_ready_flag.exists()
    
    def ensure_env_file(self) -> bool:
        """确保 .env 文件存在"""
        try:
            if not self.env_file.exists():
                env_example = self.project_root / ".env.example"
                if env_example.exists():
                    logger.info("正在从 .env.example 初始�� .env...")
                    with open(env_example, 'r', encoding='utf-8') as f:
                        template = f.read()
                    with open(self.env_file, 'w', encoding='utf-8') as f:
                        f.write(template)
                else:
                    logger.info("创建空的 .env 文件...")
                    self.env_file.touch()
                return True
            return True
        except Exception as e:
            logger.error(f"初始化 .env 失败: {e}")
            return False
    
    def install_dependencies(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """安装项目依赖
        
        Args:
            progress_callback: 进度回调函数
        
        Returns:
            是否安装成功
        """
        try:
            if self.lib_external.exists():
                logger.info("依赖已安装（lib_external 存在）")
                if progress_callback:
                    progress_callback("依赖已安装")
                return True
            
            if self.venv_dir.exists():
                logger.info("虚拟环境已存在")
                if progress_callback:
                    progress_callback("使用现有虚拟环境")
                return True
            
            # 尝试使用依赖管理器安装
            logger.info("正在安装依赖...")
            if progress_callback:
                progress_callback("正在安装依赖，请稍候...")
            
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "package.core_utils.dependency_manager", "install_all"],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    logger.info("依赖安装成功")
                    if progress_callback:
                        progress_callback("依赖安装成功 ✅")
                    return True
                else:
                    error_msg = result.stderr or result.stdout
                    logger.warning(f"依赖安装返回非零代码: {result.returncode}")
                    logger.warning(f"错误信息: {error_msg}")
                    if progress_callback:
                        progress_callback(f"依赖安装警告（可继续使用）: {error_msg[:100]}")
                    # 不中断流程，因为某些依赖是可选的
                    return True
            except subprocess.TimeoutExpired:
                logger.error("依赖安装超时")
                if progress_callback:
                    progress_callback("依赖安装超时，请检查网络连接")
                return False
            except Exception as e:
                logger.error(f"依赖安装异常: {e}")
                if progress_callback:
                    progress_callback(f"依赖安装异常: {str(e)}")
                return False
        
        except Exception as e:
            logger.error(f"安装依赖时发生错误: {e}")
            if progress_callback:
                progress_callback(f"安装依赖失败: {str(e)}")
            return False
    
    def mark_setup_complete(self) -> bool:
        """标记设置完成"""
        try:
            self.env_ready_flag.touch()
            logger.info("设置已标记为完成")
            return True
        except Exception as e:
            logger.error(f"标记设置完成失败: {e}")
            return False
    
    def run_full_setup(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """执行完整的设置流程
        
        Args:
            progress_callback: 进度回调函数
        
        Returns:
            是否设置成功
        """
        logger.info("开始完整设置流程...")
        
        steps = [
            ("检查和初始化 .env", self.ensure_env_file),
            ("安装依赖", lambda: self.install_dependencies(progress_callback)),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"执行: {step_name}")
            if progress_callback:
                progress_callback(f"⏳ {step_name}...")
            
            try:
                if not step_func():
                    logger.warning(f"步骤失败（继续）: {step_name}")
                    if progress_callback:
                        progress_callback(f"⚠️ {step_name} 失败（继续）")
            except Exception as e:
                logger.error(f"步骤异常: {step_name}, 错误: {e}")
                if progress_callback:
                    progress_callback(f"❌ {step_name} 异常")
        
        self.mark_setup_complete()
        logger.info("设置流程完成")
        if progress_callback:
            progress_callback("✅ 设置完成！Butler 即将启动...")
        return True


# 全局实例
setup_manager = SetupManager()
