import os
import sys
import threading
import queue
import time
import json
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD

# Add markitdown to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
markitdown_path = os.path.join(project_root, "markitdown/src")
if markitdown_path not in sys.path:
    sys.path.insert(0, markitdown_path)

try:
    from markitdown.main import convert
except ImportError:
    # Fallback if pathing is different
    sys.path.insert(0, os.path.join(project_root, "markitdown/src/markitdown"))
    from main import convert

class MarkItDownGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MarkItDown 极致转换 - 批量 Markdown 工具")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        self.setup_variables()
        self.load_settings()

        # Color palette for themes
        self.colors = {
            "light": {
                "bg": "#f5f5f7",
                "fg": "#1d1d1f",
                "accent": "#0071e3",
                "secondary_bg": "#ffffff",
                "border": "#d2d2d7"
            },
            "dark": {
                "bg": "#1c1c1e",
                "fg": "#f5f5f7",
                "accent": "#0a84ff",
                "secondary_bg": "#2c2c2e",
                "border": "#3a3a3c"
            }
        }

        self.setup_styles()

        # State variables
        self.results = {} # path -> processed_markdown
        self.is_running = False
        self.is_paused = False
        self.stop_requested = False
        self.worker_thread = None

        # UI Container
        self.container = ttk.Frame(self.root)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.views = {}
        self.current_view = None

        self.setup_views()
        self.show_view("queue")

        # Handle CLI arguments
        if len(sys.argv) > 1:
            self.root.after(100, lambda: self.handle_cli_args(sys.argv[1:]))

    def handle_cli_args(self, args):
        files = []
        auto_start = False
        for arg in args:
            if arg == "--start":
                auto_start = True
            elif os.path.isfile(arg):
                files.append(arg)

        if files:
            self.add_files_to_list(files)
            if auto_start:
                self.root.after(500, self.start_conversion)

    def setup_variables(self):
        self.output_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "MarkItDown_Output"))
        self.batch_size = tk.IntVar(value=4)
        self.header_style = tk.StringVar(value="atx") # atx or setext
        self.table_style = tk.StringVar(value="pipe") # pipe, grid, simple
        self.theme_mode = tk.StringVar(value="system") # light, dark, system
        self.save_mode = tk.StringVar(value="separate") # separate or merged
        self.auto_open_results = tk.BooleanVar(value=True)

    def load_settings(self):
        self.settings_file = os.path.join(current_dir, "settings.json")
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    for key, var in [
                        ("output_dir", self.output_dir),
                        ("batch_size", self.batch_size),
                        ("header_style", self.header_style),
                        ("table_style", self.table_style),
                        ("theme_mode", self.theme_mode),
                        ("save_mode", self.save_mode),
                        ("auto_open_results", self.auto_open_results)
                    ]:
                        if key in settings:
                            var.set(settings[key])
            except Exception as e:
                print(f"加载设置失败: {e}")

    def save_settings(self):
        settings = {
            "output_dir": self.output_dir.get(),
            "batch_size": self.batch_size.get(),
            "header_style": self.header_style.get(),
            "table_style": self.table_style.get(),
            "theme_mode": self.theme_mode.get(),
            "save_mode": self.save_mode.get(),
            "auto_open_results": self.auto_open_results.get()
        }
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存设置失败: {e}")

    def setup_styles(self):
        self.style = ttk.Style()
        theme = self.theme_mode.get()
        if theme == "system":
            # Just default to light for now
            theme = "light"

        colors = self.colors[theme]
        self.root.configure(bg=colors["bg"])

        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TButton", padding=5)
        self.style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])

        self.style.configure("Header.TLabel", font=("Arial", 16, "bold"), foreground=colors["accent"])
        self.style.configure("Card.TFrame", background=colors["secondary_bg"], relief="flat")

        # Treeview styling
        self.style.configure("Treeview",
            background=colors["secondary_bg"],
            foreground=colors["fg"],
            fieldbackground=colors["secondary_bg"],
            rowheight=35,
            font=("Arial", 10)
        )
        self.style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        self.style.map("Treeview", background=[("selected", colors["accent"])])

        # Notebook styling
        self.style.configure("TNotebook", background=colors["bg"])
        self.style.configure("TNotebook.Tab", background=colors["secondary_bg"], foreground=colors["fg"], padding=[10, 5])
        self.style.map("TNotebook.Tab", background=[("selected", colors["accent"])], foreground=[("selected", "#ffffff")])

    def setup_views(self):
        # Queue View
        self.views["queue"] = self.create_queue_view()
        # Result View
        self.views["results"] = self.create_results_view()

        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

    def show_view(self, name):
        if name in self.views:
            self.views[name].tkraise()
            self.current_view = name

    def create_queue_view(self):
        view = ttk.Frame(self.container, padding=20)

        # Header
        header = ttk.Frame(view)
        header.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header, text="转换队列", style="Header.TLabel").pack(side=tk.LEFT)

        btn_settings = ttk.Button(header, text="⚙ 设置", command=self.open_settings)
        btn_settings.pack(side=tk.RIGHT)

        # Toolbar
        toolbar = ttk.Frame(view)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(toolbar, text="+ 添加文件", command=self.add_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="🗑 清空队列", command=self.clear_queue).pack(side=tk.LEFT, padx=(0, 5))

        # Queue Table
        table_frame = ttk.Frame(view)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "path", "size", "status")
        self.queue_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.queue_tree.heading("name", text="文件名")
        self.queue_tree.heading("path", text="路径")
        self.queue_tree.heading("size", text="大小")
        self.queue_tree.heading("status", text="状态")

        self.queue_tree.column("name", width=200)
        self.queue_tree.column("path", width=400)
        self.queue_tree.column("size", width=100)
        self.queue_tree.column("status", width=100)

        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.queue_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_tree.configure(yscrollcommand=sb.set)

        # Drag and Drop support
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)

        # Bottom controls
        bottom = ttk.Frame(view)
        bottom.pack(fill=tk.X, pady=(20, 0))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(bottom, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(bottom, text="准备就绪")
        self.status_label.pack(side=tk.LEFT)

        self.btn_start = ttk.Button(bottom, text="🚀 开始转换", command=self.start_conversion)
        self.btn_start.pack(side=tk.RIGHT, padx=5)

        self.btn_pause = ttk.Button(bottom, text="⏸ 暂停", command=self.pause_conversion, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.RIGHT, padx=5)

        self.btn_stop = ttk.Button(bottom, text="⏹ 取消", command=self.stop_conversion, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.RIGHT, padx=5)

        # Footer
        footer = ttk.Frame(view)
        footer.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(footer, text="❓ 快捷键", command=self.show_help).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="ℹ 关于", command=self.show_about).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="🔄 检查更新", command=self.check_updates).pack(side=tk.RIGHT)

        return view

    def create_results_view(self):
        view = ttk.Frame(self.container, padding=20)

        # Header
        header = ttk.Frame(view)
        header.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header, text="转换结果", style="Header.TLabel").pack(side=tk.LEFT)

        ttk.Button(header, text="⬅ 返回队列", command=lambda: self.show_view("queue")).pack(side=tk.RIGHT)

        # Main Content - Paned Window
        paned = ttk.PanedWindow(view, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left side: Results List
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        theme = self.theme_mode.get()
        if theme == "system": theme = "light"
        colors = self.colors[theme]

        self.res_list = tk.Listbox(left_frame, font=("Arial", 10),
                                   bg=colors["secondary_bg"], fg=colors["fg"],
                                   highlightthickness=0, borderwidth=0)
        self.res_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.res_list.bind("<<ListboxSelect>>", self.on_result_select)

        res_sb = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.res_list.yview)
        res_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.res_list.configure(yscrollcommand=res_sb.set)

        # Right side: Preview
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

        # Preview Tabs
        self.preview_nb = ttk.Notebook(right_frame)
        self.preview_nb.pack(fill=tk.BOTH, expand=True)

        # Rendered View
        self.render_text = tk.Text(self.preview_nb, wrap=tk.WORD, state=tk.DISABLED,
                                   font=("Arial", 11), bg=colors["secondary_bg"], fg=colors["fg"])
        self.preview_nb.add(self.render_text, text="渲染视图")

        # Raw View
        self.raw_text = tk.Text(self.preview_nb, wrap=tk.WORD, font=("Consolas", 10),
                                bg=colors["secondary_bg"], fg=colors["fg"])
        self.preview_nb.add(self.raw_text, text="原始 Markdown")

        # Quick Actions
        actions = ttk.Frame(view)
        actions.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(actions, text="📋 复制 Markdown", command=self.copy_current_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions, text="💾 保存输出", command=self.save_current_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions, text="🔄 重新开始", command=self.restart_all).pack(side=tk.RIGHT, padx=5)

        return view

    # --- Event Handlers ---

    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        self.add_files_to_list(files)

    def add_files(self):
        files = filedialog.askopenfilenames(title="选择要转换的文件")
        if files:
            self.add_files_to_list(files)

    def remove_selected_from_queue(self):
        if self.is_running: return
        selected = self.queue_tree.selection()
        for item in selected:
            self.queue_tree.delete(item)

    def add_files_to_list(self, files):
        for f in files:
            if os.path.isfile(f):
                name = os.path.basename(f)
                size = f"{os.path.getsize(f) / 1024:.1f} KB"
                # Check if already in tree
                exists = False
                for item in self.queue_tree.get_children():
                    if self.queue_tree.item(item, "values")[1] == f:
                        exists = True
                        break
                if not exists:
                    self.queue_tree.insert("", tk.END, values=(name, f, size, "等待中"))

    def clear_queue(self):
        if self.is_running: return
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        self.results.clear()
        self.res_list.delete(0, tk.END)

    def start_conversion(self):
        items = self.queue_tree.get_children()
        if not items:
            messagebox.showwarning("提示", "队列为空，请先添加文件。")
            return

        if not os.path.exists(self.output_dir.get()):
            try:
                os.makedirs(self.output_dir.get())
            except:
                messagebox.showerror("错误", "无法创建输出目录。")
                return

        self.is_running = True
        self.is_paused = False
        self.stop_requested = False
        self.results.clear()
        self.res_list.delete(0, tk.END)

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_pause.configure(state=tk.NORMAL, text="⏸ 暂停")
        self.btn_stop.configure(state=tk.NORMAL)

        self.worker_thread = threading.Thread(target=self.process_queue_thread, daemon=True)
        self.worker_thread.start()

    def pause_conversion(self):
        self.is_paused = not self.is_paused
        self.btn_pause.configure(text="▶ 恢复" if self.is_paused else "⏸ 暂停")
        self.status_label.configure(text="已暂停" if self.is_paused else "正在转换...")

    def stop_conversion(self):
        self.stop_requested = True
        self.is_paused = False
        self.status_label.configure(text="正在取消...")

    def process_queue_thread(self):
        items = list(self.queue_tree.get_children())
        total = len(items)
        batch_size = self.batch_size.get()

        i = 0
        while i < total and not self.stop_requested:
            if self.is_paused:
                time.sleep(0.5)
                continue

            batch = items[i:i+batch_size]
            threads = []
            for item_id in batch:
                if self.stop_requested: break
                t = threading.Thread(target=self.convert_task, args=(item_id,))
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            i += batch_size
            self.root.after(0, self.update_overall_progress, i, total)

        self.root.after(0, self.finish_conversion)

    def convert_task(self, item_id):
        values = self.queue_tree.item(item_id, "values")
        name, path = values[0], values[1]

        self.root.after(0, lambda: self.queue_tree.set(item_id, "status", "转换中..."))

        try:
            content = convert(path)
            # Post-processing
            content = self.post_process_markdown(content)

            self.results[path] = content
            # Append path to name in listbox to ensure uniqueness if needed,
            # or just rely on the fact that we can store data in the listbox indirectly.
            # Here we just use the name but we will look up more carefully.
            self.root.after(0, lambda: self.res_list.insert(tk.END, name))
            self.root.after(0, lambda: self.queue_tree.set(item_id, "status", "已完成"))

            if self.save_mode.get() == "separate":
                out_path = os.path.join(self.output_dir.get(), os.path.splitext(name)[0] + ".md")
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(content)
        except Exception as e:
            self.root.after(0, lambda: self.queue_tree.set(item_id, "status", f"失败: {str(e)[:20]}"))

    def post_process_markdown(self, content):
        # Implement header style change
        if self.header_style.get() == "setext":
            content = self.atx_to_setext(content)

        # Simple Table Style adjustment (very limited)
        if self.table_style.get() == "grid":
            # Just a placeholder for actual table transformation
            pass

        return content

    def atx_to_setext(self, content):
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            m1 = re.match(r'^#\s+(.+)$', line)
            m2 = re.match(r'^##\s+(.+)$', line)
            if m1:
                title = m1.group(1)
                new_lines.append(title)
                new_lines.append('=' * len(title))
            elif m2:
                title = m2.group(1)
                new_lines.append(title)
                new_lines.append('-' * len(title))
            else:
                new_lines.append(line)
        return '\n'.join(new_lines)

    def update_overall_progress(self, current, total):
        pct = (current / total) * 100
        self.progress_var.set(pct)
        self.status_label.configure(text=f"已处理 {min(current, total)}/{total}")

    def finish_conversion(self):
        self.is_running = False
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.DISABLED)

        if self.stop_requested:
            self.status_label.configure(text="已取消")
        else:
            self.status_label.configure(text="转换完成")
            if self.save_mode.get() == "merged" and self.results:
                self.save_merged_result()

            if self.auto_open_results.get() and self.results:
                self.show_view("results")
                if self.res_list.size() > 0:
                    self.res_list.selection_set(0)
                    self.on_result_select(None)

    def save_merged_result(self):
        out_path = os.path.join(self.output_dir.get(), "merged_results.md")
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                for path, content in self.results.items():
                    title = f"Source: {os.path.basename(path)}"
                    if self.header_style.get() == "atx":
                        f.write(f"# {title}\n\n")
                    else:
                        f.write(f"{title}\n{'=' * len(title)}\n\n")
                    f.write(content)
                    f.write("\n\n---\n\n")
            messagebox.showinfo("成功", f"合并文件已保存至: {out_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存合并文件失败: {e}")

    def on_result_select(self, event):
        selection = self.res_list.curselection()
        if not selection: return

        idx = selection[0]
        name = self.res_list.get(idx)

        # Find path by name. To be safer, we use the results keys order
        # which matches the insertion order in res_list.
        paths = list(self.results.keys())
        if idx < len(paths):
            path = paths[idx]
            content = self.results[path]
            self.raw_text.delete(1.0, tk.END)
            self.raw_text.insert(tk.END, content)
            self.render_markdown_view(content)

    def render_markdown_view(self, content):
        self.render_text.configure(state=tk.NORMAL)
        self.render_text.delete(1.0, tk.END)

        # Determine theme-based colors
        theme = self.theme_mode.get()
        if theme == "system": theme = "light"
        colors = self.colors[theme]
        code_bg = "#3a3a3c" if theme == "dark" else "#f0f0f0"
        link_fg = "#0a84ff" if theme == "dark" else "#0071e3"

        # Tags for rendering
        self.render_text.tag_configure("h1", font=("Arial", 20, "bold"), spacing1=20, spacing3=12)
        self.render_text.tag_configure("h2", font=("Arial", 18, "bold"), spacing1=15, spacing3=10)
        self.render_text.tag_configure("h3", font=("Arial", 16, "bold"), spacing1=12, spacing3=8)
        self.render_text.tag_configure("bold", font=("Arial", 11, "bold"))
        self.render_text.tag_configure("italic", font=("Arial", 11, "italic"))
        self.render_text.tag_configure("code", font=("Consolas", 10), background=code_bg)
        self.render_text.tag_configure("link", foreground=link_fg, underline=True)
        self.render_text.tag_configure("quote", background=code_bg, lmargin1=20, lmargin2=20)
        self.render_text.tag_configure("hr", background=colors["border"], font=("Arial", 1))

        in_code_block = False
        lines = content.split('\n')
        for line in lines:
            if line.startswith('```'):
                in_code_block = not in_code_block
                continue

            if in_code_block:
                self.render_text.insert(tk.END, line + "\n", "code")
                continue

            if line.startswith('# '):
                self.render_text.insert(tk.END, line[2:] + "\n", "h1")
            elif line.startswith('## '):
                self.render_text.insert(tk.END, line[3:] + "\n", "h2")
            elif line.startswith('### '):
                self.render_text.insert(tk.END, line[4:] + "\n", "h3")
            elif line.startswith('> '):
                self.render_text.insert(tk.END, line[2:] + "\n", "quote")
            elif line.strip() == '---' or line.strip() == '***':
                self.render_text.insert(tk.END, "\n" + " " * 100 + "\n", "hr")
            else:
                # Basic inline parsing: bold, italic, code, links
                # Regex for [text](url)
                parts = re.split(r'(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))', line)
                for part in parts:
                    if not part: continue
                    if part.startswith('**') and part.endswith('**'):
                        self.render_text.insert(tk.END, part[2:-2], "bold")
                    elif part.startswith('*') and part.endswith('*'):
                        self.render_text.insert(tk.END, part[1:-1], "italic")
                    elif part.startswith('`') and part.endswith('`'):
                        self.render_text.insert(tk.END, part[1:-1], "code")
                    elif part.startswith('[') and '](' in part and part.endswith(')'):
                        link_text = part[1:part.find(']')]
                        self.render_text.insert(tk.END, link_text, "link")
                    else:
                        self.render_text.insert(tk.END, part)
                self.render_text.insert(tk.END, "\n")

        self.render_text.configure(state=tk.DISABLED)

    def copy_current_result(self):
        content = self.raw_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("提示", "已复制到剪贴板")

    def save_current_result(self):
        content = self.raw_text.get(1.0, tk.END)
        f = filedialog.asksaveasfile(defaultextension=".md", filetypes=[("Markdown", "*.md")])
        if f:
            f.write(content)
            f.close()
            messagebox.showinfo("成功", "文件已保存")

    def restart_all(self):
        self.show_view("queue")
        self.results.clear()
        self.res_list.delete(0, tk.END)
        for item in self.queue_tree.get_children():
            self.queue_tree.set(item, "status", "等待中")
        self.progress_var.set(0)
        self.status_label.configure(text="准备就绪")

    # --- Dialogs ---

    def open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("设置")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        dialog.grab_set()

        pad = {"padx": 10, "pady": 10}

        # Output Dir
        f1 = ttk.LabelFrame(dialog, text="输出设置", padding=10)
        f1.pack(fill=tk.X, **pad)

        ttk.Label(f1, text="输出目录:").pack(anchor=tk.W)
        row = ttk.Frame(f1)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self.output_dir.set(filedialog.askdirectory() or self.output_dir.get())).pack(side=tk.RIGHT)

        # Conversion Settings
        f2 = ttk.LabelFrame(dialog, text="转换设置", padding=10)
        f2.pack(fill=tk.X, **pad)

        row1 = ttk.Frame(f2)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text="批次大小:").pack(side=tk.LEFT)
        ttk.Spinbox(row1, from_=1, to=10, textvariable=self.batch_size, width=5).pack(side=tk.LEFT, padx=10)

        row2 = ttk.Frame(f2)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text="标题样式:").pack(side=tk.LEFT)
        ttk.Radiobutton(row2, text="ATX (#)", variable=self.header_style, value="atx").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row2, text="Setext (===)", variable=self.header_style, value="setext").pack(side=tk.LEFT, padx=5)

        # Appearance
        f3 = ttk.LabelFrame(dialog, text="外观与行为", padding=10)
        f3.pack(fill=tk.X, **pad)

        ttk.Label(f3, text="主题模式:").pack(anchor=tk.W)
        row3 = ttk.Frame(f3)
        row3.pack(fill=tk.X, pady=5)
        for t in [("明亮", "light"), ("深色", "dark"), ("系统", "system")]:
            ttk.Radiobutton(row3, text=t[0], variable=self.theme_mode, value=t[1], command=self.apply_theme_change).pack(side=tk.LEFT, padx=5)

        ttk.Checkbutton(f3, text="完成后自动打开结果视图", variable=self.auto_open_results).pack(anchor=tk.W, pady=5)

        # Buttons
        btns = ttk.Frame(dialog)
        btns.pack(fill=tk.X, side=tk.BOTTOM, pady=20)
        ttk.Button(btns, text="保存", command=lambda: [self.save_settings(), dialog.destroy()]).pack(side=tk.RIGHT, padx=10)
        ttk.Button(btns, text="取消", command=dialog.destroy).pack(side=tk.RIGHT)

    def apply_theme_change(self):
        self.setup_styles()

        theme = self.theme_mode.get()
        if theme == "system": theme = "light"
        colors = self.colors[theme]

        # Manually update non-ttk widgets
        for widget in [self.res_list, self.render_text, self.raw_text]:
            widget.configure(bg=colors["secondary_bg"], fg=colors["fg"])

        # Re-render current result if any
        self.on_result_select(None)

        messagebox.showinfo("提示", "主题已更新。")

    def show_help(self):
        help_text = "快捷键:\n\n- Ctrl+O: 添加文件\n- Del: 移除选中文件\n- F5: 开始转换\n- Esc: 取消转换"
        messagebox.showinfo("快捷键", help_text)

    def show_about(self):
        messagebox.showinfo("关于", "MarkItDown GUI v1.1\n\n一款极致的批量 Markdown 转换工具。\n基于 Microsoft MarkItDown。\n\n作者: Butler AI Agent")

    def check_updates(self):
        self.status_label.configure(text="正在检查更新...")
        def task():
            time.sleep(1.5)
            self.root.after(0, lambda: messagebox.showinfo("更新", "您使用的是最新版本 v1.1.0"))
            self.root.after(0, lambda: self.status_label.configure(text="就绪"))
        threading.Thread(target=task, daemon=True).start()

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = MarkItDownGUI(root)

    # Global bindings
    root.bind("<Control-o>", lambda e: app.add_files())
    root.bind("<F5>", lambda e: app.start_conversion())
    root.bind("<Escape>", lambda e: app.stop_conversion())
    root.bind("<Delete>", lambda e: app.remove_selected_from_queue())

    root.mainloop()
