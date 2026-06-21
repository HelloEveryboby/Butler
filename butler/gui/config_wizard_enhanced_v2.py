import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import threading
from pathlib import Path
from typing import Dict, Any, List
from butler.core.api_validator import APIValidator
from butler.core.config_backup_manager import ConfigBackupManager
from butler.core.config_manager import config_manager
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class ConfigWizardV2:
    """增强版配置向导 V2 - 包含管理功能"""

    def __init__(self, root=None):
        self.own_root = False
        if root is None:
            self.root = tk.Tk()
            self.own_root = True
        else:
            self.root = tk.Toplevel(root)
            self.root.transient(root)
            self.root.grab_set()

        self.root.title("Butler 配置向导 V2")
        self.root.geometry("700x750")
        self.root.configure(bg='#1c1c1c')

        self.backup_manager = ConfigBackupManager()
        self.validator = APIValidator()

        # API 字段定义
        self.api_fields = [
            ("DEEPSEEK_API_KEY", "🤖 DeepSeek API Key:", True),
            ("BAIDU_APP_ID", "🎤 Baidu App ID:", False),
            ("BAIDU_API_KEY", "🎤 Baidu API Key:", False),
            ("BAIDU_SECRET_KEY", "🎤 Baidu Secret Key:", False),
            ("PICOVOICE_ACCESS_KEY", "🎙️ Picovoice Access Key:", False),
        ]
        self.entries = {}
        self.status_labels = {}

        self._setup_ui()
        self._load_current_values()

    def _setup_ui(self):
        # 样式
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background='#1c1c1c', borderwidth=0)
        style.configure("TNotebook.Tab", background='#333333', foreground='#ffffff', padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", "#00ff00")], foreground=[("selected", "#000000")])

        # 主框架
        main_frame = tk.Frame(self.root, bg='#1c1c1c')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 标签页
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: API 配置
        self.api_tab = tk.Frame(self.notebook, bg='#1c1c1c')
        self.notebook.add(self.api_tab, text=" 🔑 API 配置 ")
        self._setup_api_tab()

        # Tab 2: 管理功能
        self.mgmt_tab = tk.Frame(self.notebook, bg='#1c1c1c')
        self.notebook.add(self.mgmt_tab, text=" 🛠️ 管理工具 ")
        self._setup_mgmt_tab()

        # 底部按钮区
        bottom_frame = tk.Frame(main_frame, bg='#1c1c1c')
        bottom_frame.pack(fill=tk.X, pady=10)

        self.save_btn = tk.Button(bottom_frame, text="✅ 保存并应用", command=self.save_config,
                                 bg='#00aa00', fg='#000000', font=("Arial", 10, "bold"),
                                 padx=20, pady=8, borderwidth=0, cursor="hand2")
        self.save_btn.pack(side=tk.RIGHT, padx=5)

        self.close_btn = tk.Button(bottom_frame, text="关闭", command=self.root.destroy,
                                  bg='#444444', fg='#ffffff', font=("Arial", 10),
                                  padx=20, pady=8, borderwidth=0, cursor="hand2")
        self.close_btn.pack(side=tk.RIGHT, padx=5)

    def _setup_api_tab(self):
        content = tk.Frame(self.api_tab, bg='#1c1c1c', padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="配置您的 API 密钥以启用核心功能",
                 bg='#1c1c1c', fg='#00ff00', font=("Arial", 12, "bold")).pack(anchor='w', pady=(0, 20))

        form = tk.Frame(content, bg='#1c1c1c')
        form.pack(fill=tk.X)

        for i, (key, label, required) in enumerate(self.api_fields):
            lbl = tk.Label(form, text=label + (" *" if required else ""),
                          bg='#1c1c1c', fg='#ffffff', width=25, anchor='w')
            lbl.grid(row=i, column=0, pady=10, sticky='w')

            ent = tk.Entry(form, bg='#000000', fg='#00ff00', insertbackground='#00ff00',
                          width=40, font=("Arial", 10))
            ent.grid(row=i, column=1, pady=10, sticky='ew')
            self.entries[key] = ent

            status = tk.Label(form, text="○", bg='#1c1c1c', fg='#888888', font=("Arial", 12))
            status.grid(row=i, column=2, padx=10)
            self.status_labels[key] = status

        form.columnconfigure(1, weight=1)

        btn_row = tk.Frame(content, bg='#1c1c1c')
        btn_row.pack(fill=tk.X, pady=20)

        tk.Button(btn_row, text="🧪 批量验证 API", command=self.run_validation,
                  bg='#0078d4', fg='#ffffff', padx=15, pady=5, borderwidth=0).pack(side=tk.LEFT)

        # 结果显示
        self.result_box = scrolledtext.ScrolledText(content, height=10, bg='#000000', fg='#00ff00',
                                                   font=("Courier", 9), borderwidth=0)
        self.result_box.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    def _setup_mgmt_tab(self):
        content = tk.Frame(self.mgmt_tab, bg='#1c1c1c', padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        # 备份管理区
        tk.Label(content, text="💾 备份与恢复", bg='#1c1c1c', fg='#00ff00',
                 font=("Arial", 11, "bold")).pack(anchor='w', pady=(0, 10))

        backup_frame = tk.Frame(content, bg='#252525', padx=10, pady=10)
        backup_frame.pack(fill=tk.X, pady=(0, 20))

        self.backup_list = tk.Listbox(backup_frame, bg='#000000', fg='#ffffff', height=6,
                                     borderwidth=0, font=("Arial", 9))
        self.backup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(backup_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.backup_list.config(yscrollcommand=sb.set)
        sb.config(command=self.backup_list.yview)

        btn_col = tk.Frame(content, bg='#1c1c1c')
        btn_col.pack(fill=tk.X)

        tk.Button(btn_col, text="创建备份", command=self.create_backup, bg='#444444', fg='#ffffff').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_col, text="恢复选中", command=self.restore_backup, bg='#444444', fg='#ffffff').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_col, text="删除选中", command=self.delete_backup, bg='#a30000', fg='#ffffff').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_col, text="刷新列表", command=self.refresh_backups, bg='#444444', fg='#ffffff').pack(side=tk.LEFT, padx=2)

        # 导入导出区
        tk.Label(content, text="📦 导入与导出", bg='#1c1c1c', fg='#00ff00',
                 font=("Arial", 11, "bold")).pack(anchor='w', pady=(20, 10))

        io_frame = tk.Frame(content, bg='#1c1c1c')
        io_frame.pack(fill=tk.X)

        tk.Button(io_frame, text="📤 导出配置 (ZIP)", command=self.export_zip,
                  bg='#0078d4', fg='#ffffff', width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(io_frame, text="📥 导入配置 (ZIP)", command=self.import_zip,
                  bg='#0078d4', fg='#ffffff', width=15).pack(side=tk.LEFT, padx=5)

        # 危险区
        tk.Label(content, text="⚠️ 危险操作", bg='#1c1c1c', fg='#ff4444',
                 font=("Arial", 11, "bold")).pack(anchor='w', pady=(30, 10))

        danger_frame = tk.Frame(content, bg='#331111', padx=10, pady=10)
        danger_frame.pack(fill=tk.X)

        tk.Label(danger_frame, text="重置功能将删除当前所有配置并恢复到初始模板状态。",
                 bg='#331111', fg='#cccccc', font=("Arial", 8)).pack(side=tk.LEFT)
        tk.Button(danger_frame, text="安全重置", command=self.perform_reset,
                  bg='#ff4444', fg='#ffffff', font=("Arial", 9, "bold")).pack(side=tk.RIGHT)

        self.refresh_backups()

    def _load_current_values(self):
        for key, entry in self.entries.items():
            val = config_manager.get(f"api.{key.lower()}") or os.getenv(key, "")
            if "YOUR_" in str(val):
                val = ""
            entry.insert(0, str(val))

    def run_validation(self):
        self.result_box.delete(1.0, tk.END)
        self.result_box.insert(tk.END, "开始验证 API 密钥...\n" + "-"*40 + "\n")

        config = {k: v.get().strip() for k, v in self.entries.items()}

        def _task():
            results = self.validator.validate_all(config)
            self.root.after(0, lambda: self._update_validation_ui(results))

        threading.Thread(target=_task, daemon=True).start()

    def _update_validation_ui(self, results: Dict[str, Any]):
        for key, res in results.items():
            status_lbl = self.status_labels.get(key)
            if res.get('valid'):
                status_lbl.config(text="✅", fg='#00ff00')
                self.result_box.insert(tk.END, f"OK  - {key}\n")
            else:
                status_lbl.config(text="❌", fg='#ff4444')
                err = res.get('error', '未知错误')
                self.result_box.insert(tk.END, f"ERR - {key}: {err}\n")

        self.result_box.insert(tk.END, "\n验证完成。")

    def save_config(self):
        for key, entry in self.entries.items():
            val = entry.get().strip()

            # 简单映射 key
            path = f"api.{key.lower()}"
            if key == "DEEPSEEK_API_KEY": path = "api.deepseek_key"
            elif key == "BAIDU_APP_ID": path = "api.baidu_app_id"
            elif key == "BAIDU_API_KEY": path = "api.baidu_api_key"
            elif key == "BAIDU_SECRET_KEY": path = "api.baidu_secret_key"

            # 即使为空也保存（允许清除）
            config_manager.set(path, val)

        messagebox.showinfo("成功", "配置已保存。部分更改可能需要重启程序。")

    # 备份管理逻辑
    def refresh_backups(self):
        self.backup_list.delete(0, tk.END)
        self.backups_data = self.backup_manager.list_backups()
        for b in self.backups_data:
            self.backup_list.insert(tk.END, f"{b['timestamp']} - {b['description']}")

    def create_backup(self):
        name = self.backup_manager.create_backup("Manual UI Backup")
        if name:
            self.refresh_backups()
            messagebox.showinfo("成功", f"备份 {name} 已创建")

    def restore_backup(self):
        idx = self.backup_list.curselection()
        if not idx: return

        backup_name = self.backups_data[idx[0]]['name']
        if messagebox.askyesno("确认", f"确定要恢复备份 {backup_name} 吗？当前配置将被覆盖。"):
            if self.backup_manager.restore_backup(backup_name):
                messagebox.showinfo("成功", "配置已恢复，请重启程序。")
                config_manager.reload()
                self._load_current_values()

    def delete_backup(self):
        idx = self.backup_list.curselection()
        if not idx: return

        backup_name = self.backups_data[idx[0]]['name']
        if self.backup_manager.delete_backup(backup_name):
            self.refresh_backups()

    def export_zip(self):
        path = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP files", "*.zip")])
        if path:
            if self.backup_manager.export_config(path):
                messagebox.showinfo("成功", f"配置已导出至 {path}")

    def import_zip(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")])
        if path:
            if self.backup_manager.import_config(path):
                messagebox.showinfo("成功", "配置已导入，请重启程序。")
                config_manager.reload()
                self._load_current_values()
                self.refresh_backups()

    def perform_reset(self):
        if messagebox.askyesno("强烈警告", "此操作将清除所有个人配置！确定要继续吗？"):
            if self.backup_manager.safe_reset():
                messagebox.showinfo("成功", "配置已重置。")
                config_manager.reload()
                self._load_current_values()
                self.refresh_backups()

if __name__ == "__main__":
    wizard = ConfigWizardV2()
    wizard.root.mainloop()
