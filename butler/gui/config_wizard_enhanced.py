import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
from pathlib import Path
from dotenv import load_dotenv, set_key
import threading
import requests
import json
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class EnhancedConfigWizard:
    """增强的配置向导 - 支持验证、进度反馈、统一配置管理"""
    
    def __init__(self, root=None):
        self.own_root = False
        if root is None:
            self.root = tk.Tk()
            self.own_root = True
        else:
            self.root = tk.Toplevel(root)
            self.root.transient(root)
            self.root.grab_set()

        self.root.title("Butler - 初始化配置")
        self.root.geometry("600x700")
        self.root.configure(bg='#1c1c1c')
        
        self.env_path = Path(".env")
        self.config_yaml_path = Path("config/config.yaml")
        load_dotenv(self.env_path)

        # API 密钥字段配置
        self.fields = [
            ("DEEPSEEK_API_KEY", "🤖 DeepSeek API Key (必需 - 核心对话功能):", True),
            ("BAIDU_APP_ID", "🎤 Baidu App ID (可选 - 语音功能):", False),
            ("BAIDU_API_KEY", "🎤 Baidu API Key (可选 - 语音功能):", False),
            ("BAIDU_SECRET_KEY", "🎤 Baidu Secret Key (可选 - 语音功能):", False),
            ("PICOVOICE_ACCESS_KEY", "🎙️ Picovoice Access Key (可选 - 唤醒词):", False),
        ]
        self.entries = {}
        self.validation_results = {}
        self.setup_complete = False
        
        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        # 样式配置
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Header.TLabel", background='#1c1c1c', foreground='#00ff00', font=("Arial", 14, "bold"))
        style.configure("TLabel", background='#1c1c1c', foreground='#ffffff', font=("Arial", 10))
        style.configure("TEntry", fieldbackground='#000000', foreground='#00ff00')
        style.configure("Info.TLabel", background='#1c1c1c', foreground='#cccccc', font=("Arial", 9))
        
        # 主框架
        main_frame = tk.Frame(self.root, bg='#1c1c1c')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题
        header = ttk.Label(main_frame, text="欢迎使用 Butler!", style="Header.TLabel")
        header.pack(pady=(0, 10))
        
        # 说明文本
        info = ttk.Label(main_frame, 
                        text="请配置以下 API 密钥以开启全部功能。\n必需项为 DeepSeek，其他为可选。\n系统会自动验证密钥有效性。",
                        style="Info.TLabel", justify=tk.LEFT)
        info.pack(pady=(0, 20))
        
        # 表单框架（使用 Canvas 支持滚动）
        canvas = tk.Canvas(main_frame, bg='#1c1c1c', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1c1c1c')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 添加表单字段
        for env_key, label_text, required in self.fields:
            row = tk.Frame(scrollable_frame, bg='#1c1c1c')
            row.pack(fill=tk.X, pady=8)
            
            # 标签
            required_mark = " *" if required else ""
            lbl = tk.Label(row, text=label_text + required_mark, bg='#1c1c1c', fg='#ffffff', 
                          width=30, anchor='w', font=("Arial", 9))
            lbl.pack(side=tk.LEFT)
            
            # 输入框
            val = os.getenv(env_key, "")
            if "YOUR_" in val:
                val = ""
            
            ent = tk.Entry(row, bg='#000000', fg='#00ff00', insertbackground='#00ff00', 
                          borderwidth=1, font=("Arial", 9))
            ent.insert(0, val)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            
            # 状态指示器
            status_label = tk.Label(row, text="○", bg='#1c1c1c', fg='#888888', 
                                   font=("Arial", 12), width=2)
            status_label.pack(side=tk.LEFT, padx=(5, 0))
            
            self.entries[env_key] = {
                'entry': ent,
                'status_label': status_label,
                'required': required,
                'env_key': env_key
            }
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 按钮框架
        btn_frame = tk.Frame(main_frame, bg='#1c1c1c')
        btn_frame.pack(pady=20, fill=tk.X)
        
        # 测试按钮
        test_btn = tk.Button(btn_frame, text="🧪 测试密钥", command=self.test_api_keys,
                            bg='#444444', fg='#ffffff', padx=15, pady=8, borderwidth=0,
                            font=("Arial", 10), cursor="hand2")
        test_btn.pack(side=tk.LEFT, padx=5)
        
        # 保存并启动按钮
        save_btn = tk.Button(btn_frame, text="✅ 保存并启动", command=self.save_and_close,
                            bg='#00aa00', fg='#000000', padx=20, pady=8, borderwidth=0,
                            font=("Arial", 10, "bold"), cursor="hand2")
        save_btn.pack(side=tk.LEFT, padx=5)
        
        # 跳过按钮
        skip_btn = tk.Button(btn_frame, text="⏭️ 稍后配置", command=self.skip_setup,
                            bg='#333333', fg='#ffffff', padx=15, pady=8, borderwidth=0,
                            font=("Arial", 10), cursor="hand2")
        skip_btn.pack(side=tk.LEFT, padx=5)
        
        # 状态消息框
        self.status_text = scrolledtext.ScrolledText(main_frame, height=5, width=70,
                                                     bg='#000000', fg='#00ff00',
                                                     font=("Courier", 8),
                                                     borderwidth=1)
        self.status_text.pack(pady=(10, 0), fill=tk.BOTH, expand=True)

    def test_api_keys(self):
        """测试 API 密钥有效性"""
        self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, "🔍 正在验证 API 密钥...\n")
        self.root.update()
        
        # 在后台线程中执行测试
        threading.Thread(target=self._test_keys_background, daemon=True).start()

    def _test_keys_background(self):
        """后台验证 API 密钥"""
        deepseek_key = self.entries["DEEPSEEK_API_KEY"]['entry'].get().strip()
        
        # 清空之前的验证结果
        self.validation_results.clear()
        
        # 验证 DeepSeek
        if deepseek_key:
            self.status_text.insert(tk.END, "\n📍 测试 DeepSeek API...")
            self.root.update()
            
            result = self._validate_deepseek_key(deepseek_key)
            if result['valid']:
                self.status_text.insert(tk.END, " ✅\n")
                self.validation_results['DEEPSEEK_API_KEY'] = True
                self._update_status_indicator('DEEPSEEK_API_KEY', True)
            else:
                self.status_text.insert(tk.END, f" ❌\n   错误: {result['error']}\n")
                self.validation_results['DEEPSEEK_API_KEY'] = False
                self._update_status_indicator('DEEPSEEK_API_KEY', False)
        else:
            self.status_text.insert(tk.END, "\n⚠️ DeepSeek API Key 未填写\n")
            self._update_status_indicator('DEEPSEEK_API_KEY', False)
        
        # 验证 Baidu（如果填写）
        baidu_app_id = self.entries["BAIDU_APP_ID"]['entry'].get().strip()
        if baidu_app_id:
            self.status_text.insert(tk.END, "\n📍 测试 Baidu API...")
            self.root.update()
            
            result = self._validate_baidu_key(baidu_app_id)
            if result['valid']:
                self.status_text.insert(tk.END, " ✅\n")
                self.validation_results['BAIDU_API_KEY'] = True
                self._update_status_indicator('BAIDU_APP_ID', True)
            else:
                self.status_text.insert(tk.END, f" ❌\n   错误: {result['error']}\n")
                self.validation_results['BAIDU_API_KEY'] = False
                self._update_status_indicator('BAIDU_APP_ID', False)
        
        # 总结
        self.status_text.insert(tk.END, "\n" + "="*50)
        if self.validation_results.get('DEEPSEEK_API_KEY', False):
            self.status_text.insert(tk.END, "\n✅ 验证完成！所有必需的密钥都已有效。\n")
        else:
            self.status_text.insert(tk.END, "\n⚠️ 请检查必需的 API 密钥。\n")
        
        self.root.update()

    def _validate_deepseek_key(self, api_key: str) -> dict:
        """验证 DeepSeek API 密钥"""
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1
                },
                timeout=5
            )
            
            if response.status_code == 200:
                return {'valid': True}
            elif response.status_code == 401:
                return {'valid': False, 'error': '密钥无效或已过期'}
            elif response.status_code == 429:
                return {'valid': False, 'error': '请求过于频繁'}
            else:
                return {'valid': False, 'error': f'HTTP {response.status_code}'}
        except requests.exceptions.Timeout:
            return {'valid': False, 'error': '连接超时'}
        except requests.exceptions.ConnectionError:
            return {'valid': False, 'error': '网络连接失败'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def _validate_baidu_key(self, app_id: str) -> dict:
        """验证 Baidu API 密钥（简单检查）"""
        try:
            if len(app_id) >= 5:  # Baidu App ID 通常足够长
                return {'valid': True}
            else:
                return {'valid': False, 'error': 'App ID 格式无效'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def _update_status_indicator(self, env_key: str, is_valid: bool):
        """更新状态指示器"""
        if env_key in self.entries:
            status_label = self.entries[env_key]['status_label']
            if is_valid:
                status_label.config(text="✅", fg='#00aa00')
            else:
                status_label.config(text="❌", fg='#ff4444')

    def save_and_close(self):
        """保存配置并关闭向导"""
        # 验证必需字段
        deepseek_key = self.entries["DEEPSEEK_API_KEY"]['entry'].get().strip()
        
        if not deepseek_key:
            messagebox.showerror("错误", "DeepSeek API Key 是必需的！")
            return
        
        if "YOUR_" in deepseek_key:
            messagebox.showerror("错误", "请填写真实的 API Key！")
            return
        
        # 保存所有密钥到 .env
        try:
            for env_key, _, _ in self.fields:
                value = self.entries[env_key]['entry'].get().strip()
                if value and "YOUR_" not in value:
                    set_key(self.env_path, env_key, value)
                    logger.info(f"已保存 {env_key}")
            
            # 保存配置标记
            self.setup_complete = True
            messagebox.showinfo("成功", "配置已保存！Butler 将在 3 秒后启动...")
            self.root.after(3000, self._close_wizard)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存配置：{str(e)}")
            logger.error(f"Failed to save config: {e}")

    def skip_setup(self):
        """跳过配置设置"""
        if messagebox.askyesno("确认", "确定要跳过配置吗？某些功能将无法使用。"):
            self.setup_complete = True
            self._close_wizard()

    def _close_wizard(self):
        """关闭向导"""
        if self.own_root:
            self.root.quit()
        else:
            self.root.destroy()


def show_config_wizard_if_needed():
    """检查是否需要显示配置向导（增强版）"""
    from package.core_utils.config_loader import config_loader
    
    # 检查是否已配置了必需的 API 密钥
    deepseek_key = config_loader.get("api.deepseek_key") or os.getenv("DEEPSEEK_API_KEY", "")
    
    if not deepseek_key or "YOUR_" in deepseek_key:
        logger.info("检测到缺少 API 密钥，显示配置向导")
        wizard = EnhancedConfigWizard()
        wizard.root.mainloop()
        return wizard.setup_complete
    
    return False
