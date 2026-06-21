"""启动向导 - 统一的首次启动体验

This module provides a comprehensive startup wizard that handles:
- Environment setup
- Dependency installation
- Configuration
- API key validation
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from pathlib import Path
from butler.core.setup_manager import setup_manager
from butler.gui.config_wizard_enhanced import EnhancedConfigWizard
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)


class StartupWizard:
    """启动向导"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Butler - 首次启动向导")
        self.root.geometry("700x600")
        self.root.configure(bg='#1c1c1c')
        self.root.resizable(False, False)
        
        # 防止用户关闭窗口
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        self.current_step = 0
        self.steps_completed = False
        self._setup_ui()
    
    def _setup_ui(self):
        """设置用户界面"""
        # 进度条
        progress_frame = tk.Frame(self.root, bg='#1c1c1c')
        progress_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        tk.Label(progress_frame, text="初始化进度", bg='#1c1c1c', fg='#00ff00',
                font=("Arial", 12, "bold")).pack(anchor='w')
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                           maximum=100, length=660)
        self.progress_bar.pack(pady=10)
        
        # 状态文本
        status_frame = tk.Frame(self.root, bg='#1c1c1c')
        status_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(status_frame, text="状态日志", bg='#1c1c1c', fg='#00ff00',
                font=("Arial", 10, "bold")).pack(anchor='w')
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, width=80,
                                                    bg='#000000', fg='#00ff00',
                                                    font=("Courier", 8), borderwidth=1)
        self.status_text.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 按钮框架
        btn_frame = tk.Frame(self.root, bg='#1c1c1c')
        btn_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.continue_btn = tk.Button(btn_frame, text="继续", command=self._next_step,
                                      bg='#00aa00', fg='#000000', padx=20, pady=8,
                                      borderwidth=0, font=("Arial", 10, "bold"),
                                      cursor="hand2", state=tk.DISABLED)
        self.continue_btn.pack(side=tk.LEFT, padx=5)
        
        self.skip_btn = tk.Button(btn_frame, text="跳过", command=self._skip_setup,
                                 bg='#333333', fg='#ffffff', padx=20, pady=8,
                                 borderwidth=0, font=("Arial", 10), cursor="hand2")
        self.skip_btn.pack(side=tk.LEFT, padx=5)
        
        self._append_status("🚀 Butler 首次启动向导")
        self._append_status("\n正在检查系统环境...\n")
        
        # 启动初始化流程
        threading.Thread(target=self._run_setup, daemon=True).start()
    
    def _append_status(self, message: str):
        """添加状态消息"""
        self.status_text.insert(tk.END, message)
        self.status_text.see(tk.END)
        self.root.update()
    
    def _update_progress(self, value: float):
        """更新进度条"""
        self.progress_var.set(min(value, 100))
        self.root.update()
    
    def _progress_callback(self, message: str):
        """进度回调"""
        self._append_status(f"{message}\n")
        
        # 根据消息类型更新进度
        if "初始化" in message or "检查" in message:
            self._update_progress(20)
        elif "安装" in message:
            self._update_progress(50)
        elif "完成" in message or "成功" in message:
            self._update_progress(100)
    
    def _run_setup(self):
        """后台运行设置"""
        try:
            # 步骤1: 确保 .env
            self._append_status("\n✓ 检查配置文件...")
            if setup_manager.ensure_env_file():
                self._append_status(" 完成\n")
                self._update_progress(30)
            
            # 步骤2: 安装依赖
            self._append_status("✓ 检查依赖...")
            if setup_manager.install_dependencies(self._progress_callback):
                self._append_status(" 完成\n")
                self._update_progress(60)
            
            # 步骤3: 完成初始化
            self._append_status("\n" + "="*60)
            self._append_status("\n✅ 系统初始化完成！\n\n")
            self._append_status("现在需要配置 API 密钥...\n")
            self._append_status("点击「继续」进入 API 密钥配置界面\n")
            
            # 启用继续按钮
            self.continue_btn.config(state=tk.NORMAL)
            self._update_progress(100)
            
            self.steps_completed = True
        except Exception as e:
            logger.error(f"设置失败: {e}")
            self._append_status(f"\n❌ 设置失败: {str(e)}\n")
            messagebox.showerror("设置失败", f"系统初始化失败:\n{str(e)}")
            self.skip_btn.config(state=tk.NORMAL)
    
    def _next_step(self):
        """继续到下一步"""
        if self.steps_completed:
            # 关闭启动向导，显示配置向导
            self.root.destroy()
            config_wizard = EnhancedConfigWizard()
            config_wizard.root.mainloop()
    
    def _skip_setup(self):
        """跳过设置"""
        self.root.destroy()
    
    def run(self):
        """运行启动向导"""
        self.root.mainloop()


def show_startup_wizard_if_needed():
    """如果需要，显示启动向导"""
    if setup_manager.check_first_run():
        logger.info("检测到首次运行，显示启动向导")
        wizard = StartupWizard()
        wizard.run()
        return True
    return False
