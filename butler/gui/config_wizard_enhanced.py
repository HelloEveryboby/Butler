import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
from pathlib import Path
from dotenv import load_dotenv, set_key
import threading
import requests
import json
from package.core_utils.log_manager import LogManager
from butler.core.config_model import PROVIDER_DEFAULTS, PROVIDER_KEY_PATHS

logger = LogManager.get_logger(__name__)


# 提供商选项：(id, 显示名, 描述, 是否需要自定义地址)
PROVIDER_OPTIONS = [
    ("deepseek",  "🤖 DeepSeek", "官方默认 - 稳定、性价比高", False),
    ("openai",    "🧠 OpenAI / 兼容格式", "GPT 系列及兼容服务（如 OneAPI）", False),
    ("zhipu",     "🇨🇳 智谱 AI (GLM)", "国产大模型，中文能力优秀", False),
    ("anthropic", "🎭 Anthropic Claude", "Claude 3.5/4 系列", False),
    ("gemini",    "✨ Google Gemini", "Gemini 1.5/2.0 系列", False),
    ("dashscope", "🇨🇳 通义千问 (Qwen)", "阿里 DashScope，中文优秀", False),
    ("qianfan",   "🇨🇳 百度文心一言 (ERNIE)", "百度千帆平台", False),
    ("custom",    "🔧 自定义 API 地址", "Ollama / 本地部署 / 其他兼容 OpenAI 格式的服务", True),
]


class EnhancedConfigWizard:
    """增强的配置向导 V2 - 两步式：先选提供商，再填密钥"""

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
        self.root.geometry("620x720")
        self.root.configure(bg='#1c1c1c')

        self.env_path = Path(".env")
        load_dotenv(self.env_path)

        # 状态
        self.current_step = 1         # 1=选择提供商, 2=填写密钥
        self.selected_provider = "deepseek"
        self.entries = {}
        self.validation_results = {}
        self.setup_complete = False

        # 读取已有配置作为初始值
        self.existing_provider = os.getenv("AI_PROVIDER", "deepseek") or "deepseek"
        if self.existing_provider not in [p[0] for p in PROVIDER_OPTIONS]:
            self.existing_provider = "deepseek"

        self._setup_styles()
        self._build_ui()
        self._show_step(1)

    # ---------- 样式 ----------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Header.TLabel", background='#1c1c1c', foreground='#00ff00',
                        font=("Arial", 15, "bold"))
        style.configure("Step.TLabel", background='#1c1c1c', foreground='#88ff88',
                        font=("Arial", 11, "bold"))
        style.configure("Info.TLabel", background='#1c1c1c', foreground='#cccccc',
                        font=("Arial", 9))
        style.configure("Card.TFrame", background='#252525')

    # ---------- 主 UI ----------
    def _build_ui(self):
        self.main_frame = tk.Frame(self.root, bg='#1c1c1c')
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        ttk.Label(self.main_frame, text="🤖 Butler 配置向导", style="Header.TLabel").pack(pady=(0, 5))
        ttk.Label(self.main_frame,
                  text="两步完成 AI 能力配置：选择服务商 → 填入密钥",
                  style="Info.TLabel").pack(pady=(0, 15))

        # 步骤指示器
        self.step_indicator = tk.Frame(self.main_frame, bg='#1c1c1c')
        self.step_indicator.pack(fill=tk.X, pady=(0, 15))
        self._build_step_indicator()

        # 动态内容容器
        self.content_frame = tk.Frame(self.main_frame, bg='#1c1c1c')
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # 底部按钮
        self.btn_frame = tk.Frame(self.main_frame, bg='#1c1c1c')
        self.btn_frame.pack(pady=(15, 0), fill=tk.X)

    def _build_step_indicator(self):
        for w in self.step_indicator.winfo_children():
            w.destroy()

        steps = [
            (1, "选择模型服务商"),
            (2, "输入 API 密钥"),
        ]
        for i, (num, label) in enumerate(steps):
            active = (num == self.current_step)
            done = (num < self.current_step)

            bg = "#00aa00" if done or active else "#333333"
            fg = "#000000" if done or active else "#888888"

            # 圆圈
            circle = tk.Label(self.step_indicator, text=str(num),
                              bg=bg, fg=fg, width=3, height=1,
                              font=("Arial", 10, "bold"))
            circle.grid(row=0, column=i*2, padx=(0, 5))

            # 文字
            tk.Label(self.step_indicator, text=label,
                     bg='#1c1c1c',
                     fg="#00ff00" if active else ("#00aa00" if done else "#666666"),
                     font=("Arial", 10, "bold" if active else "normal")).grid(
                row=0, column=i*2 + 1, padx=(0, 20 if i < len(steps)-1 else 0), sticky='w')

            # 连接线
            if i < len(steps) - 1:
                tk.Frame(self.step_indicator, bg="#333333", width=40, height=2).grid(
                    row=0, column=i*2 + 2, pady=(0, 0))

    # ---------- 步骤 1: 选择提供商 ----------
    def _show_step(self, step):
        self.current_step = step
        self._build_step_indicator()

        for w in self.content_frame.winfo_children():
            w.destroy()
        for w in self.btn_frame.winfo_children():
            w.destroy()

        if step == 1:
            self._build_step1()
            self._build_buttons_step1()
        elif step == 2:
            self._build_step2()
            self._build_buttons_step2()

    def _build_step1(self):
        ttk.Label(self.content_frame, text="步骤 1 / 2 ：选择 AI 模型服务商",
                  style="Step.TLabel").pack(anchor='w', pady=(0, 10))

        self.provider_var = tk.StringVar(value=self.existing_provider)

        # 选项卡片
        card_frame = tk.Frame(self.content_frame, bg='#1c1c1c')
        card_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(card_frame, bg='#1c1c1c', highlightthickness=0)
        scrollbar = ttk.Scrollbar(card_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg='#1c1c1c')

        scrollable.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.provider_cards = {}
        for idx, (pid, name, desc, is_custom) in enumerate(PROVIDER_OPTIONS):
            card = self._make_provider_card(scrollable, pid, name, desc, is_custom)
            card.pack(fill=tk.X, pady=(0, 8), padx=2)
            self.provider_cards[pid] = card

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 选中默认项
        self._on_provider_select(self.existing_provider)

    def _make_provider_card(self, parent, pid, name, desc, is_custom):
        defaults = PROVIDER_DEFAULTS.get(pid, {})
        default_url = defaults.get("base_url", "")
        default_model = defaults.get("model_name", "")

        # 卡片容器
        card = tk.Frame(parent, bg='#252525', highlightthickness=1,
                        highlightbackground='#333333')
        inner = tk.Frame(card, bg='#252525', padx=12, pady=10)
        inner.pack(fill=tk.X)

        # 单选按钮 + 名称
        top_row = tk.Frame(inner, bg='#252525')
        top_row.pack(fill=tk.X)

        rb = tk.Radiobutton(top_row, variable=self.provider_var, value=pid,
                            text=name, bg='#252525', fg='#ffffff',
                            selectcolor='#252525', activebackground='#252525',
                            activeforeground='#00ff00', font=("Arial", 11, "bold"),
                            command=lambda p=pid: self._on_provider_select(p),
                            cursor="hand2")
        rb.pack(side=tk.LEFT)

        # 描述
        tk.Label(inner, text=desc, bg='#252525', fg='#aaaaaa',
                 font=("Arial", 8), wraplength=500, justify=tk.LEFT).pack(
            anchor='w', pady=(4, 0))

        # 默认信息
        info_txt = ""
        if not is_custom:
            info_txt = f"默认地址: {default_url}    默认模型: {default_model}"
        else:
            info_txt = "下一步可手动填写 API 基础地址和模型名称（兼容 OpenAI 格式，如 http://localhost:11434/v1）"

        tk.Label(inner, text=info_txt, bg='#252525', fg='#66aa66',
                 font=("Arial", 8), wraplength=500, justify=tk.LEFT).pack(
            anchor='w', pady=(4, 0))

        # 整个卡片点击也能选中
        def _on_click(e=None, p=pid):
            self.provider_var.set(p)
            self._on_provider_select(p)

        for w in (card, inner, top_row):
            w.bind("<Button-1>", _on_click)

        card._radio = rb
        card._pid = pid
        return card

    def _on_provider_select(self, pid):
        self.selected_provider = pid
        # 更新卡片高亮
        for cpid, card in self.provider_cards.items():
            selected = (cpid == pid)
            color = "#00aa00" if selected else "#333333"
            card.configure(highlightbackground=color, highlightthickness=2 if selected else 1)

    def _build_buttons_step1(self):
        tk.Button(self.btn_frame, text="下一步 →", command=self._goto_step2,
                  bg='#00aa00', fg='#000000', padx=25, pady=8, borderwidth=0,
                  font=("Arial", 10, "bold"), cursor="hand2").pack(side=tk.RIGHT, padx=5)

        tk.Button(self.btn_frame, text="⏭️ 稍后配置", command=self.skip_setup,
                  bg='#333333', fg='#ffffff', padx=15, pady=8, borderwidth=0,
                  font=("Arial", 10), cursor="hand2").pack(side=tk.RIGHT, padx=5)

    # ---------- 步骤 2: 填写密钥 ----------
    def _goto_step2(self):
        self._show_step(2)

    def _build_step2(self):
        pid = self.selected_provider
        defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])
        display_name = defaults["display_name"]
        key_env = defaults["key_env"]
        default_url = defaults["base_url"]
        default_model = defaults["model_name"]

        ttk.Label(self.content_frame,
                  text=f"步骤 2 / 2 ：配置 {display_name} API",
                  style="Step.TLabel").pack(anchor='w', pady=(0, 10))

        info = f"当前选择：{display_name}"
        ttk.Label(self.content_frame, text=info,
                  background='#1c1c1c', foreground='#00ff00',
                  font=("Arial", 10, "bold")).pack(anchor='w')

        # 表单卡片
        form_card = tk.Frame(self.content_frame, bg='#252525', padx=15, pady=15)
        form_card.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.entries = {}

        # 自定义 API 地址（仅 custom 时必填，其他可选填覆盖）
        row = 0
        if pid == "custom":
            self._add_form_field(form_card, row, "🏷️ 自定义名称（用于区分）", "CUSTOM_PROVIDER_NAME",
                                 f"例如: 我的Ollama", required=False)
            row += 1
            self._add_form_field(form_card, row, "🌐 API 基础地址 *", "base_url",
                                 f"例如: http://localhost:11434/v1", required=True)
            row += 1
            self._add_form_field(form_card, row, "📋 模型名称 *", "model_name",
                                 f"例如: qwen2.5:7b 或 llama3.1", required=True)
            row += 1
        else:
            # 其他提供商允许覆盖
            self._add_form_field(form_card, row, "🌐 API 基础地址 (可选)", "base_url",
                                 f"留空使用默认：{default_url}", required=False)
            row += 1
            self._add_form_field(form_card, row, "📋 模型名称 (可选)", "model_name",
                                 f"留空使用默认：{default_model}", required=False)
            row += 1

        # API 密钥
        self._add_form_field(form_card, row, f"🔑 {display_name} API Key *",
                             "api_key", f"将保存到环境变量 {key_env}", required=True)
        row += 1

        # 百度语音（可选，折叠在后面）
        ttk.Label(form_card, text="\n🎤 语音服务（可选，留空跳过）",
                  background='#252525', foreground='#88ff88',
                  font=("Arial", 10, "bold")).pack(anchor='w', pady=(15, 5))

        self._add_form_field(form_card, row, "Baidu App ID", "BAIDU_APP_ID", "", False)
        row += 1
        self._add_form_field(form_card, row, "Baidu API Key", "BAIDU_API_KEY", "", False)
        row += 1
        self._add_form_field(form_card, row, "Baidu Secret Key", "BAIDU_SECRET_KEY", "", False)
        row += 1
        self._add_form_field(form_card, row, "Picovoice Access Key", "PICOVOICE_ACCESS_KEY", "", False)
        row += 1

        # 底部状态
        self.status_text = scrolledtext.ScrolledText(self.content_frame, height=5,
                                                     bg='#000000', fg='#00ff00',
                                                     font=("Courier", 8), borderwidth=1)
        self.status_text.pack(fill=tk.BOTH, pady=(10, 0))
        self.status_text.insert(tk.END, "💡 提示：填写完毕后可点击「测试密钥」验证有效性\n")

    def _add_form_field(self, parent, row_idx, label, key, placeholder, required=False):
        row = tk.Frame(parent, bg='#252525')
        row.pack(fill=tk.X, pady=6)

        required_mark = " *" if required else ""
        lbl = tk.Label(row, text=label + required_mark, bg='#252525', fg='#ffffff',
                       width=24, anchor='w', font=("Arial", 9))
        lbl.pack(side=tk.LEFT)

        ent = tk.Entry(row, bg='#000000', fg='#00ff00', insertbackground='#00ff00',
                       borderwidth=1, font=("Arial", 9))

        # 预填已有值
        val = ""
        if key == "api_key":
            pid = self.selected_provider
            defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])
            key_env_name = defaults.get("key_env", "DEEPSEEK_API_KEY")
            val = os.getenv(key_env_name, "")
        elif key == "base_url":
            val = os.getenv("API_BASE_URL", "")
        elif key == "model_name":
            val = os.getenv("MODEL_NAME", "")
        elif key == "CUSTOM_PROVIDER_NAME":
            val = os.getenv("CUSTOM_PROVIDER_NAME", "")
        else:
            val = os.getenv(key, "")

        if "YOUR_" in val:
            val = ""
        if val:
            ent.insert(0, val)

        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        if placeholder and not val:
            # 用 insert 占位符的方式
            ent.config(fg='#555555')
            ent.insert(0, placeholder)
            def _on_focus_in(e, ph=placeholder):
                if ent.get() == ph:
                    ent.delete(0, tk.END)
                    ent.config(fg='#00ff00')
            def _on_focus_out(e, ph=placeholder):
                if ent.get() == "":
                    ent.insert(0, ph)
                    ent.config(fg='#555555')
            ent.bind("<FocusIn>", _on_focus_in)
            ent.bind("<FocusOut>", _on_focus_out)

        self.entries[key] = {'entry': ent, 'required': required, 'placeholder': placeholder}

    def _build_buttons_step2(self):
        # 测试
        tk.Button(self.btn_frame, text="🧪 测试密钥", command=self.test_api_keys,
                  bg='#444444', fg='#ffffff', padx=15, pady=8, borderwidth=0,
                  font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)
        # 上一步
        tk.Button(self.btn_frame, text="← 上一步", command=lambda: self._show_step(1),
                  bg='#333333', fg='#ffffff', padx=15, pady=8, borderwidth=0,
                  font=("Arial", 10), cursor="hand2").pack(side=tk.RIGHT, padx=5)
        # 保存
        tk.Button(self.btn_frame, text="✅ 保存并启动", command=self.save_and_close,
                  bg='#00aa00', fg='#000000', padx=25, pady=8, borderwidth=0,
                  font=("Arial", 10, "bold"), cursor="hand2").pack(side=tk.RIGHT, padx=5)

    # ---------- 测试 & 验证 ----------
    def _get_field_value(self, key):
        info = self.entries.get(key)
        if not info:
            return ""
        val = info['entry'].get().strip()
        if val == info.get('placeholder', None):
            return ""
        return val

    def _resolve_request_config(self):
        """根据当前选择解析出调用 API 所需的 url / key / model。"""
        pid = self.selected_provider
        defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])

        base_url = self._get_field_value("base_url") or defaults["base_url"]
        model = self._get_field_value("model_name") or defaults["model_name"]
        api_key = self._get_field_value("api_key")

        base_url = base_url.rstrip("/") if base_url else ""
        url = f"{base_url}/chat/completions" if base_url else ""

        return url, api_key, model

    def test_api_keys(self):
        self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, "🔍 正在验证 API 配置...\n")
        self.root.update()
        threading.Thread(target=self._test_keys_background, daemon=True).start()

    def _test_keys_background(self):
        pid = self.selected_provider
        defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])
        display_name = defaults["display_name"]

        url, api_key, model = self._resolve_request_config()

        self.status_text.insert(tk.END, f"\n📍 服务商: {display_name}")
        self.status_text.insert(tk.END, f"\n📍 地址: {url or '(空)'}")
        self.status_text.insert(tk.END, f"\n📍 模型: {model or '(空)'}")
        self.status_text.insert(tk.END, f"\n📍 密钥: {'已填写' if api_key and 'YOUR_' not in api_key else '未填写'}")
        self.root.update()

        if not api_key or "YOUR_" in api_key:
            self.status_text.insert(tk.END, "\n⚠️ API Key 未填写或为占位符。\n")
            self.root.update()
            return

        if not url:
            self.status_text.insert(tk.END, "\n❌ API 基础地址为空（自定义模式必填）\n")
            self.root.update()
            return

        if not model:
            self.status_text.insert(tk.END, "\n⚠️ 模型名称为空，可能会导致请求失败。\n")
            self.root.update()

        self.status_text.insert(tk.END, f"\n\n🧪 发送测试请求到 {url} ...")
        self.root.update()

        result = self._validate_any_provider(url, api_key, model)
        if result['valid']:
            self.status_text.insert(tk.END, " ✅\n🎉 验证成功！配置可以正常使用。\n")
            self.validation_results['api_key'] = True
        else:
            self.status_text.insert(tk.END, f" ❌\n错误: {result.get('error', '未知错误')}\n")
            self.validation_results['api_key'] = False
        self.root.update()

    def _validate_any_provider(self, url, api_key, model) -> dict:
        """通用 OpenAI 格式 API 验证。"""
        try:
            response = requests.post(
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
            if response.status_code == 200:
                data = response.json()
                if "choices" in data:
                    return {'valid': True}
                return {'valid': False, 'error': f"响应格式异常: {str(data)[:100]}"}
            elif response.status_code == 401:
                return {'valid': False, 'error': '认证失败 (401)：API Key 无效或已过期'}
            elif response.status_code == 403:
                return {'valid': False, 'error': '权限不足 (403)：请检查账号权限'}
            elif response.status_code == 404:
                return {'valid': False, 'error': f'地址不存在 (404)：请检查 {url}'}
            elif response.status_code == 429:
                return {'valid': False, 'error': '请求过于频繁 (429)：请稍后重试'}
            else:
                try:
                    msg = response.json()
                except Exception:
                    msg = response.text
                return {'valid': False, 'error': f'HTTP {response.status_code}: {str(msg)[:150]}'}
        except requests.exceptions.Timeout:
            return {'valid': False, 'error': '连接超时，请检查网络或地址是否正确'}
        except requests.exceptions.ConnectionError:
            return {'valid': False, 'error': '网络连接失败，请检查地址、端口或网络'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    # ---------- 保存 ----------
    def save_and_close(self):
        pid = self.selected_provider
        defaults = PROVIDER_DEFAULTS.get(pid, PROVIDER_DEFAULTS["deepseek"])
        key_env = defaults["key_env"]
        display_name = defaults["display_name"]

        # 必填校验
        required_fields = ['api_key']
        if pid == "custom":
            required_fields += ['base_url', 'model_name']

        for f in required_fields:
            v = self._get_field_value(f)
            if not v or "YOUR_" in v:
                label_map = {
                    'api_key': f'{display_name} API Key',
                    'base_url': 'API 基础地址',
                    'model_name': '模型名称',
                }
                messagebox.showerror("缺少必填项",
                                     f"请填写：{label_map.get(f, f)}")
                return

        api_key = self._get_field_value("api_key")
        base_url = self._get_field_value("base_url")
        model_name = self._get_field_value("model_name")
        provider_label = self._get_field_value("CUSTOM_PROVIDER_NAME") if pid == "custom" else ""

        try:
            # 写入 provider
            set_key(self.env_path, "AI_PROVIDER", pid)

            # 写入 base_url / model_name（空值也写入以覆盖旧值）
            set_key(self.env_path, "API_BASE_URL", base_url)
            set_key(self.env_path, "MODEL_NAME", model_name)

            # 写入自定义提供商名称（仅 custom 时有效，对应 api.provider_label）
            set_key(self.env_path, "CUSTOM_PROVIDER_NAME", provider_label)

            # 写入对应 key，同时清理其他提供商的 key（避免混淆）
            all_key_envs = [paths[1] for paths in PROVIDER_KEY_PATHS.values()]
            for ke in all_key_envs:
                if ke == key_env:
                    set_key(self.env_path, ke, api_key)
                elif os.getenv(ke):
                    # 保留旧值但注释掉（更安全）
                    # 这里简单地不改动其他 key
                    pass

            # 百度 & Picovoice 可选
            optional_keys = ["BAIDU_APP_ID", "BAIDU_API_KEY", "BAIDU_SECRET_KEY", "PICOVOICE_ACCESS_KEY"]
            for ke in optional_keys:
                v = self._get_field_value(ke)
                if v and "YOUR_" not in v:
                    set_key(self.env_path, ke, v)

            logger.info(f"配置已保存：AI_PROVIDER={pid}, {key_env}=***")
            self.setup_complete = True
            messagebox.showinfo("成功",
                                f"✅ 配置已保存到 .env 文件！\n\n"
                                f"提供商: {display_name}\n"
                                f"密钥已保存至: {key_env}\n\n"
                                f"Butler 将在 3 秒后启动...")
            self.root.after(3000, self._close_wizard)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存配置：{str(e)}")
            logger.error(f"Failed to save config: {e}")

    # ---------- 跳过 / 关闭 ----------
    def skip_setup(self):
        if messagebox.askyesno("确认", "确定要跳过配置吗？某些功能将无法使用。"):
            self.setup_complete = True
            self._close_wizard()

    def _close_wizard(self):
        if self.own_root:
            self.root.quit()
        else:
            self.root.destroy()


def show_config_wizard_if_needed():
    """当缺少必需配置时弹出向导。"""
    from butler.core.config_manager import config_manager
    is_valid, missing = config_manager.validate_required_keys()
    if is_valid:
        return False
    logger.info(f"检测到缺失配置: {missing}，弹出配置向导")
    wizard = EnhancedConfigWizard()
    wizard.root.mainloop()
    return True


if __name__ == "__main__":
    w = EnhancedConfigWizard()
    w.root.mainloop()
