import tkinter as tk
from tkinter import messagebox, ttk
import os
from pathlib import Path
from butler.core.config_loader import config_loader

class ConfigWizard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Butler - Configuration Wizard")
        self.root.geometry("500x350")
        self.root.configure(bg="#f0f0f0")

        self.project_root = Path(__file__).resolve().parent.parent
        self.env_path = self.project_root / ".env"

        self._setup_ui()

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="欢迎使用 Butler 助手", font=("Arial", 14, "bold")).pack(pady=(0, 10))
        ttk.Label(main_frame, text="未检测到必要的 API 配置，请填写以下信息：", font=("Arial", 10)).pack(pady=(0, 20))

        # DeepSeek API Key
        ttk.Label(main_frame, text="DeepSeek API Key:").pack(anchor=tk.W)
        self.api_key_entry = ttk.Entry(main_frame, width=50, show="*")
        self.api_key_entry.pack(fill=tk.X, pady=(5, 15))

        # Initialize with existing key if available
        existing_key = config_loader.get("api.deepseek.key")
        if existing_key and "YOUR_" not in existing_key:
            self.api_key_entry.insert(0, existing_key)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=20)

        self.test_btn = ttk.Button(btn_frame, text="测试连接", command=self.test_connection)
        self.test_btn.pack(side=tk.LEFT, padx=5)

        self.save_btn = ttk.Button(btn_frame, text="保存并启动", command=self.save_config)
        self.save_btn.pack(side=tk.RIGHT, padx=5)

    def test_connection(self):
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("错误", "请输入 API Key")
            return

        self.test_btn.config(state=tk.DISABLED, text="测试中...")
        self.root.update()

        try:
            import requests
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5
            }
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                messagebox.showinfo("成功", "连接测试成功！")
            else:
                messagebox.showerror("失败", f"测试失败，状态码: {response.status_code}\n{response.text}")
        except Exception as e:
            messagebox.showerror("错误", f"请求出错: {e}")
        finally:
            self.test_btn.config(state=tk.NORMAL, text="测试连接")

    def save_config(self):
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("错误", "请输入 API Key")
            return

        # Update .env file
        env_content = ""
        if self.env_path.exists():
            with open(self.env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                key_found = False
                for line in lines:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        env_content += f"DEEPSEEK_API_KEY={api_key}\n"
                        key_found = True
                    else:
                        env_content += line
                if not key_found:
                    env_content += f"\nDEEPSEEK_API_KEY={api_key}\n"
        else:
            env_content = f"DEEPSEEK_API_KEY={api_key}\n"

        with open(self.env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)

        # Update system_config.json via config_loader
        config_loader.save({"api": {"deepseek": {"key": api_key}}})

        messagebox.showinfo("成功", "配置已保存，正在启动程序...")
        self.root.destroy()

    def run(self):
        self.root.mainloop()

def check_config_and_run_wizard():
    api_key = config_loader.get("api.deepseek.key")
    if not api_key or "YOUR_" in api_key:
        wizard = ConfigWizard()
        wizard.run()
        # Reload config after wizard
        config_loader._load()
        return True
    return False

if __name__ == "__main__":
    check_config_and_run_wizard()
