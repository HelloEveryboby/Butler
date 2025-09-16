import tkinter as tk
from tkinter import scrolledtext, filedialog
import sys
import os
import json
import re
from package.log_manager import LogManager

# Pygments 用于语法高亮
try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.styles import get_style_by_name
    from pygments.token import Token
    PYGMENTS_INSTALLED = True
except ImportError:
    PYGMENTS_INSTALLED = False

logger = LogManager.get_logger(__name__)

class CommandPanel(tk.Frame):
    def __init__(self, master, program_mapping=None, programs=None, command_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.command_callback = command_callback
        self.program_mapping = program_mapping or {}
        self.programs = programs or {}
        self.all_program_names = sorted(list(self.programs.keys()))

        # --- 主题和样式 ---
        self.background_color = '#282c34'
        self.foreground_color = '#abb2bf'
        self.input_bg_color = '#21252b'
        self.button_bg_color = '#3e4451'
        self.button_fg_color = self.foreground_color
        self.code_bg_color = '#21252b'
        self.menu_bg_color = '#21252b'
        self.menu_fg_color = self.foreground_color

        self.font_configs = {
            "small": {
                "menu_label": ("Arial", 10, "bold"),
                "program_listbox": ("Arial", 8),
                "output_text": ("Consolas", 9),
                "input_entry": ("Consolas", 9),
                "buttons": ("Arial", 7),
                "user_prompt": ("Consolas", 9, "bold"),
                "system_message": ("Consolas", 9, "italic"),
            },
            "medium": {
                "menu_label": ("Arial", 12, "bold"),
                "program_listbox": ("Arial", 10),
                "output_text": ("Consolas", 11),
                "input_entry": ("Consolas", 11),
                "buttons": ("Arial", 9),
                "user_prompt": ("Consolas", 11, "bold"),
                "system_message": ("Consolas", 11, "italic"),
            },
            "large": {
                "menu_label": ("Arial", 14, "bold"),
                "program_listbox": ("Arial", 12),
                "output_text": ("Consolas", 13),
                "input_entry": ("Consolas", 13),
                "buttons": ("Arial", 11),
                "user_prompt": ("Consolas", 13, "bold"),
                "system_message": ("Consolas", 13, "italic"),
            }
        }

        self.config(bg=self.background_color)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- 用于可折叠菜单的主 PanedWindow ---
        self.main_paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg=self.background_color, sashwidth=4)
        self.main_paned_window.grid(row=0, column=0, sticky="nsew")

        # --- 左侧窗格: 菜单 ---
        self.menu_frame = tk.Frame(self.main_paned_window, bg=self.menu_bg_color, width=200)
        self.menu_frame.grid_rowconfigure(2, weight=1)  # 使列表框可扩展
        self.menu_frame.grid_columnconfigure(0, weight=1)
        self.main_paned_window.add(self.menu_frame, stretch="never", minsize=200)

        self.menu_label = tk.Label(self.menu_frame, text="Programs", font=("Arial", 12, "bold"), bg=self.menu_bg_color, fg=self.menu_fg_color)
        self.menu_label.grid(row=0, column=0, pady=5, padx=5, sticky="ew")

        self.search_entry = tk.Entry(self.menu_frame, bg=self.input_bg_color, fg=self.foreground_color, insertbackground=self.foreground_color, borderwidth=0, highlightthickness=1)
        self.search_entry.grid(row=1, column=0, pady=(0, 5), padx=5, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.filter_programs)

        self.program_listbox = tk.Listbox(
            self.menu_frame,
            bg=self.menu_bg_color,
            fg=self.menu_fg_color,
            selectbackground="#4f5b70",
            selectforeground=self.menu_fg_color,
            highlightthickness=0,
            borderwidth=0,
            font=("Arial", 10)
        )
        self.program_listbox.grid(row=2, column=0, sticky="nsew", padx=(5, 0), pady=(0, 5))
        self.program_listbox.bind("<<ListboxSelect>>", self.on_program_select)

        scrollbar = tk.Scrollbar(self.menu_frame, orient="vertical", command=self.program_listbox.yview)
        scrollbar.grid(row=2, column=1, sticky="ns", pady=(0, 5))
        self.program_listbox.config(yscrollcommand=scrollbar.set)

        for prog_name in self.all_program_names:
            self.program_listbox.insert(tk.END, prog_name)

        # --- 设置按钮 ---
        self.settings_icon = tk.PhotoImage(file="assets/settings_icon.png")
        self.settings_button = tk.Button(
            self.menu_frame,
            text="Settings",
            image=self.settings_icon,
            compound=tk.LEFT,
            command=self.open_settings_window,
            bg=self.button_bg_color,
            fg=self.button_fg_color,
            activebackground="#4f5b70",
            activeforeground=self.foreground_color,
            borderwidth=0,
            highlightthickness=0,
            font=("Arial", 9)
        )
        self.settings_button.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)


        # --- 右侧窗格: 主内容 ---
        self.main_content_frame = tk.Frame(self.main_paned_window, bg=self.background_color)
        self.main_content_frame.grid_rowconfigure(1, weight=1) # 调整行以适应 output_text
        self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.main_paned_window.add(self.main_content_frame, stretch="always")

        # --- 显示模式框架 ---
        self.display_mode_frame = tk.Frame(self.main_content_frame, bg=self.background_color)
        self.display_mode_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))

        tk.Label(self.display_mode_frame, text="Display Mode:", bg=self.background_color, fg=self.foreground_color).pack(side=tk.LEFT, padx=(0, 5))

        self.display_mode_var = tk.StringVar(value='host')
        self.font_size_var = tk.StringVar(value='medium')
        radio_button_config = {
            "bg": self.background_color,
            "fg": self.foreground_color,
            "selectcolor": self.input_bg_color,
            "activebackground": self.background_color,
            "activeforeground": self.foreground_color,
            "highlightthickness": 0,
            "variable": self.display_mode_var,
            "command": self.on_display_mode_change
        }

        tk.Radiobutton(self.display_mode_frame, text="Host", value='host', **radio_button_config).pack(side=tk.LEFT)
        tk.Radiobutton(self.display_mode_frame, text="USB", value='usb', **radio_button_config).pack(side=tk.LEFT)
        tk.Radiobutton(self.display_mode_frame, text="Both", value='both', **radio_button_config).pack(side=tk.LEFT)


        # --- 主输出文本区域 ---
        self.output_text = scrolledtext.ScrolledText(
            self.main_content_frame, # 父容器现在是 main_content_frame
            bg=self.background_color,
            fg=self.foreground_color,
            state='disabled',
            wrap=tk.WORD,
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0,
            selectbackground="#4f5b70"
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # --- 输入框架 (底部) ---
        self.input_frame = tk.Frame(self.main_content_frame, bg=self.background_color) # 父容器现在是 main_content_frame
        self.input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = tk.Entry(
            self.input_frame,
            bg=self.input_bg_color,
            fg=self.foreground_color,
            insertbackground=self.foreground_color,
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        self.input_entry.bind("<Return>", self.send_text_command)

        # --- 按钮 ---
        button_config = {
            "bg": self.button_bg_color,
            "fg": self.button_fg_color,
            "activebackground": "#4f5b70",
            "activeforeground": self.foreground_color,
            "borderwidth": 0,
            "highlightthickness": 0,
            "font": ("Arial", 9)
        }
        self.send_button = tk.Button(self.input_frame, text="Send", command=self.send_text_command, **button_config)
        self.send_button.grid(row=0, column=1, padx=(5, 0))
        self.listen_button = tk.Button(self.input_frame, text="Listen", command=self.send_listen_command, **button_config)
        self.listen_button.grid(row=0, column=2, padx=(5, 0))
        self.clear_button = tk.Button(self.input_frame, text="Clear", command=self.clear_history, **button_config)
        self.clear_button.grid(row=0, column=3, padx=(5, 0))
        self.restart_button = tk.Button(self.input_frame, text="Restart", command=self.restart_application, **button_config)
        self.restart_button.grid(row=0, column=4, padx=(5, 0))
        self.markdown_button = tk.Button(self.input_frame, text="Markdown", command=self.open_markdown_converter, **button_config)
        self.markdown_button.grid(row=0, column=5, padx=(5, 0))

        self._configure_styles_and_tags()
        self.update_font_size('medium')

    def on_program_select(self, event=None):
        """处理列表框中的程序选择。"""
        # 获取选中的索引
        selected_indices = self.program_listbox.curselection()
        if not selected_indices:
            return

        # 从索引获取程序名称
        selected_index = selected_indices[0]
        program_name = self.program_listbox.get(selected_index)

        if program_name and self.command_callback:
            logger.info(f"从菜单执行程序: {program_name}")
            self.append_to_history(f"正在执行: {program_name}", "system_message")
            self.command_callback("execute_program", program_name)

    def filter_programs(self, event=None):
        """根据搜索输入框过滤程序列表框。"""
        search_term = self.search_entry.get().lower()

        # 清空列表框
        self.program_listbox.delete(0, tk.END)

        # 重新填充匹配的项目
        for name in self.all_program_names:
            if search_term in name.lower():
                self.program_listbox.insert(tk.END, name)

    def _configure_styles_and_tags(self):
        """配置用于样式化输出的文本标签。"""
        self.output_text.tag_config('user_prompt', foreground='#61afef', font=("Consolas", 11, "bold"))
        self.output_text.tag_config('ai_response', foreground=self.foreground_color)
        self.output_text.tag_config('system_message', foreground='#e5c07b', font=("Consolas", 11, "italic"))
        self.output_text.tag_config('error', foreground='#e06c75')

        # 配置 Pygments 语法高亮标签
        if PYGMENTS_INSTALLED:
            style = get_style_by_name('monokai')
            for token, t_style in style:
                tag_name = str(token)
                foreground = t_style['color']
                if foreground:
                    self.output_text.tag_config(tag_name, foreground=f"#{foreground}")

    def _highlight_code(self, code, language=''):
        """对代码块应用语法高亮。"""
        if not PYGMENTS_INSTALLED:
            self.output_text.insert(tk.END, code)
            return

        try:
            if language:
                lexer = get_lexer_by_name(language, stripall=True)
            else:
                lexer = guess_lexer(code, stripall=True)
        except Exception:
            lexer = get_lexer_by_name('text', stripall=True)

        # 带有背景插入代码块
        start_index = self.output_text.index(tk.END)
        self.output_text.insert(tk.END, code)
        end_index = self.output_text.index(tk.END)
        self.output_text.tag_add("code_block", start_index, end_index)
        self.output_text.tag_config("code_block", background=self.code_bg_color, borderwidth=1, relief=tk.SOLID, lmargin1=10, lmargin2=10, rmargin=10)

        # 应用基于 token 的高亮
        for token, content in lex(code, lexer):
            tag_name = str(token)
            # 查找内容相对于整个代码块开始的位置
            # 这对于 Text 小部件来说有点棘手，所以我们进行搜索
            start = self.output_text.search(content, start_index, stopindex=end_index)
            if start:
                end = f"{start}+{len(content)}c"
                self.output_text.tag_add(tag_name, start, end)
                start_index = end # 将搜索起点移动到找到的 token 之后


    def append_to_history(self, text, tag='ai_response'):
        self.output_text.config(state='normal')

        code_block_pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

        last_end = 0
        for match in code_block_pattern.finditer(text):
            # 在代码块之前插入文本
            pre_text = text[last_end:match.start()]
            if pre_text.strip():
                self.output_text.insert(tk.END, pre_text, (tag,))

            # 插入高亮的代码块
            language = match.group(1).lower()
            code = match.group(2)
            self._highlight_code(code, language)

            last_end = match.end()

        # 在最后一个代码块之后插入任何剩余的文本
        remaining_text = text[last_end:]
        if remaining_text.strip():
            self.output_text.insert(tk.END, remaining_text, (tag,))

        self.output_text.insert(tk.END, "\n\n")
        self.output_text.see(tk.END)
        self.output_text.config(state='disabled')


    def on_display_mode_change(self):
        mode = self.display_mode_var.get()
        if self.command_callback:
            logger.info(f"显示模式已更改为: {mode}")
            # 我们可以使用一个特殊的 command_type 重用 command_callback
            self.command_callback("display_mode_change", mode)

    def set_command_callback(self, callback):
        self.command_callback = callback

    def send_text_command(self, event=None):
        command = self.input_entry.get().strip()
        if command and self.command_callback:
            self.append_to_history(f"You: {command}", "user_prompt")
            logger.info(f"发送文本命令: {command}")
            self.command_callback("text", command)
            self.input_entry.delete(0, tk.END)

    def send_listen_command(self):
        if self.command_callback:
            logger.info("正在启动语音命令")
            self.command_callback("voice", None)

    def set_input_text(self, text):
        self.input_entry.delete(0, tk.END)
        self.input_entry.insert(0, text)

    def clear_history(self):
        logger.info("正在清除历史记录")
        self.output_text.config(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state='disabled')

    def open_settings_window(self):
        settings_win = tk.Toplevel(self.master)
        settings_win.title("Settings")
        settings_win.config(bg=self.background_color)
        settings_win.transient(self.master)
        settings_win.grab_set()

        font_size_frame = tk.Frame(settings_win, bg=self.background_color)
        font_size_frame.pack(pady=10, padx=10)

        tk.Label(font_size_frame, text="Font Size:", bg=self.background_color, fg=self.foreground_color).pack(side=tk.LEFT, padx=(0, 5))

        font_radio_config = {
            "bg": self.background_color,
            "fg": self.foreground_color,
            "selectcolor": self.input_bg_color,
            "activebackground": self.background_color,
            "activeforeground": self.foreground_color,
            "highlightthickness": 0,
            "variable": self.font_size_var,
            "command": lambda: self.update_font_size(self.font_size_var.get())
        }

        tk.Radiobutton(font_size_frame, text="Small", value='small', **font_radio_config).pack(side=tk.LEFT)
        tk.Radiobutton(font_size_frame, text="Medium", value='medium', **font_radio_config).pack(side=tk.LEFT)
        tk.Radiobutton(font_size_frame, text="Large", value='large', **font_radio_config).pack(side=tk.LEFT)

    def update_font_size(self, size_mode):
        logger.info(f"正在将字体大小更新为 {size_mode}")
        fonts = self.font_configs[size_mode]

        # 更新小部件
        self.menu_label.config(font=fonts["menu_label"])
        self.program_listbox.config(font=fonts["program_listbox"])
        self.output_text.config(font=fonts["output_text"])
        self.input_entry.config(font=fonts["input_entry"])

        # 更新按钮
        button_font = fonts["buttons"]
        self.send_button.config(font=button_font)
        self.listen_button.config(font=button_font)
        self.clear_button.config(font=button_font)
        self.restart_button.config(font=button_font)
        self.markdown_button.config(font=button_font)
        self.settings_button.config(font=button_font)

        # 更新文本标签
        self.output_text.tag_config('user_prompt', font=fonts["user_prompt"])
        self.output_text.tag_config('system_message', font=fonts["system_message"])

    def open_markdown_converter(self):
        """打开文件对话框以选择要转换为 markdown 的文件。"""
        filepath = filedialog.askopenfilename(
            title="Select a file to convert to Markdown",
            filetypes=(
                ("All supported files", "*.txt *.csv *.html *.htm *.docx *.pptx *.pdf *.xlsx *.png *.jpg *.jpeg *.gif *.bmp *.zip *.epub"),
                ("Text files", "*.txt"),
                ("Documents", "*.docx *.pdf *.pptx *.epub"),
                ("Web files", "*.html *.htm"),
                ("Data files", "*.csv *.xlsx *.json"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Archives", "*.zip"),
                ("All files", "*.*")
            )
        )
        if filepath:
            # 构造命令并发送
            command = f'markdown "{filepath}"'
            self.append_to_history(f"You: {command}", "user_prompt")
            logger.info(f"发送 markdown 转换命令: {filepath}")
            if self.command_callback:
                self.command_callback("text", command)

    def restart_application(self):
        logger.info("正在重新启动应用程序")
        python = sys.executable
        os.execl(python, python, *sys.argv)
