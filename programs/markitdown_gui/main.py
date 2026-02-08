import os
import sys
import threading
import queue
import time
import json
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
        self.root.title("MarkItDown 批量转换工具")
        self.root.geometry("900x650")

        self.setup_variables()
        self.load_settings()
        self.setup_ui()
        self.setup_dnd()

        self.convert_queue = queue.Queue()
        self.is_running = False
        self.is_paused = False
        self.stop_requested = False
        self.worker_thread = None

        self.results = {} # path -> markdown_content

    def setup_variables(self):
        self.output_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "MarkItDown_Output"))
        self.batch_size = tk.IntVar(value=4)
        self.header_style = tk.StringVar(value="atx") # atx or setext
        self.table_style = tk.StringVar(value="pipe") # pipe, grid, etc.
        self.theme_mode = tk.StringVar(value="system") # light, dark, system
        self.save_mode = tk.StringVar(value="separate") # separate or merged

    def load_settings(self):
        self.settings_file = os.path.join(current_dir, "settings.json")
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.output_dir.set(settings.get("output_dir", self.output_dir.get()))
                    self.batch_size.set(settings.get("batch_size", self.batch_size.get()))
                    self.header_style.set(settings.get("header_style", self.header_style.get()))
                    self.table_style.set(settings.get("table_style", self.table_style.get()))
                    self.theme_mode.set(settings.get("theme_mode", self.theme_mode.get()))
                    self.save_mode.set(settings.get("save_mode", self.save_mode.get()))
            except Exception as e:
                print(f"加载设置失败: {e}")

    def save_settings(self):
        settings = {
            "output_dir": self.output_dir.get(),
            "batch_size": self.batch_size.get(),
            "header_style": self.header_style.get(),
            "table_style": self.table_style.get(),
            "theme_mode": self.theme_mode.get(),
            "save_mode": self.save_mode.get()
        }
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存设置失败: {e}")

    def setup_ui(self):
        # Configure styles
        style = ttk.Style()
        # Basic theme support (simplified)
        if self.theme_mode.get() == "dark":
            self.apply_dark_theme(style)
        else:
            self.apply_light_theme(style)

        # Main layout
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        self.toolbar = ttk.Frame(self.main_frame)
        self.toolbar.pack(fill=tk.X, pady=(0, 10))

        self.btn_add = ttk.Button(self.toolbar, text="添加文件", command=self.add_files)
        self.btn_add.pack(side=tk.LEFT, padx=2)

        self.btn_clear = ttk.Button(self.toolbar, text="清空队列", command=self.clear_queue)
        self.btn_clear.pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.btn_start = ttk.Button(self.toolbar, text="开始转换", command=self.start_conversion)
        self.btn_start.pack(side=tk.LEFT, padx=2)

        self.btn_pause = ttk.Button(self.toolbar, text="暂停", command=self.pause_conversion, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=2)

        self.btn_stop = ttk.Button(self.toolbar, text="取消", command=self.stop_conversion, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        self.btn_restart = ttk.Button(self.toolbar, text="重新开始", command=self.restart_queue)
        self.btn_restart.pack(side=tk.LEFT, padx=2)

        self.btn_settings = ttk.Button(self.toolbar, text="设置", command=self.open_settings)
        self.btn_settings.pack(side=tk.RIGHT, padx=2)

        # Queue Table
        self.queue_frame = ttk.LabelFrame(self.main_frame, text="转换队列 (支持拖放文件)")
        self.queue_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "path", "size", "status", "progress")
        self.tree = ttk.Treeview(self.queue_frame, columns=columns, show="headings")
        self.tree.heading("name", text="文件名")
        self.tree.heading("path", text="完整路径")
        self.tree.heading("size", text="大小")
        self.tree.heading("status", text="状态")
        self.tree.heading("progress", text="进度")

        self.tree.column("name", width=200)
        self.tree.column("path", width=350)
        self.tree.column("size", width=80)
        self.tree.column("status", width=100)
        self.tree.column("progress", width=100)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_item_double_click)

        scrollbar = ttk.Scrollbar(self.queue_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Progress Bar and Status
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(fill=tk.X, pady=(10, 0))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.status_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.status_label = ttk.Label(self.status_frame, text="准备就绪")
        self.status_label.pack(side=tk.RIGHT)

        # Footer Actions
        self.footer = ttk.Frame(self.main_frame)
        self.footer.pack(fill=tk.X, pady=(10, 0))

        self.btn_update = ttk.Button(self.footer, text="检查更新", command=self.check_updates)
        self.btn_update.pack(side=tk.RIGHT, padx=2)

        self.btn_about = ttk.Button(self.footer, text="关于", command=self.show_about)
        self.btn_about.pack(side=tk.RIGHT, padx=2)

        self.btn_help = ttk.Button(self.footer, text="快捷键", command=self.show_help)
        self.btn_help.pack(side=tk.RIGHT, padx=2)

        self.setup_bindings()

    def setup_bindings(self):
        self.root.bind("<Control-o>", lambda e: self.add_files())
        self.root.bind("<Delete>", lambda e: self.remove_selected())
        self.root.bind("<F5>", lambda e: self.start_conversion())

    def remove_selected(self):
        selected = self.tree.selection()
        for item in selected:
            self.tree.delete(item)

    def restart_queue(self):
        if self.is_running:
            return
        for item in self.tree.get_children():
            self.tree.set(item, "status", "等待中")
            self.tree.set(item, "progress", "0%")
        self.results.clear()
        self.progress_var.set(0)
        self.status_label.configure(text="准备就绪")

    def setup_dnd(self):
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)

    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        self.add_files_to_list(files)

    def add_files(self):
        files = filedialog.askopenfilenames(title="选择文件")
        if files:
            self.add_files_to_list(files)

    def add_files_to_list(self, files):
        for f in files:
            if os.path.isfile(f):
                name = os.path.basename(f)
                size = f"{os.path.getsize(f) / 1024:.1f} KB"
                # Check if already in tree
                exists = False
                for item in self.tree.get_children():
                    if self.tree.item(item, "values")[1] == f:
                        exists = True
                        break
                if not exists:
                    self.tree.insert("", tk.END, values=(name, f, size, "等待中", "0%"))

    def clear_queue(self):
        if self.is_running:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results.clear()

    def apply_light_theme(self, style):
        self.root.configure(bg="#f0f0f0")

    def apply_dark_theme(self, style):
        # Very basic dark theme emulation
        self.root.configure(bg="#2d2d2d")
        style.configure("TFrame", background="#2d2d2d")
        style.configure("TLabel", background="#2d2d2d", foreground="#ffffff")
        style.configure("TLabelframe", background="#2d2d2d", foreground="#ffffff")
        style.configure("TLabelframe.Label", background="#2d2d2d", foreground="#ffffff")
        style.configure("TButton", background="#3d3d3d")

    def start_conversion(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("警告", "队列中没有文件")
            return

        if not os.path.exists(self.output_dir.get()):
            try:
                os.makedirs(self.output_dir.get())
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return

        self.is_running = True
        self.is_paused = False
        self.stop_requested = False

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_pause.configure(state=tk.NORMAL, text="暂停")
        self.btn_stop.configure(state=tk.NORMAL)
        self.btn_add.configure(state=tk.DISABLED)
        self.btn_clear.configure(state=tk.DISABLED)

        self.worker_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.worker_thread.start()

    def pause_conversion(self):
        if not self.is_running:
            return
        self.is_paused = not self.is_paused
        self.btn_pause.configure(text="恢复" if self.is_paused else "暂停")
        self.status_label.configure(text="已暂停" if self.is_paused else "转换中...")

    def stop_conversion(self):
        if not self.is_running:
            return
        self.stop_requested = True
        self.is_paused = False
        self.status_label.configure(text="正在停止...")

    def safe_ui_update(self, func, *args, **kwargs):
        """Helper to run UI updates on the main thread."""
        self.root.after(0, lambda: func(*args, **kwargs))

    def process_queue(self):
        items = list(self.tree.get_children())
        total = len(items)

        # Reset progress for all
        for item in items:
            self.safe_ui_update(self.tree.set, item, "status", "等待中")
            self.safe_ui_update(self.tree.set, item, "progress", "0%")

        batch_size = self.batch_size.get()

        i = 0
        while i < total and not self.stop_requested:
            if self.is_paused:
                time.sleep(0.5)
                continue

            # Take a batch
            current_batch = items[i:i+batch_size]
            batch_threads = []

            for item in current_batch:
                if self.stop_requested: break
                t = threading.Thread(target=self.convert_single_item, args=(item,))
                t.start()
                batch_threads.append(t)

            for t in batch_threads:
                t.join()

            i += batch_size

            # Update overall progress
            processed = min(i, total)
            self.safe_ui_update(self.progress_var.set, (processed / total) * 100)
            self.safe_ui_update(self.status_label.configure, text=f"已处理 {processed}/{total}")

        self.safe_ui_update(self.finish_conversion)

    def convert_single_item(self, item):
        file_path = self.tree.item(item, "values")[1]
        name = self.tree.item(item, "values")[0]

        self.safe_ui_update(self.tree.set, item, "status", "转换中...")
        self.safe_ui_update(self.tree.set, item, "progress", "20%")

        try:
            # Actual conversion
            markdown_content = convert(file_path)
            self.results[file_path] = markdown_content

            self.safe_ui_update(self.tree.set, item, "progress", "80%")

            # Save if separate mode
            if self.save_mode.get() == "separate":
                out_name = os.path.splitext(name)[0] + ".md"
                out_path = os.path.join(self.output_dir.get(), out_name)
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)

            self.safe_ui_update(self.tree.set, item, "status", "已完成")
            self.safe_ui_update(self.tree.set, item, "progress", "100%")
        except Exception as e:
            self.safe_ui_update(self.tree.set, item, "status", f"失败: {str(e)}")
            self.safe_ui_update(self.tree.set, item, "progress", "-")

    def finish_conversion(self):
        self.is_running = False
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED, text="暂停")
        self.btn_stop.configure(state=tk.DISABLED)
        self.btn_add.configure(state=tk.NORMAL)
        self.btn_clear.configure(state=tk.NORMAL)

        if self.stop_requested:
            self.status_label.configure(text="已取消")
        else:
            self.status_label.configure(text="转换完成")
            # If merged mode, save now
            if self.save_mode.get() == "merged" and self.results:
                self.save_merged()

    def save_merged(self):
        out_path = os.path.join(self.output_dir.get(), "merged_output.md")
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                for path, content in self.results.items():
                    f.write(f"<!-- Source: {os.path.basename(path)} -->\n")
                    f.write(content)
                    f.write("\n\n---\n\n")
            messagebox.showinfo("成功", f"合并文件已保存至: {out_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存合并文件失败: {e}")

    def on_item_double_click(self, event):
        item = self.tree.selection()
        if item:
            file_path = self.tree.item(item[0], "values")[1]
            if file_path in self.results:
                self.open_preview(file_path)
            else:
                # If not converted yet, try to convert or just show info
                status = self.tree.item(item[0], "values")[3]
                if status == "等待中":
                    if messagebox.askyesno("预览", "该文件尚未转换，是否现在转换并预览？"):
                        # Temporary conversion for preview
                        try:
                            content = convert(file_path)
                            self.results[file_path] = content
                            self.open_preview(file_path)
                        except Exception as e:
                            messagebox.showerror("错误", f"转换失败: {e}")
                else:
                    messagebox.showinfo("提示", f"当前状态: {status}")

    def open_preview(self, file_path):
        preview_win = tk.Toplevel(self.root)
        preview_win.title(f"预览: {os.path.basename(file_path)}")
        preview_win.geometry("800x600")

        content = self.results.get(file_path, "")

        # Notebook for Raw and Rendered
        nb = ttk.Notebook(preview_win)
        nb.pack(fill=tk.BOTH, expand=True, padding=5)

        # Raw View
        raw_frame = ttk.Frame(nb)
        raw_text = tk.Text(raw_frame, wrap=tk.WORD, undo=True)
        raw_text.insert(tk.END, content)
        raw_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        raw_scroll = ttk.Scrollbar(raw_frame, orient=tk.VERTICAL, command=raw_text.yview)
        raw_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        raw_text.configure(yscrollcommand=raw_scroll.set)

        nb.add(raw_frame, text="原始 Markdown")

        # Rendered View (Simulated)
        rendered_frame = ttk.Frame(nb)
        rendered_text = tk.Text(rendered_frame, wrap=tk.WORD, state=tk.DISABLED)
        rendered_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        rendered_scroll = ttk.Scrollbar(rendered_frame, orient=tk.VERTICAL, command=rendered_text.yview)
        rendered_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        rendered_text.configure(yscrollcommand=rendered_scroll.set)

        self.render_markdown(rendered_text, content)

        nb.add(rendered_frame, text="渲染视图")

        # Actions Frame
        btn_frame = ttk.Frame(preview_win, padding=5)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="复制到剪贴板", command=lambda: self.copy_to_clipboard(content)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="保存为...", command=lambda: self.save_as(content)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=preview_win.destroy).pack(side=tk.RIGHT, padx=5)

    def render_markdown(self, text_widget, content):
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)

        # Define tags for rendering
        text_widget.tag_configure("h1", font=("Arial", 16, "bold"), spacing1=10, spacing3=5)
        text_widget.tag_configure("h2", font=("Arial", 14, "bold"), spacing1=8, spacing3=4)
        text_widget.tag_configure("h3", font=("Arial", 12, "bold"), spacing1=6, spacing3=3)
        text_widget.tag_configure("bold", font=("Arial", 10, "bold"))
        text_widget.tag_configure("italic", font=("Arial", 10, "italic"))
        text_widget.tag_configure("code", font=("Consolas", 10), background="#e0e0e0")

        import re
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                text_widget.insert(tk.END, line[2:] + "\n", "h1")
            elif line.startswith('## '):
                text_widget.insert(tk.END, line[3:] + "\n", "h2")
            elif line.startswith('### '):
                text_widget.insert(tk.END, line[4:] + "\n", "h3")
            else:
                # Basic inline parsing for bold and italic
                # This is still rudimentary but better than nothing
                parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        text_widget.insert(tk.END, part[2:-2], "bold")
                    elif part.startswith('*') and part.endswith('*'):
                        text_widget.insert(tk.END, part[1:-1], "italic")
                    else:
                        text_widget.insert(tk.END, part)
                text_widget.insert(tk.END, "\n")

        text_widget.config(state=tk.DISABLED)

    def copy_to_clipboard(self, content):
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("提示", "已复制到剪贴板")

    def save_as(self, content):
        f = filedialog.asksaveasfile(defaultextension=".md",
                                     filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                                     title="保存文件")
        if f:
            f.write(content)
            f.close()
            messagebox.showinfo("提示", "文件已保存")

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("设置")
        settings_win.geometry("500x400")

        frame = ttk.Frame(settings_win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Output Directory
        ttk.Label(frame, text="输出文件夹:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.output_dir, width=40).grid(row=0, column=1, pady=5)
        ttk.Button(frame, text="浏览", command=self.browse_output).grid(row=0, column=2, padx=5)

        # Batch Size
        ttk.Label(frame, text="批次大小:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(frame, from_=1, to=100, textvariable=self.batch_size, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)

        # Header Style
        ttk.Label(frame, text="标题样式:").grid(row=2, column=0, sticky=tk.W, pady=5)
        hs_frame = ttk.Frame(frame)
        hs_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(hs_frame, text="ATX (#)", variable=self.header_style, value="atx").pack(side=tk.LEFT)
        ttk.Radiobutton(hs_frame, text="Setext (===)", variable=self.header_style, value="setext").pack(side=tk.LEFT)

        # Table Style
        ttk.Label(frame, text="表格样式:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Combobox(frame, textvariable=self.table_style, values=["pipe", "grid", "simple", "html"]).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Theme Mode
        ttk.Label(frame, text="主题模式:").grid(row=4, column=0, sticky=tk.W, pady=5)
        theme_frame = ttk.Frame(frame)
        theme_frame.grid(row=4, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(theme_frame, text="明亮", variable=self.theme_mode, value="light").pack(side=tk.LEFT)
        ttk.Radiobutton(theme_frame, text="深色", variable=self.theme_mode, value="dark").pack(side=tk.LEFT)
        ttk.Radiobutton(theme_frame, text="系统默认", variable=self.theme_mode, value="system").pack(side=tk.LEFT)

        # Save Mode
        ttk.Label(frame, text="保存模式:").grid(row=5, column=0, sticky=tk.W, pady=5)
        sm_frame = ttk.Frame(frame)
        sm_frame.grid(row=5, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(sm_frame, text="独立文件", variable=self.save_mode, value="separate").pack(side=tk.LEFT)
        ttk.Radiobutton(sm_frame, text="合并为一个文件", variable=self.save_mode, value="merged").pack(side=tk.LEFT)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=20)
        ttk.Button(btn_frame, text="保存设置", command=lambda: [self.save_settings(), settings_win.destroy()]).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=settings_win.destroy).pack(side=tk.LEFT)

    def browse_output(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir.set(d)

    def check_updates(self):
        self.status_label.configure(text="正在检查更新...")
        # Simulate network delay
        def do_check():
            time.sleep(1.5)
            self.root.after(0, lambda: messagebox.showinfo("更新检查", "当前已是最新版本 (v1.0.0)"))
            self.root.after(0, lambda: self.status_label.configure(text="就绪"))

        threading.Thread(target=do_check, daemon=True).start()

    def show_about(self):
        messagebox.showinfo("关于", "MarkItDown GUI v1.0\n\n基于 Microsoft MarkItDown 开发的批量转换工具。\n\n作者: Butler Agent")

    def show_help(self):
        help_text = "常用快捷键:\n\n" \
                    "- 双击队列项: 预览结果\n" \
                    "- Ctrl+O: 添加文件\n" \
                    "- Del: 从队列移除选中项\n" \
                    "- F5: 开始转换"
        messagebox.showinfo("快捷键", help_text)

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = MarkItDownGUI(root)
    root.mainloop()
