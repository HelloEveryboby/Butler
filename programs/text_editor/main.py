import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import json
import re
from datetime import datetime

# Add project root to path to import package modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from package.log_manager import LogManager
    logger = LogManager.get_logger("TextEditor")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("TextEditor")

try:
    from package.TextEditor import ArchiveManager
except ImportError:
    ArchiveManager = None

import chardet

from pygments import lexers, highlight
from pygments.lexers import get_lexer_for_filename, guess_lexer
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound

# Check for tkinterdnd2
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, *args):
        # Let the actual widget perform the command
        try:
            result = self.tk.call((self._orig,) + args)
        except tk.TclError:
            return None

        # Generate events that we can listen to
        if (args[0] in ("insert", "replace", "delete") or
            args[0:3] == ("mark", "set", "insert") or
            args[0:2] == ("xview", "moveto") or
            args[0:2] == ("xview", "scroll") or
            args[0:2] == ("yview", "moveto") or
            args[0:2] == ("yview", "scroll")
        ):
            self.event_generate("<<Change>>", when="tail")

        return result

class LineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None

    def redraw(self, *args):
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, fill=self.textwidget.cget("insertbackground"))
            i = self.textwidget.index("%s+1line" % i)

class EditorTab(ttk.Frame):
    def __init__(self, master, editor, file_path=None, **kwargs):
        super().__init__(master, **kwargs)
        self.editor = editor
        self.file_path = file_path
        self.last_modified = 0
        self.content_modified = False

        self.setup_ui()

        if file_path:
            self.load_file(file_path)
        else:
            self.title = "未命名"

    def setup_ui(self):
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.linenumbers = LineNumbers(self, width=40, highlightthickness=0)
        self.linenumbers.pack(side=tk.LEFT, fill=tk.Y)

        self.text_area = CustomText(self, undo=True, wrap=tk.NONE,
                                    yscrollcommand=self.v_scroll.set,
                                    xscrollcommand=self.h_scroll.set,
                                    font=("Consolas", 12),
                                    padx=5, pady=5)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.v_scroll.config(command=self.text_area.yview)
        self.h_scroll.config(command=self.text_area.xview)

        self.linenumbers.textwidget = self.text_area

        self.text_area.bind("<<Change>>", self.on_change)
        self.text_area.bind("<Configure>", self.on_change)
        self.text_area.bind("<KeyRelease>", self.on_key_release)

        # Highlighting tags
        self.setup_tags()

    def setup_tags(self):
        # Basic tags for syntax highlighting (will be updated by pygments)
        self.text_area.tag_configure("found", background="yellow")
        self.text_area.tag_configure("match", background="orange")
        self.text_area.tag_configure("bracket", background="cyan")

    def on_change(self, event):
        self.linenumbers.redraw()

    def on_key_release(self, event):
        if not self.content_modified:
            self.content_modified = True
            self.editor.update_tab_title(self)

        # Simple auto-indent
        if event.keysym == 'Return':
            self.auto_indent()

        # Bracket matching
        self.highlight_brackets()

        # Syntax highlighting (throttled)
        self.editor.schedule_highlight(self)

    def highlight_brackets(self):
        self.text_area.tag_remove("bracket", "1.0", tk.END)
        pos = self.text_area.index(tk.INSERT)

        # Check char before cursor
        try:
            char = self.text_area.get(f"{pos}-1c")
            if char in "()[]{}":
                self.match_bracket(f"{pos}-1c", char)
        except: pass

    def match_bracket(self, pos, char):
        pairs = {"(": ")", "[": "]", "{": "}", ")": "(", "]": "[", "}": "{"}
        other = pairs[char]
        direction = 1 if char in "([{" else -1

        start = pos
        search_pos = pos

        if direction == 1:
            search_pos = self.text_area.search(f"\\{other}" if other in "[](){}" else other, f"{search_pos}+1c", stopindex=tk.END, regexp=True)
        else:
            search_pos = self.text_area.search(f"\\{other}" if other in "[](){}" else other, f"{search_pos}-1c", stopindex="1.0", backwards=True, regexp=True)

        if search_pos:
            self.text_area.tag_add("bracket", start, f"{start}+1c")
            self.text_area.tag_add("bracket", search_pos, f"{search_pos}+1c")

    def auto_indent(self):
        idx = self.text_area.index(tk.INSERT + " -1 line")
        line = self.text_area.get(idx + " linestart", idx + " lineend")
        whitespace = re.match(r"^\s*", line).group(0)
        self.text_area.insert(tk.INSERT, whitespace)

    def load_file(self, file_path):
        try:
            # Detect encoding
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'

            content = raw_data.decode(encoding)

            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, content)
            self.file_path = file_path
            self.title = os.path.basename(file_path)
            self.content_modified = False
            self.text_area.edit_reset()
            self.editor.schedule_highlight(self)
        except Exception as e:
            messagebox.showerror("错误", f"无法加载文件: {e}")

    def save_file(self, file_path=None):
        target_path = file_path or self.file_path
        if not target_path:
            target_path = filedialog.asksaveasfilename(defaultextension=".txt")

        if target_path:
            try:
                content = self.text_area.get(1.0, tk.END)
                # Remove trailing newline added by tk.Text
                if content.endswith('\n'):
                    content = content[:-1]

                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                self.file_path = target_path
                self.title = os.path.basename(target_path)
                self.content_modified = False
                self.editor.update_tab_title(self)
                return True
            except Exception as e:
                messagebox.showerror("错误", f"无法保存文件: {e}")
        return False

class TextEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("极简代码编辑器")
        self.root.geometry("1000x700")

        self.recent_files = []
        self.load_config()

        self.setup_ui()
        self.setup_menu()

        self.highlight_timer = None

        # Default empty tab
        self.new_file()

        if HAS_DND:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.handle_drop)

    def setup_ui(self):
        # Toolbar
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(self.toolbar, text="新建", command=self.new_file).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(self.toolbar, text="打开", command=self.open_file).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(self.toolbar, text="保存", command=self.save_file).pack(side=tk.LEFT, padx=2, pady=2)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # Status Bar
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text="就绪")
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.cursor_label = ttk.Label(self.status_bar, text="行: 1, 列: 0")
        self.cursor_label.pack(side=tk.RIGHT, padx=5)

    def setup_menu(self):
        menubar = tk.Menu(self.root)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="新建", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="打开", accelerator="Ctrl+O", command=self.open_file)

        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="最近打开", menu=self.recent_menu)
        self.update_recent_menu()

        file_menu.add_separator()
        file_menu.add_command(label="保存", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="另存为", command=self.save_as)
        file_menu.add_separator()

        if ArchiveManager:
            file_menu.add_command(label="压缩当前文件...", command=self.archive_current)

        file_menu.add_command(label="删除当前文件", command=self.delete_current)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_exit)
        menubar.add_cascade(label="文件", menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="撤销", accelerator="Ctrl+Z", command=lambda: self.current_tab().text_area.event_generate("<<Undo>>"))
        edit_menu.add_command(label="重做", accelerator="Ctrl+Y", command=lambda: self.current_tab().text_area.event_generate("<<Redo>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="剪切", accelerator="Ctrl+X", command=lambda: self.current_tab().text_area.event_generate("<<Cut>>"))
        edit_menu.add_command(label="复制", accelerator="Ctrl+C", command=lambda: self.current_tab().text_area.event_generate("<<Copy>>"))
        edit_menu.add_command(label="粘贴", accelerator="Ctrl+V", command=lambda: self.current_tab().text_area.event_generate("<<Paste>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="全选", accelerator="Ctrl+A", command=self.select_all)
        edit_menu.add_command(label="注释/取消注释", accelerator="Ctrl+/", command=self.toggle_comment)
        edit_menu.add_separator()
        edit_menu.add_command(label="查找与替换", accelerator="Ctrl+F", command=self.show_find_replace)
        menubar.add_cascade(label="编辑", menu=edit_menu)

        # View Menu
        view_menu = tk.Menu(menubar, tearoff=0)
        self.word_wrap = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="自动换行", variable=self.word_wrap, command=self.toggle_word_wrap)

        self.theme_var = tk.StringVar(value="light")
        view_menu.add_radiobutton(label="浅色模式", variable=self.theme_var, value="light", command=self.apply_theme)
        view_menu.add_radiobutton(label="深色模式", variable=self.theme_var, value="dark", command=self.apply_theme)

        menubar.add_cascade(label="视图", menu=view_menu)

        self.root.config(menu=menubar)

        # Bindings
        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-f>", lambda e: self.show_find_replace())
        self.root.bind("<Control-a>", lambda e: self.select_all())
        self.root.bind("<Control-slash>", lambda e: self.toggle_comment())
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def select_all(self, event=None):
        tab = self.current_tab()
        if tab:
            tab.text_area.tag_add(tk.SEL, "1.0", tk.END)
            return "break"

    def toggle_comment(self, event=None):
        tab = self.current_tab()
        if not tab: return

        try:
            # Determine comment character based on file extension
            ext = os.path.splitext(tab.file_path)[1] if tab.file_path else ".txt"
            comment_char = "#"
            if ext in [".cpp", ".c", ".java", ".js"]: comment_char = "//"
            elif ext in [".html", ".xml"]: return # HTML is multi-line <!-- -->

            try:
                start_idx = tab.text_area.index(tk.SEL_FIRST)
                end_idx = tab.text_area.index(tk.SEL_LAST)
            except tk.TclError:
                start_idx = tab.text_area.index("insert linestart")
                end_idx = tab.text_area.index("insert lineend")

            start_line = int(start_idx.split(".")[0])
            end_line = int(end_idx.split(".")[0])

            for line_num in range(start_line, end_line + 1):
                line_start = f"{line_num}.0"
                line_content = tab.text_area.get(line_start, f"{line_num}.end")
                if line_content.strip().startswith(comment_char):
                    # Uncomment
                    match = re.search(re.escape(comment_char), line_content)
                    if match:
                        tab.text_area.delete(f"{line_num}.{match.start()}", f"{line_num}.{match.start() + len(comment_char)}")
                else:
                    # Comment
                    tab.text_area.insert(line_start, comment_char)
        except Exception as e:
            logger.error(f"Toggle comment error: {e}")
        return "break"

    def current_tab(self):
        try:
            tab_id = self.notebook.select()
            return self.notebook.nametowidget(tab_id)
        except Exception:
            return None

    def new_file(self):
        tab = EditorTab(self.notebook, self)
        self.notebook.add(tab, text=tab.title)
        self.notebook.select(tab)

    def open_file(self, file_path=None):
        if not file_path:
            file_path = filedialog.askopenfilename()

        if file_path:
            # Check if already open
            for slave in self.notebook.winfo_children():
                if isinstance(slave, EditorTab) and slave.file_path == file_path:
                    self.notebook.select(slave)
                    return

            tab = EditorTab(self.notebook, self, file_path=file_path)
            self.notebook.add(tab, text=tab.title)
            self.notebook.select(tab)
            self.add_recent_file(file_path)

    def save_file(self):
        tab = self.current_tab()
        if tab:
            if tab.save_file():
                self.add_recent_file(tab.file_path)

    def save_as(self):
        tab = self.current_tab()
        if tab:
            if tab.save_file(file_path=None):
                self.add_recent_file(tab.file_path)

    def update_tab_title(self, tab):
        title = tab.title
        if tab.content_modified:
            title += "*"
        self.notebook.tab(tab, text=title)

    def on_tab_changed(self, event):
        tab = self.current_tab()
        if tab:
            self.update_status()

    def update_status(self):
        tab = self.current_tab()
        if tab:
            pos = tab.text_area.index(tk.INSERT)
            line, col = pos.split(".")
            self.cursor_label.config(text=f"行: {line}, 列: {col}")

            ext = os.path.splitext(tab.file_path)[1] if tab.file_path else "纯文本"
            self.status_label.config(text=f"文件类型: {ext or 'None'}")

    def schedule_highlight(self, tab):
        if self.highlight_timer:
            self.root.after_cancel(self.highlight_timer)
        self.highlight_timer = self.root.after(300, lambda: self.apply_highlighting(tab))

    def apply_highlighting(self, tab):
        text = tab.text_area.get(1.0, tk.END)
        filename = tab.file_path or "file.txt"

        try:
            lexer = get_lexer_for_filename(filename)
        except ClassNotFound:
            try:
                lexer = guess_lexer(text)
            except ClassNotFound:
                return

        # Simple highlighting implementation using Pygments tokens
        tab.text_area.mark_set("range_start", "1.0")

        # Clear existing tags (except search ones)
        for tag in tab.text_area.tag_names():
            if tag not in ("found", "match"):
                tab.text_area.tag_remove(tag, "1.0", tk.END)

        # Optimization: only highlight visible part or use a faster way
        # For now, let's do a simple one
        tokens = lexer.get_tokens(text)

        line = 1
        column = 0

        # Map pygments tokens to tags
        # Token.Keyword, Token.Name, Token.String, Token.Comment, etc.
        for ttype, value in tokens:
            tag_name = str(ttype)

            if tag_name not in tab.text_area.tag_names():
                # Define colors based on theme
                color = self.get_token_color(ttype)
                tab.text_area.tag_configure(tag_name, foreground=color)

            end_column = column + len(value)

            # Multi-line handling
            if '\n' in value:
                lines = value.split('\n')
                # First line
                if lines[0]:
                    tab.text_area.tag_add(tag_name, f"{line}.{column}", f"{line}.{column + len(lines[0])}")

                for i in range(1, len(lines)):
                    line += 1
                    column = 0
                    if lines[i]:
                        tab.text_area.tag_add(tag_name, f"{line}.{column}", f"{line}.{column + len(lines[i])}")
                column = len(lines[-1])
            else:
                tab.text_area.tag_add(tag_name, f"{line}.{column}", f"{line}.{end_column}")
                column = end_column

    def get_token_color(self, ttype):
        # Basic mapping for light theme
        colors = {
            'Token.Keyword': '#0000FF',
            'Token.Name.Function': '#008000',
            'Token.Name.Class': '#008000',
            'Token.String': '#A31515',
            'Token.Comment': '#008000',
            'Token.Number': '#098658',
            'Token.Operator': '#000000',
        }
        if self.theme_var.get() == "dark":
            colors = {
                'Token.Keyword': '#569CD6',
                'Token.Name.Function': '#DCDCAA',
                'Token.Name.Class': '#4EC9B0',
                'Token.String': '#CE9178',
                'Token.Comment': '#6A9955',
                'Token.Number': '#B5CEA8',
                'Token.Operator': '#D4D4D4',
            }

        for k, v in colors.items():
            if k in str(ttype):
                return v
        return "#000000" if self.theme_var.get() == "light" else "#D4D4D4"

    def toggle_word_wrap(self):
        wrap_mode = tk.WORD if self.word_wrap.get() else tk.NONE
        for slave in self.notebook.winfo_children():
            if isinstance(slave, EditorTab):
                slave.text_area.config(wrap=wrap_mode)

    def apply_theme(self):
        theme = self.theme_var.get()
        if theme == "dark":
            bg, fg, insert = "#1E1E1E", "#D4D4D4", "white"
        else:
            bg, fg, insert = "white", "black", "black"

        for slave in self.notebook.winfo_children():
            if isinstance(slave, EditorTab):
                slave.text_area.config(bg=bg, fg=fg, insertbackground=insert)
                slave.linenumbers.config(bg=bg)
                self.apply_highlighting(slave)

    def show_find_replace(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("查找与替换")
        dialog.geometry("400x150")

        ttk.Label(dialog, text="查找:").grid(row=0, column=0, padx=5, pady=5)
        find_entry = ttk.Entry(dialog, width=30)
        find_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="替换为:").grid(row=1, column=0, padx=5, pady=5)
        replace_entry = ttk.Entry(dialog, width=30)
        replace_entry.grid(row=1, column=1, padx=5, pady=5)

        use_regex = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="正则表达式", variable=use_regex).grid(row=2, column=1, sticky=tk.W)

        def find_next():
            tab = self.current_tab()
            if not tab: return

            search_str = find_entry.get()
            tab.text_area.tag_remove("match", "1.0", tk.END)

            start_pos = tab.text_area.index(tk.INSERT)
            pos = tab.text_area.search(search_str, start_pos, stopindex=tk.END, regexp=use_regex.get())
            if not pos:
                pos = tab.text_area.search(search_str, "1.0", stopindex=start_pos, regexp=use_regex.get())

            if pos:
                # For regex, we need the actual matched length
                if use_regex.get():
                    match_obj = re.search(search_str, tab.text_area.get(pos, f"{pos} lineend"))
                    length = len(match_obj.group(0)) if match_obj else len(search_str)
                else:
                    length = len(search_str)

                end_pos = f"{pos}+{length}c"
                tab.text_area.tag_add("match", pos, end_pos)
                tab.text_area.mark_set(tk.INSERT, end_pos)
                tab.text_area.see(pos)

        def replace_all():
            tab = self.current_tab()
            if not tab: return

            search_str = find_entry.get()
            replace_str = replace_entry.get()

            content = tab.text_area.get(1.0, tk.END)
            if use_regex.get():
                new_content = re.sub(search_str, replace_str, content)
            else:
                new_content = content.replace(search_str, replace_str)

            tab.text_area.delete(1.0, tk.END)
            tab.text_area.insert(1.0, new_content)

        ttk.Button(dialog, text="查找下一个", command=find_next).grid(row=3, column=0, padx=5, pady=5)
        ttk.Button(dialog, text="全部替换", command=replace_all).grid(row=3, column=1, padx=5, pady=5)

    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        for f in files:
            self.open_file(f)

    def add_recent_file(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:10]
        self.update_recent_menu()
        self.save_config()

    def update_recent_menu(self):
        self.recent_menu.delete(0, tk.END)
        for f in self.recent_files:
            self.recent_menu.add_command(label=f, command=lambda path=f: self.open_file(path))

    def load_config(self):
        config_path = os.path.join(current_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.recent_files = config.get("recent_files", [])
            except: pass

    def save_config(self):
        config_path = os.path.join(current_dir, "config.json")
        try:
            with open(config_path, 'w') as f:
                json.dump({"recent_files": self.recent_files}, f)
        except: pass

    def archive_current(self):
        tab = self.current_tab()
        if not tab or not tab.file_path:
            messagebox.showwarning("警告", "请先保存文件后再进行压缩。")
            return

        dest = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP Archive", "*.zip")])
        if dest:
            success, msg = ArchiveManager.compress(tab.file_path, dest)
            if success:
                messagebox.showinfo("完成", msg)
            else:
                messagebox.showerror("错误", msg)

    def delete_current(self):
        tab = self.current_tab()
        if not tab or not tab.file_path:
            messagebox.showwarning("警告", "当前无打开的文件。")
            return

        if messagebox.askyesno("删除文件", f"确定要彻底删除文件 {tab.file_path} 吗？"):
            try:
                os.remove(tab.file_path)
                self.notebook.forget(tab)
                messagebox.showinfo("完成", "文件已删除。")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {e}")

    def on_exit(self):
        unsaved = False
        for slave in self.notebook.winfo_children():
            if isinstance(slave, EditorTab) and slave.content_modified:
                unsaved = True
                break

        if unsaved:
            if messagebox.askyesno("退出", "有未保存的内容，确定要退出吗？"):
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    app = TextEditor(root)

    # Handle CLI args
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if os.path.isfile(arg):
                app.open_file(arg)

    root.mainloop()
