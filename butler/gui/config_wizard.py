import tkinter as tk
from tkinter import ttk, messagebox
import os
from pathlib import Path
from dotenv import load_dotenv, set_key

class ConfigWizard:
    def __init__(self, root=None):
        self.own_root = False
        if root is None:
            self.root = tk.Tk()
            self.own_root = True
        else:
            self.root = tk.Toplevel(root)
            self.root.transient(root)
            self.root.grab_set()

        self.root.title("Butler - 初始配置向导")
        self.root.geometry("500x450")
        self.root.configure(bg='#1c1c1c')

        self.env_path = Path(".env")
        load_dotenv(self.env_path)

        self.fields = [
            ("DEEPSEEK_API_KEY", "DeepSeek API Key (核心对话功能):"),
            ("BAIDU_APP_ID", "Baidu App ID (语音功能 - 可选):"),
            ("BAIDU_API_KEY", "Baidu API Key (语音功能 - 可选):"),
            ("BAIDU_SECRET_KEY", "Baidu Secret Key (语音功能 - 可选):"),
            ("PICOVOICE_ACCESS_KEY", "Picovoice Access Key (唤醒词 - 可选):"),
        ]
        self.entries = {}
        self._setup_ui()

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TLabel", background='#1c1c1c', foreground='#ffffff', font=("Arial", 10))
        style.configure("TEntry", fieldbackground='#000000', foreground='#00ff00')

        header = tk.Label(self.root, text="欢迎使用 Butler！", font=("Arial", 16, "bold"), bg='#1c1c1c', fg='#00ff00')
        header.pack(pady=20)

        info = tk.Label(self.root, text="请配置以下 API 密钥以开启全部功能。\n您可以现在输入，也可以稍后在 .env 文件中修改。",
                        bg='#1c1c1c', fg='#cccccc', font=("Arial", 9))
        info.pack(pady=(0, 20))

        form_frame = tk.Frame(self.root, bg='#1c1c1c')
        form_frame.pack(padx=30, fill=tk.X)

        for env_key, label_text in self.fields:
            row = tk.Frame(form_frame, bg='#1c1c1c')
            row.pack(fill=tk.X, pady=5)

            lbl = tk.Label(row, text=label_text, bg='#1c1c1c', fg='#ffffff', width=25, anchor='w')
            lbl.pack(side=tk.LEFT)

            val = os.getenv(env_key, "")
            if "YOUR_" in val: val = "" # Clear placeholder

            ent = tk.Entry(row, bg='#000000', fg='#00ff00', insertbackground='#00ff00', borderwidth=0)
            ent.insert(0, val)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[env_key] = ent

        btn_frame = tk.Frame(self.root, bg='#1c1c1c')
        btn_frame.pack(pady=30)

        save_btn = tk.Button(btn_frame, text="保存并启动", command=self.save_and_close,
                             bg='#333333', fg='#ffffff', padx=20, borderwidth=0)
        save_btn.pack(side=tk.LEFT, padx=10)

        skip_btn = tk.Button(btn_frame, text="稍后配置", command=self.close,
                              bg='#1c1c1c', fg='#aaaaaa', padx=20, borderwidth=0)
        skip_btn.pack(side=tk.LEFT, padx=10)

    def save_and_close(self):
        if not self.env_path.exists():
            self.env_path.touch()

        for env_key, entry in self.entries.items():
            val = entry.get().strip()
            if val:
                set_key(str(self.env_path), env_key, val)

        messagebox.showinfo("成功", "配置已保存！")
        self.close()

    def close(self):
        if self.own_root:
            self.root.destroy()
        else:
            self.root.grab_release()
            self.root.destroy()

    def run(self):
        if self.own_root:
            self.root.mainloop()

def show_config_wizard_if_needed(root=None):
    # Check if critical keys are missing or placeholder
    critical_key = "DEEPSEEK_API_KEY"
    val = os.getenv(critical_key, "")
    if not val or "YOUR_" in val:
        wizard = ConfigWizard(root)
        if wizard.own_root:
            wizard.run()
        return True
    return False

if __name__ == "__main__":
    show_config_wizard_if_needed()
