import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import threading
from pathlib import Path
from typing import Dict, Any, List
from butler.core.api_validator import APIValidator
from butler.core.config_backup_manager import ConfigBackupManager
from butler.core.config_manager import config_manager
from butler.core.config_model import PROVIDER_DEFAULTS
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)


# 提供商显示选项
PROVIDER_CHOICES = [
    ("deepseek", "🤖 DeepSeek"),
    ("openai",   "🧠 OpenAI / 兼容格式"),
    ("zhipu",    "🇨🇳 智谱 AI (GLM)"),
    ("custom",   "🔧 自定义 API 地址"),
]

# provider -> (config_path, env_name)
PROVIDER_KEY_PATHS = {
    "deepseek": ("api.deepseek_key", "DEEPSEEK_API_KEY"),
    "openai":   ("api.openai_key",   "OPENAI_API_KEY"),
    "zhipu":    ("api.zhipu_key",    "ZHIPU_API_KEY"),
    "custom":   ("api.custom_key",   "CUSTOM_API_KEY"),
}


class ConfigWizardV2:
    """增强版配置向导 V2 - 支持多模型提供商选择"""

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
        self.root.geometry("760x820")
        self.root.configure(bg='#1c1c1c')

        self.backup_manager = ConfigBackupManager()
        self.validator = APIValidator()

        # 提供商选择变量
        self.provider_var = tk.StringVar(value="deepseek")

        # 基础字段（不随提供商变化）
        self.base_fields = [
            ("BAIDU_APP_ID", "🎤 Baidu App ID:", False),
            ("BAIDU_API_KEY", "🎤 Baidu API Key:", False),
            ("BAIDU_SECRET_KEY", "🎤 Baidu Secret Key:", False),
            ("PICOVOICE_ACCESS_KEY", "🎙️ Picovoice Access Key:", False),
        ]

        # 动态字段容器
        self.entries = {}
        self.status_labels = {}

        self._setup_ui()
        self._load_current_values()

    # ---------- UI 构建 ----------
    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background='#1c1c1c', borderwidth=0)
        style.configure("TNotebook.Tab", background='#333333', foreground='#ffffff', padding=[10, 5])
        style.map("TNotebook.Tab",
                  background=[("selected", "#00ff00")],
                  foreground=[("selected", "#000000")])

        main_frame = tk.Frame(self.root, bg='#1c1c1c')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.api_tab = tk.Frame(self.notebook, bg='#1c1c1c')
        self.notebook.add(self.api_tab, text=" 🔑 API 配置 ")
        self._setup_api_tab()

        self.mgmt_tab = tk.Frame(self.notebook, bg='#1c1c1c')
        self.notebook.add(self.mgmt_tab, text=" 🛠️ 管理工具 ")
        self._setup_mgmt_tab()

        bottom_frame = tk.Frame(main_frame, bg='#1c1c1c')
        bottom_frame.pack(fill=tk.X, pady=10)

        self.save_btn = tk.Button(bottom_frame, text="✅ 保存并应用",
                                  command=self.save_config,
                                  bg='#00aa00', fg='#000000',
                                  font=("Arial", 10, "bold"),
                                  padx=20, pady=8, borderwidth=0,
                                  cursor="hand2")
        self.save_btn.pack(side=tk.RIGHT, padx=5)

        self.close_btn = tk.Button(bottom_frame, text="关闭",
                                   command=self.root.destroy,
                                   bg='#444444', fg='#ffffff',
                                   font=("Arial", 10),
                                   padx=20, pady=8, borderwidth=0,
                                   cursor="hand2")
        self.close_btn.pack(side=tk.RIGHT, padx=5)

    def _setup_api_tab(self):
        content = tk.Frame(self.api_tab, bg='#1c1c1c', padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="配置您的 API 以启用核心 AI 功能",
                 bg='#1c1c1c', fg='#00ff00',
                 font=("Arial", 12, "bold")).pack(anchor='w', pady=(0, 15))

        # ---- ① 提供商选择 ----
        provider_box = tk.LabelFrame(content, text="① 选择 AI 模型服务商",
                                     bg='#1c1c1c', fg='#00ff00',
                                     font=("Arial", 10, "bold"),
                                     padx=12, pady=10,
                                     labelanchor='nw', relief=tk.GROOVE)
        provider_box.pack(fill=tk.X, pady=(0, 12))

        pv_row = tk.Frame(provider_box, bg='#1c1c1c')
        pv_row.pack(fill=tk.X)
        for i, (pid, label) in enumerate(PROVIDER_CHOICES):
            tk.Radiobutton(pv_row, text=label, variable=self.provider_var,
                           value=pid, bg='#1c1c1c', fg='#ffffff',
                           selectcolor='#1c1c1c', activebackground='#1c1c1c',
                           activeforeground='#00ff00', font=("Arial", 10, "bold"),
                           cursor="hand2",
                           command=self._on_provider_change).grid(
                row=0, column=i, padx=8, sticky='w')

        # ---- ② AI 配置动态区 ----
        self.ai_cfg_frame = tk.LabelFrame(content,
                                          text="② AI 服务商配置 (API 地址 / 模型 / 密钥)",
                                          bg='#1c1c1c', fg='#00ff00',
                                          font=("Arial", 10, "bold"),
                                          padx=12, pady=10,
                                          labelanchor='nw', relief=tk.GROOVE)
        self.ai_cfg_frame.pack(fill=tk.X, pady=(0, 12))
        self._build_ai_provider_fields()

        # ---- ③ 其他服务 ----
        other_box = tk.LabelFrame(content, text="③ 其他服务 (可选)",
                                  bg='#1c1c1c', fg='#00ff00',
                                  font=("Arial", 10, "bold"),
                                  padx=12, pady=10,
                                  labelanchor='nw', relief=tk.GROOVE)
        other_box.pack(fill=tk.X, pady=(0, 12))

        other_form = tk.Frame(other_box, bg='#1c1c1c')
        other_form.pack(fill=tk.X)

        for i, (key, label, required) in enumerate(self.base_fields):
            lbl = tk.Label(other_form, text=label, bg='#1c1c1c', fg='#ffffff',
                          width=30, anchor='w')
            lbl.grid(row=i, column=0, pady=6, sticky='w')

            ent = tk.Entry(other_form, bg='#000000', fg='#00ff00',
                          insertbackground='#00ff00', width=40,
                          font=("Arial", 10))
            ent.grid(row=i, column=1, pady=6, sticky='ew')
            self.entries[key] = ent

            status = tk.Label(other_form, text="○", bg='#1c1c1c', fg='#888888',
                             font=("Arial", 12))
            status.grid(row=i, column=2, padx=8)
            self.status_labels[key] = status

        other_form.columnconfigure(1, weight=1)

        # ---- 按钮 & 结果 ----
        btn_row = tk.Frame(content, bg='#1c1c1c')
        btn_row.pack(fill=tk.X, pady=(5, 10))

        tk.Button(btn_row, text="🧪 批量验证 API", command=self.run_validation,
                  bg='#0078d4', fg='#ffffff', padx=15, pady=5,
                  borderwidth=0).pack(side=tk.LEFT)

        self.result_box = scrolledtext.ScrolledText(content, height=8,
                                                    bg='#000000', fg='#00ff00',
                                                    font=("Courier", 9),
                                                    borderwidth=0)
        self.result_box.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _build_ai_provider_fields(self):
        """重建 AI 提供商相关的表单字段（provider 切换时调用）。"""
        for w in self.ai_cfg_frame.winfo_children():
            w.destroy()

        pid = self.provider_var.get()
        defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])
        display_name = defaults["display_name"]
        default_url = defaults["base_url"] or ""
        default_model = defaults["model_name"] or ""
        key_env = defaults["key_env"]

        form = tk.Frame(self.ai_cfg_frame, bg='#1c1c1c')
        form.pack(fill=tk.X)

        required_custom = (pid == "custom")
        row_i = 0

        # --- base_url ---
        url_label = f"🌐 API 基础地址{' *' if required_custom else ' (可选)'}:"
        tk.Label(form, text=url_label, bg='#1c1c1c', fg='#ffffff',
                width=30, anchor='w').grid(row=row_i, column=0, pady=6, sticky='w')

        ent_url = tk.Entry(form, bg='#000000', fg='#00ff00',
                          insertbackground='#00ff00', width=40,
                          font=("Arial", 10))
        ent_url.grid(row=row_i, column=1, pady=6, sticky='ew')

        if default_url and not required_custom:
            url_hint = f"留空使用默认：{default_url}"
        else:
            url_hint = "例如: http://localhost:11434/v1"
        tk.Label(form, text=url_hint, bg='#1c1c1c', fg='#66aa66',
                font=("Arial", 8)).grid(row=row_i, column=2, padx=8, sticky='w')
        self.entries["_AI_BASE_URL"] = ent_url
        row_i += 1

        # --- model_name ---
        model_label = f"📋 模型名称{' *' if required_custom else ' (可选)'}:"
        tk.Label(form, text=model_label, bg='#1c1c1c', fg='#ffffff',
                width=30, anchor='w').grid(row=row_i, column=0, pady=6, sticky='w')

        ent_model = tk.Entry(form, bg='#000000', fg='#00ff00',
                            insertbackground='#00ff00', width=40,
                            font=("Arial", 10))
        ent_model.grid(row=row_i, column=1, pady=6, sticky='ew')

        if default_model and not required_custom:
            model_hint = f"留空使用默认：{default_model}"
        else:
            model_hint = "例如: qwen2.5:7b"
        tk.Label(form, text=model_hint, bg='#1c1c1c', fg='#66aa66',
                font=("Arial", 8)).grid(row=row_i, column=2, padx=8, sticky='w')
        self.entries["_AI_MODEL_NAME"] = ent_model
        row_i += 1

        # --- api_key ---
        key_label = f"🔑 {display_name} API Key *:"
        tk.Label(form, text=key_label, bg='#1c1c1c', fg='#ffffff',
                width=30, anchor='w').grid(row=row_i, column=0, pady=6, sticky='w')

        ent_key = tk.Entry(form, bg='#000000', fg='#00ff00',
                          insertbackground='#00ff00', width=40,
                          font=("Arial", 10))
        ent_key.grid(row=row_i, column=1, pady=6, sticky='ew')

        tk.Label(form, text=f"保存到 {key_env}", bg='#1c1c1c', fg='#66aa66',
                font=("Arial", 8)).grid(row=row_i, column=2, padx=8, sticky='w')

        self.entries["_AI_API_KEY"] = ent_key
        status_key = tk.Label(form, text="○", bg='#1c1c1c', fg='#888888',
                             font=("Arial", 12))
        status_key.grid(row=row_i, column=3, padx=8)
        self.status_labels["_AI_API_KEY"] = status_key

        form.columnconfigure(1, weight=1)

        # --- 预填已有值 ---
        current_base = config_manager.get("api.base_url") or os.getenv("API_BASE_URL", "")
        if current_base:
            ent_url.insert(0, current_base)

        current_model = config_manager.get("api.model_name") or os.getenv("MODEL_NAME", "")
        if current_model:
            ent_model.insert(0, current_model)

        cfg_path, env_name = PROVIDER_KEY_PATHS.get(pid, PROVIDER_KEY_PATHS["deepseek"])
        current_key = config_manager.get(cfg_path) or os.getenv(env_name, "")
        if current_key and "YOUR_" not in current_key:
            ent_key.insert(0, current_key)

    def _on_provider_change(self):
        self._build_ai_provider_fields()

    def _load_current_values(self):
        cur_provider = config_manager.get("api.provider") or os.getenv("AI_PROVIDER", "deepseek")
        if cur_provider in [p[0] for p in PROVIDER_CHOICES]:
            self.provider_var.set(cur_provider)
        self._on_provider_change()

        for key, _, _ in self.base_fields:
            ent = self.entries.get(key)
            if not ent:
                continue
            val = config_manager.get(f"api.{key.lower()}") or os.getenv(key, "")
            if "YOUR_" in str(val):
                val = ""
            ent.insert(0, str(val))

    # ---------- 管理工具 Tab ----------
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

        tk.Button(btn_col, text="创建备份", command=self.create_backup,
                  bg='#444444', fg='#ffffff').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_col, text="恢复选中", command=self.restore_backup,
                  bg='#444444', fg='#ffffff').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_col, text="删除选中", command=self.delete_backup,
                  bg='#a30000', fg='#ffffff').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_col, text="刷新列表", command=self.refresh_backups,
                  bg='#444444', fg='#ffffff').pack(side=tk.LEFT, padx=2)

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

        tk.Label(danger_frame,
                 text="重置功能将删除当前所有配置并恢复到初始模板状态。",
                 bg='#331111', fg='#cccccc', font=("Arial", 8)).pack(side=tk.LEFT)
        tk.Button(danger_frame, text="安全重置", command=self.perform_reset,
                  bg='#ff4444', fg='#ffffff',
                  font=("Arial", 9, "bold")).pack(side=tk.RIGHT)

        self.refresh_backups()

    # ---------- 读取表单值 ----------
    def _get_entry_val(self, key):
        ent = self.entries.get(key)
        if ent is None:
            return ""
        try:
            val = ent.get().strip()
        except Exception:
            return ""
        return val

    # ---------- 验证 ----------
    def run_validation(self):
        self.result_box.delete(1.0, tk.END)
        self.result_box.insert(tk.END, "开始验证 API 配置...\n" + "-" * 40 + "\n")

        pid = self.provider_var.get()
        defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])
        display_name = defaults["display_name"]

        base_url = self._get_entry_val("_AI_BASE_URL") or defaults["base_url"]
        model = self._get_entry_val("_AI_MODEL_NAME") or defaults["model_name"]
        api_key = self._get_entry_val("_AI_API_KEY")

        base_url = base_url.rstrip("/") if base_url else ""
        url = f"{base_url}/chat/completions" if base_url else ""

        self.result_box.insert(tk.END, f"\n📍 服务商: {display_name}")
        self.result_box.insert(tk.END, f"\n📍 URL: {url or '(空)'}")
        self.result_box.insert(tk.END, f"\n📍 模型: {model or '(空)'}")
        self.result_box.insert(tk.END, f"\n📍 密钥: {'已填写' if api_key and 'YOUR_' not in api_key else '未填写'}\n")

        config = {k: self._get_entry_val(k) for k, _, _ in self.base_fields}
        config["_AI_PROVIDER"] = pid
        config["_AI_URL"] = url
        config["_AI_MODEL"] = model
        config["_AI_KEY"] = api_key

        def _task():
            # AI 通用验证
            ai_ok = False
            if api_key and "YOUR_" not in api_key and url:
                self.result_box.insert(tk.END, f"\n🧪 测试 {display_name} API ...")
                self.root.update()
                r = self._validate_any_provider(url, api_key, model)
                if r.get("valid"):
                    self.result_box.insert(tk.END, " ✅\n")
                    ai_ok = True
                    if "_AI_API_KEY" in self.status_labels:
                        self.status_labels["_AI_API_KEY"].config(text="✅", fg="#00ff00")
                else:
                    self.result_box.insert(tk.END, f" ❌  {r.get('error', '未知错误')}\n")
                    if "_AI_API_KEY" in self.status_labels:
                        self.status_labels["_AI_API_KEY"].config(text="❌", fg="#ff4444")
            elif not api_key or "YOUR_" in api_key:
                self.result_box.insert(tk.END, "\n⚠️ AI API Key 未填写或为占位符。\n")

            # Baidu 简单校验 (长度)
            for env_key, label, _ in self.base_fields:
                v = config.get(env_key, "")
                lbl = self.status_labels.get(env_key)
                if v and len(v) >= 5:
                    self.result_box.insert(tk.END, f"OK  - {env_key} (格式校验通过)\n")
                    if lbl:
                        lbl.config(text="✅", fg="#00ff00")
                elif v:
                    self.result_box.insert(tk.END, f"ERR - {env_key} (长度可能不足)\n")
                    if lbl:
                        lbl.config(text="❌", fg="#ff4444")

            self.result_box.insert(tk.END, "\n验证完成。")

        threading.Thread(target=_task, daemon=True).start()

    def _validate_any_provider(self, url, api_key, model):
        import requests as _req
        try:
            r = _req.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                    "temperature": 0,
                },
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                if "choices" in data:
                    return {"valid": True}
                return {"valid": False, "error": f"响应格式异常: {str(data)[:100]}"}
            elif r.status_code == 401:
                return {"valid": False, "error": "认证失败 (401)：密钥无效"}
            elif r.status_code == 404:
                return {"valid": False, "error": f"地址 404：{url}"}
            elif r.status_code == 429:
                return {"valid": False, "error": "请求过于频繁 (429)"}
            else:
                try:
                    msg = r.json()
                except Exception:
                    msg = r.text
                return {"valid": False, "error": f"HTTP {r.status_code}: {str(msg)[:150]}"}
        except _req.exceptions.Timeout:
            return {"valid": False, "error": "连接超时"}
        except _req.exceptions.ConnectionError:
            return {"valid": False, "error": "网络连接失败，请检查地址/端口"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    # ---------- 保存 ----------
    def save_config(self):
        pid = self.provider_var.get()
        defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])
        key_env = defaults["key_env"]
        display_name = defaults["display_name"]

        base_url = self._get_entry_val("_AI_BASE_URL")
        model_name = self._get_entry_val("_AI_MODEL_NAME")
        api_key = self._get_entry_val("_AI_API_KEY")

        # 简单校验
        if not api_key or "YOUR_" in api_key:
            messagebox.showerror("错误", f"{display_name} API Key 是必需的！")
            return
        if pid == "custom":
            if not base_url:
                messagebox.showerror("错误", "自定义模式下 API 基础地址是必需的！")
                return
            if not model_name:
                messagebox.showerror("错误", "自定义模式下模型名称是必需的！")
                return

        try:
            # Provider / URL / Model
            config_manager.set("api.provider", pid, persist=True)
            config_manager.set("api.base_url", base_url, persist=True)
            config_manager.set("api.model_name", model_name, persist=True)

            # 当前 provider 的 key
            cfg_path, _ = PROVIDER_KEY_PATHS.get(pid, PROVIDER_KEY_PATHS["deepseek"])
            config_manager.set(cfg_path, api_key, persist=True)

            # 其他字段
            for key, _, _ in self.base_fields:
                val = self._get_entry_val(key)
                config_manager.set(f"api.{key.lower()}", val, persist=True)

            messagebox.showinfo("成功",
                                f"✅ 配置已保存！\n\n"
                                f"提供商: {display_name}\n"
                                f"密钥保存至: {key_env}\n\n"
                                f"部分更改可能需要重启程序。")
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存配置：{str(e)}")
            logger.error(f"Failed to save config: {e}")

    # ---------- 备份管理 ----------
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
        if not idx:
            return
        backup_name = self.backups_data[idx[0]]['name']
        if messagebox.askyesno("确认",
                               f"确定要恢复备份 {backup_name} 吗？当前配置将被覆盖。"):
            if self.backup_manager.restore_backup(backup_name):
                messagebox.showinfo("成功", "配置已恢复，请重启程序。")
                config_manager.reload()
                self._load_current_values()

    def delete_backup(self):
        idx = self.backup_list.curselection()
        if not idx:
            return
        backup_name = self.backups_data[idx[0]]['name']
        if self.backup_manager.delete_backup(backup_name):
            self.refresh_backups()

    def export_zip(self):
        path = filedialog.asksaveasfilename(defaultextension=".zip",
                                             filetypes=[("ZIP files", "*.zip")])
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
