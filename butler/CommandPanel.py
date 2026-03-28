import tkinter as tk
from tkinter import scrolledtext
import sys
import os
import re
from package.core_utils.log_manager import LogManager
from butler.core.asset_loader import asset_loader
from butler.core.event_bus import event_bus
from queue import Queue

# 用于语法高亮显示的 Pygments
try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.styles import get_style_by_name
    from pygments.token import Token
    PYGMENTS_INSTALLED = True
except ImportError:
    PYGMENTS_INSTALLED = False

logger = LogManager.get_logger(__name__)

# tmd要是中考分不那么低一中就去了，也就能早读了

class CommandPanel(tk.Frame):
    def __init__(self, master, program_mapping=None, programs=None, command_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.command_callback = command_callback
        self.msg_queue = Queue()

        # Subscribe to events
        event_bus.subscribe("ui_output", self._queue_ui_output)
        event_bus.subscribe("voice_status", self._queue_voice_status)
        event_bus.subscribe("link_status", self._queue_link_status)
        event_bus.subscribe("screenshot_update", self._queue_screenshot_update)
        event_bus.subscribe("archive_browser_update", self._queue_archive_browser_update)
        event_bus.subscribe("nostalgia_mode_activated", self._activate_nostalgia_ui)

        # Start queue processing
        self.master.after(100, self.process_queue)
        self.program_mapping = program_mapping or {}
        self.programs = programs or {}
        self.all_program_names = sorted(list(self.programs.keys()))

        # --- 主题和样式 (Admin/Power User Style) ---
        self.background_color = '#1c1c1c' # Deeper black
        self.foreground_color = '#00ff00' # Terminal green
        self.input_bg_color = '#000000'
        self.button_bg_color = '#333333'
        self.button_fg_color = '#ffffff'
        self.code_bg_color = '#000000'
        self.menu_bg_color = '#121212'
        self.menu_fg_color = '#00ff00'

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

        # --- 用于可折叠菜单的主分窗格 ---
        self.main_paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg=self.background_color, sashwidth=4)
        self.main_paned_window.grid(row=0, column=0, sticky="nsew")

        # --- 左侧面板：菜单 ---
        self.menu_frame = tk.Frame(self.main_paned_window, bg=self.menu_bg_color, width=200)
        self.menu_frame.grid_rowconfigure(2, weight=1)  # 使列表框可扩展
        self.menu_frame.grid_columnconfigure(0, weight=1)
        self.main_paned_window.add(self.menu_frame, stretch="never", minsize=200)

        self.menu_label = tk.Label(self.menu_frame, text="程序列表", font=("Arial", 12, "bold"), bg=self.menu_bg_color, fg=self.menu_fg_color)
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

        # --- Archive Explorer (FileBrowser) ---
        from tkinter import ttk
        self.archive_label = tk.Label(self.menu_frame, text="压缩包浏览器", font=("Arial", 10, "bold"), bg=self.menu_bg_color, fg=self.menu_fg_color)
        self.archive_label.grid(row=3, column=0, pady=(10, 5), padx=5, sticky="ew")

        self.archive_tree = ttk.Treeview(self.menu_frame, selectmode='browse', show='tree')
        self.archive_tree.grid(row=4, column=0, sticky="nsew", padx=(5, 0), pady=(0, 5))
        self.archive_tree.bind("<Double-1>", self.on_archive_item_double_click)

        # Style the Treeview to match the dark theme
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Treeview", background=self.menu_bg_color, foreground=self.menu_fg_color, fieldbackground=self.menu_bg_color, borderwidth=0)
        style.map("Treeview", background=[('selected', '#4f5b70')], foreground=[('selected', self.menu_fg_color)])

        # --- 手动控制工具栏 ---
        self.manual_toolbar = tk.Frame(self.menu_frame, bg=self.menu_bg_color)
        self.manual_toolbar.grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.manual_toolbar.grid_columnconfigure((0, 1, 2), weight=1)

        btn_style = {
            "bg": self.button_bg_color,
            "fg": self.button_fg_color,
            "font": ("Arial", 8),
            "borderwidth": 0,
            "highlightthickness": 0
        }

        self.btn_screenshot = tk.Button(self.manual_toolbar, text="📸", command=lambda: self.manual_action("screenshot"), **btn_style)
        self.btn_screenshot.grid(row=0, column=0, padx=1, sticky="ew")

        self.btn_click = tk.Button(self.manual_toolbar, text="🖱️", command=lambda: self.manual_action("left_click"), **btn_style)
        self.btn_click.grid(row=0, column=1, padx=1, sticky="ew")

        self.btn_type = tk.Button(self.manual_toolbar, text="⌨️", command=lambda: self.manual_action("type"), **btn_style)
        self.btn_type.grid(row=0, column=2, padx=1, sticky="ew")

        # --- 设置按钮 ---
        settings_icon_path = asset_loader.resolve_path("asset://settings_icon.png")
        self.settings_icon = tk.PhotoImage(file=settings_icon_path)
        self.settings_button = tk.Button(
            self.menu_frame,
            text="设置",
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
        self.settings_button.grid(row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=5)


        # --- 右侧面板：内容与远程视图 ---
        self.content_paned_window = tk.PanedWindow(self.main_paned_window, orient=tk.VERTICAL, sashrelief=tk.RAISED, bg=self.background_color, sashwidth=4)
        self.main_paned_window.add(self.content_paned_window, stretch="always")

        # --- 上部内容：输出与输入 ---
        self.main_content_frame = tk.Frame(self.content_paned_window, bg=self.background_color)
        self.main_content_frame.grid_rowconfigure(1, weight=1)
        self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.content_paned_window.add(self.main_content_frame, stretch="always")

        # --- 显示模式框架 ---
        self.display_mode_frame = tk.Frame(self.main_content_frame, bg=self.background_color)
        self.display_mode_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))

        tk.Label(self.display_mode_frame, text="显示模式:", bg=self.background_color, fg=self.foreground_color).pack(side=tk.LEFT, padx=(0, 5))

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

        tk.Radiobutton(self.display_mode_frame, text="主机", value='host', **radio_button_config).pack(side=tk.LEFT)
        tk.Radiobutton(self.display_mode_frame, text="USB", value='usb', **radio_button_config).pack(side=tk.LEFT)
        tk.Radiobutton(self.display_mode_frame, text="双显", value='both', **radio_button_config).pack(side=tk.LEFT)

        # --- 连接状态指示器 ---
        self.link_status_frame = tk.Frame(self.display_mode_frame, bg=self.background_color)
        self.link_status_frame.pack(side=tk.RIGHT, padx=10)

        self.link_label = tk.Label(self.link_status_frame, text="数据链:", bg=self.background_color, fg=self.foreground_color, font=("Arial", 9))
        self.link_label.pack(side=tk.LEFT)

        self.link_indicator = tk.Label(self.link_status_frame, text="●", fg="gray", bg=self.background_color, font=("Arial", 12))
        self.link_indicator.pack(side=tk.LEFT, padx=2)

        self.link_text = tk.Label(self.link_status_frame, text="未连接", bg=self.background_color, fg=self.foreground_color, font=("Arial", 9))
        self.link_text.pack(side=tk.LEFT)

        # --- 主输出文本区域 ---
        self.output_text = scrolledtext.ScrolledText(
            self.main_content_frame, # 父级现在是 main_content_frame
            bg=self.background_color,
            fg=self.foreground_color,
            state='normal',
            wrap=tk.WORD,
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0,
            selectbackground="#4f5b70"
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # --- 输入框架（底部） ---
        self.input_frame = tk.Frame(self.main_content_frame, bg=self.background_color) # 父级现在是 main_content_frame
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

        # --- Buttons ---
        button_config = {
            "bg": self.button_bg_color,
            "fg": self.button_fg_color,
            "activebackground": "#4f5b70",
            "activeforeground": self.foreground_color,
            "borderwidth": 0,
            "highlightthickness": 0,
            "font": ("Arial", 9)
        }
        self.send_button = tk.Button(self.input_frame, text="发送", command=self.send_text_command, **button_config)
        self.send_button.grid(row=0, column=1, padx=(5, 0))
        self.listen_button = tk.Button(self.input_frame, text="聆听", command=self.send_listen_command, **button_config)
        self.listen_button.grid(row=0, column=2, padx=(5, 0))
        self.clear_button = tk.Button(self.input_frame, text="清空", command=self.clear_history, **button_config)
        self.clear_button.grid(row=0, column=3, padx=(5, 0))
        self.restart_button = tk.Button(self.input_frame, text="重启", command=self.restart_application, **button_config)
        self.restart_button.grid(row=0, column=4, padx=(5, 0))

        # --- 下部内容：远程视图（可折叠） ---
        self.remote_view_frame = tk.Frame(self.content_paned_window, bg=self.input_bg_color)
        self.remote_view_frame.grid_rowconfigure(0, weight=1)
        self.remote_view_frame.grid_columnconfigure(0, weight=1)
        self.content_paned_window.add(self.remote_view_frame, stretch="never", minsize=0)

        self.screenshot_canvas = tk.Canvas(self.remote_view_frame, bg="black", highlightthickness=0)
        self.screenshot_canvas.grid(row=0, column=0, sticky="nsew")
        self.screenshot_canvas.bind("<Button-1>", self.on_canvas_click)

        self.last_screenshot_image = None
        self.canvas_image_id = None

        self._configure_styles_and_tags()
        self.update_font_size('medium')

        # Auto-scaling support
        self.bind("<Configure>", self.on_resize)
        self.last_scale_factor = 1.0

    def on_resize(self, event):
        """Handle window resize and auto-scale fonts."""
        # Only scale if it's the main frame resize
        if event.widget != self:
            return

        # Reference size 1000x700
        new_scale_factor = min(event.width / 1000, event.height / 700)

        # Only update if change is more than 5% to avoid constant redraws
        if abs(new_scale_factor - self.last_scale_factor) > 0.05:
            self.last_scale_factor = new_scale_factor
            self.auto_scale_fonts(new_scale_factor)

    def auto_scale_fonts(self, scale):
        """Dynamically scale fonts based on window size."""
        # Base sizes for 'medium'
        base_fonts = {
            "menu_label": 12,
            "program_listbox": 10,
            "output_text": 11,
            "input_entry": 11,
            "buttons": 9,
            "user_prompt": 11,
            "system_message": 11
        }

        scaled_fonts = {}
        for key, size in base_fonts.items():
            new_size = max(int(size * scale), 7)
            if key == "menu_label":
                scaled_fonts[key] = ("Arial", new_size, "bold")
            elif key == "user_prompt":
                scaled_fonts[key] = ("Consolas", new_size, "bold")
            elif key == "system_message":
                scaled_fonts[key] = ("Consolas", new_size, "italic")
            elif key in ["output_text", "input_entry"]:
                scaled_fonts[key] = ("Consolas", new_size)
            else:
                scaled_fonts[key] = ("Arial", new_size)

        # Apply scaled fonts
        self.menu_label.config(font=scaled_fonts["menu_label"])
        self.program_listbox.config(font=scaled_fonts["program_listbox"])
        self.output_text.config(font=scaled_fonts["output_text"])
        self.input_entry.config(font=scaled_fonts["input_entry"])

        self.send_button.config(font=scaled_fonts["buttons"])
        self.listen_button.config(font=scaled_fonts["buttons"])
        self.clear_button.config(font=scaled_fonts["buttons"])
        self.restart_button.config(font=scaled_fonts["buttons"])
        self.settings_button.config(font=scaled_fonts["buttons"])

        # Update manual toolbar buttons
        manual_btn_font = ("Arial", max(int(8 * scale), 6))
        self.btn_screenshot.config(font=manual_btn_font)
        self.btn_click.config(font=manual_btn_font)
        self.btn_type.config(font=manual_btn_font)

        self.output_text.tag_config('user_prompt', font=scaled_fonts["user_prompt"])
        self.output_text.tag_config('system_message', font=scaled_fonts["system_message"])

    def on_program_select(self, event=None):
        """处理列表框中的程序选择。"""
        # 获取选中的索引
        selected_indices = self.program_listbox.curselection()
        if not selected_indices:
            return

        # 从索引中获取程序名称
        selected_index = selected_indices[0]
        program_name = self.program_listbox.get(selected_index)

        if program_name and self.command_callback:
            logger.info(f"Executing program from menu: {program_name}")
            self.append_to_history(f"正在执行: {program_name}", "system_message")
            self.command_callback("execute_program", program_name)

    def filter_programs(self, event=None):
        """基于搜索输入过滤程序列表框。"""
        search_term = self.search_entry.get().lower()

        # 清空列表框
        self.program_listbox.delete(0, tk.END)

        # 重新填充匹配的项目
        for name in self.all_program_names:
            if search_term in name.lower():
                self.program_listbox.insert(tk.END, name)

    def _configure_styles_and_tags(self):
        """配置用于设置输出样式的文本标签。"""
        self.output_text.tag_config('user_prompt', foreground='#ff00ff', font=("Consolas", 11, "bold"), background='#2d2d2d')
        self.output_text.tag_config('ai_response', foreground=self.foreground_color, background='#121212')
        self.output_text.tag_config('system_message', foreground='#00ffff', font=("Consolas", 11, "italic"))
        self.output_text.tag_config('error', foreground='#ff0000', font=("Consolas", 11, "bold"))

        # Configure Pygments syntax highlighting tags
        if PYGMENTS_INSTALLED:
            style = get_style_by_name('monokai')
            for token, t_style in style:
                tag_name = str(token)
                foreground = t_style['color']
                if foreground:
                    self.output_text.tag_config(tag_name, foreground=f"#{foreground}")

    def _highlight_code(self, code, language=''):
        """为代码块应用语法高亮。"""
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

        # Insert the code block with a background
        start_index = self.output_text.index(tk.END)
        self.output_text.insert(tk.END, code)
        end_index = self.output_text.index(tk.END)
        self.output_text.tag_add("code_block", start_index, end_index)
        self.output_text.tag_config("code_block", background=self.code_bg_color, borderwidth=1, relief=tk.SOLID, lmargin1=10, lmargin2=10, rmargin=10)

        # Apply token-based highlighting
        for token, content in lex(code, lexer):
            tag_name = str(token)
            # Find where the content starts relative to the beginning of the whole code block
            # This is a bit tricky with the Text widget, so we search
            start = self.output_text.search(content, start_index, stopindex=end_index)
            if start:
                end = f"{start}+{len(content)}c"
                self.output_text.tag_add(tag_name, start, end)
                start_index = end # Move search start to after the found token


    def append_to_history(self, text, tag='ai_response', response_id=None):
        self.output_text.config(state='normal')

        # In this enhanced version, we'll try to keep the text widget editable
        # so the user can modify code blocks.

        # If it's a streaming response, just insert the initial text.
        if response_id:
            block_tag = f"block_{response_id}"
            self.output_text.insert(tk.END, text, (tag, block_tag))
        else:
            # For non-streaming messages, parse for code blocks as before.
            code_block_pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
            last_end = 0
            for match in code_block_pattern.finditer(text):
                pre_text = text[last_end:match.start()]
                if pre_text.strip():
                    self.output_text.insert(tk.END, pre_text, (tag,))

                language = match.group(1).lower()
                code = match.group(2)
                self._highlight_code(code, language)
                last_end = match.end()

            remaining_text = text[last_end:]
            if remaining_text.strip():
                self.output_text.insert(tk.END, remaining_text, (tag,))

            # Add the final newlines for non-streaming messages
            self.output_text.insert(tk.END, "\n\n")

        self.output_text.see(tk.END)
        # self.output_text.config(state='disabled') # Keep it enabled for manual editing

    def append_to_response(self, text_chunk, response_id):
        """Appends a chunk of text to a response block identified by response_id."""
        if not response_id:
            return

        self.output_text.config(state='normal')

        # Insert the chunk at the end of the text widget.
        self.output_text.insert(tk.END, text_chunk)

        # If we just inserted code block or wait for approval, keep it editable
        if "/approve" in text_chunk or "```python" in self.output_text.get("1.0", tk.END):
            # We want to allow editing the code block.
            # For simplicity, let's keep it 'normal' if it looks like we are in approval mode.
            pass
        else:
            # self.output_text.config(state='disabled')
            pass

        self.output_text.see(tk.END)
        # Note: We are keeping state 'normal' more often now to allow "C. Manual Editing"
        # but we should be careful.

    def update_screenshot(self, b64_data):
        """使用新的截图更新远程视图。"""
        import base64
        from io import BytesIO
        from PIL import Image, ImageTk

        try:
            img_data = base64.b64decode(b64_data)
            img = Image.open(BytesIO(img_data))

            # Resize to fit canvas while maintaining aspect ratio
            canvas_width = self.screenshot_canvas.winfo_width()
            canvas_height = self.screenshot_canvas.winfo_height()

            if canvas_width < 10:
                canvas_width = 400
            if canvas_height < 10:
                canvas_height = 300

            img.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
            self.last_screenshot_tk = ImageTk.PhotoImage(img)
            self.last_raw_img_size = Image.open(BytesIO(img_data)).size # Keep track of original size

            if self.canvas_image_id:
                self.screenshot_canvas.delete(self.canvas_image_id)

            self.canvas_image_id = self.screenshot_canvas.create_image(
                canvas_width//2, canvas_height//2,
                anchor=tk.CENTER, image=self.last_screenshot_tk
            )
            # Store scale factors for coordinate mapping
            self.img_scale_x = self.last_raw_img_size[0] / img.size[0]
            self.img_scale_y = self.last_raw_img_size[1] / img.size[1]
            self.img_offset_x = (canvas_width - img.size[0]) / 2
            self.img_offset_y = (canvas_height - img.size[1]) / 2

        except Exception as e:
            logger.error(f"Failed to update screenshot in UI: {e}")

    def on_canvas_click(self, event):
        """将画布点击映射到屏幕坐标并发送命令。"""
        if not hasattr(self, 'img_scale_x'): return

        # Calculate coordinates relative to the image
        rel_x = event.x - self.img_offset_x
        rel_y = event.y - self.img_offset_y

        if 0 <= rel_x <= (self.last_raw_img_size[0] / self.img_scale_x) and \
           0 <= rel_y <= (self.last_raw_img_size[1] / self.img_scale_y):

            real_x = int(rel_x * self.img_scale_x)
            real_y = int(rel_y * self.img_scale_y)

            if self.command_callback:
                self.command_callback("manual_action", {"action": "left_click", "coordinate": (real_x, real_y)})

    def manual_action(self, action_type):
        """向 Jarvis 发送手动操作命令。"""
        if self.command_callback:
            if action_type == "type":
                # Prompt for text in a simple dialog or just use input entry?
                # Let's use whatever is in the input entry
                text = self.input_entry.get()
                if text:
                    self.command_callback("manual_action", {"action": "type", "text": text})
                else:
                    self.append_to_history("请先在输入框中输入文字。", "system_message")
            else:
                self.command_callback("manual_action", {"action": action_type})


    def on_display_mode_change(self):
        mode = self.display_mode_var.get()
        if self.command_callback:
            logger.info(f"Display mode changed to: {mode}")
            # We can reuse the command_callback with a special command_type
            self.command_callback("display_mode_change", mode)

    def set_command_callback(self, callback):
        self.command_callback = callback

    def _queue_ui_output(self, message, tag, response_id):
        self.msg_queue.put(("ui_output", (message, tag, response_id)))

    def _queue_voice_status(self, is_listening):
        self.msg_queue.put(("voice_status", is_listening))

    def _queue_link_status(self, connected, device):
        self.msg_queue.put(("link_status", (connected, device)))

    def _queue_screenshot_update(self, b64_data):
        self.msg_queue.put(("screenshot_update", b64_data))

    def _queue_archive_browser_update(self, zip_path, contents):
        self.msg_queue.put(("archive_browser_update", (zip_path, contents)))

    def _activate_nostalgia_ui(self):
        """Changes UI colors to a nostalgic 'No. 1 Middle School' theme."""
        self.msg_queue.put(("nostalgia_ui", None))

    def process_queue(self):
        """Processes messages from the background threads."""
        try:
            while not self.msg_queue.empty():
                msg_type, payload = self.msg_queue.get_nowait()
                if msg_type == "ui_output":
                    message, tag, response_id = payload
                    self.append_to_history(message, tag, response_id)
                elif msg_type == "voice_status":
                    self.update_listen_button_state(payload)
                elif msg_type == "link_status":
                    connected, device = payload
                    self.update_link_status(connected, device)
                elif msg_type == "screenshot_update":
                    self.update_screenshot(payload)
                elif msg_type == "archive_browser_update":
                    zip_path, contents = payload
                    self.update_archive_browser(zip_path, contents)
                elif msg_type == "nostalgia_ui":
                    self._apply_nostalgia_theme()
        finally:
            self.master.after(100, self.process_queue)

    def send_text_command(self, event=None):
        command = self.input_entry.get().strip()
        if command and self.command_callback:
            self.append_to_history(f"你: {command}", "user_prompt")
            logger.info(f"Sending text command: {command}")
            self.command_callback("text", command)
            self.input_entry.delete(0, tk.END)

    def send_listen_command(self):
        if self.command_callback:
            logger.info("Toggling voice command")
            self.command_callback("voice", None)

    def on_archive_item_double_click(self, event):
        item_id = self.archive_tree.selection()[0]
        item_text = self.archive_tree.item(item_id, "text")
        if self.command_callback and hasattr(self, 'current_zip_path'):
            self.command_callback("archive_action", {"action": "open", "zip_path": self.current_zip_path, "file_in_zip": item_text})

    def update_archive_browser(self, zip_path, contents):
        self.current_zip_path = zip_path
        self.archive_tree.delete(*self.archive_tree.get_children())
        for content in contents:
            self.archive_tree.insert('', 'end', text=content)
        # Force switch menu label
        self.archive_label.config(text=f"浏览: {os.path.basename(zip_path)}")

    def show_update_dialog(self, filename):
        """ModalDialog for update confirmation."""
        from tkinter import messagebox
        ans = messagebox.askyesnocancel("Butler 提醒", f"检测到 {filename} 已修改，是否同步回压缩包？", parent=self.master)
        return ans

    def update_listen_button_state(self, is_listening):
        if is_listening:
            self.listen_button.config(text="停止", relief=tk.SUNKEN, bg="#e06c75")
        else:
            self.listen_button.config(text="聆听", relief=tk.RAISED, bg=self.button_bg_color)

    def update_link_status(self, connected, device_name=""):
        """更新 UI 中的连接状态指示器。"""
        if connected:
            self.link_indicator.config(fg="#98c379") # Green
            self.link_text.config(text=f"已连接 ({device_name})")
        else:
            self.link_indicator.config(fg="gray")
            self.link_text.config(text="未连接")

    def set_input_text(self, text):
        self.input_entry.delete(0, tk.END)
        self.input_entry.insert(0, text)

    def clear_history(self):
        logger.info("Clearing history")
        self.output_text.config(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state='disabled')

    def open_settings_window(self):
        settings_win = tk.Toplevel(self.master)
        settings_win.title("设置")
        settings_win.config(bg=self.background_color)
        settings_win.transient(self.master)
        settings_win.grab_set()

        font_size_frame = tk.Frame(settings_win, bg=self.background_color)
        font_size_frame.pack(pady=10, padx=10)

        tk.Label(font_size_frame, text="字体大小:", bg=self.background_color, fg=self.foreground_color).pack(side=tk.LEFT, padx=(0, 5))

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

        tk.Radiobutton(font_size_frame, text="小", value='small', **font_radio_config).pack(side=tk.LEFT)
        tk.Radiobutton(font_size_frame, text="中", value='medium', **font_radio_config).pack(side=tk.LEFT)
        tk.Radiobutton(font_size_frame, text="大", value='large', **font_radio_config).pack(side=tk.LEFT)

    def update_font_size(self, size_mode):
        logger.info(f"正在将字体大小更新为 {size_mode}")
        fonts = self.font_configs[size_mode]

        # 更新控件
        self.menu_label.config(font=fonts["menu_label"])
        self.program_listbox.config(font=fonts["program_listbox"])
        self.output_text.config(font=fonts["output_text"])
        self.input_entry.config(font=fonts["input_entry"])

        # Update buttons
        button_font = fonts["buttons"]
        self.send_button.config(font=button_font)
        self.listen_button.config(font=button_font)
        self.clear_button.config(font=button_font)
        self.restart_button.config(font=button_font)
        self.settings_button.config(font=button_font)

        # Update text tags
        self.output_text.tag_config('user_prompt', font=fonts["user_prompt"])
        self.output_text.tag_config('system_message', font=fonts["system_message"])

    def _apply_nostalgia_theme(self):
        """Applies a sepia/nostalgic theme to the CommandPanel."""
        nostalgia_bg = '#2b261d' # Sepia dark
        nostalgia_fg = '#d4c5a1' # Aged paper

        self.config(bg=nostalgia_bg)
        self.output_text.config(bg=nostalgia_bg, fg=nostalgia_fg)
        self.input_entry.config(bg='#1a1610', fg=nostalgia_fg)
        self.menu_frame.config(bg='#1a1610')
        self.menu_label.config(bg='#1a1610', fg=nostalgia_fg)
        self.program_listbox.config(bg='#1a1610', fg=nostalgia_fg)

        # Change tags to match theme
        self.output_text.tag_config('user_prompt', foreground='#bc8f8f', background='#3a3429') # Rosy brown
        self.output_text.tag_config('ai_response', foreground=nostalgia_fg, background='#2b261d')
        self.output_text.tag_config('system_message', foreground='#deb887') # Burlywood

        self.append_to_history("--- 怀旧模式已开启：一中往事 ---", "system_message")

    def restart_application(self):
        logger.info("Restarting application")
        python = sys.executable
        os.execl(python, python, *sys.argv)
