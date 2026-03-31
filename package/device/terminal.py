import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import os
import shlex

# try:
#     from tkinterdnd2 import DND_FILES, TkinterDnD
#     HAS_DND = True
# except ImportError:
HAS_DND = False
DND_FILES = None
TkinterDnD = None


class TerminalTab(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.current_directory = os.getcwd()
        self.command_history = []
        self.history_index = -1

        # 创建命令输出区域
        self.output_area = tk.Text(self, wrap="word", bg="black", fg="white")
        self.output_area.pack(
            side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 5), pady=(5, 5)
        )

        # 创建滚动条并将其链接到命令输出区域
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_area.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.output_area.yview)

        self.output_area.insert(tk.END, "Welcome to the Terminal!\n")

        # 创建命令输入区域
        self.command_input = tk.Entry(self, bg="black", fg="white")
        self.command_input.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=5, pady=5)
        self.command_input.bind("<Return>", self.run_command)
        self.command_input.bind("<Up>", self.show_previous_command)
        self.command_input.bind("<Down>", self.show_next_command)

        # 支持拖放文件
        if HAS_DND:
            try:
                self.command_input.drop_target_register(DND_FILES)
                self.command_input.dnd_bind("<<Drop>>", self.on_file_drop)
            except Exception:
                pass

        # 创建运行按钮
        self.run_button = tk.Button(self, text="Run", command=self.run_command)
        self.run_button.pack(side=tk.RIGHT, padx=5, pady=5)

    def run_command(self, event=None):
        command = self.command_input.get()
        if command.strip():
            self.output_area.insert(tk.END, f">>> {command}\n")
            self.command_history.append(command)
            self.history_index = len(self.command_history)
            threading.Thread(target=self.execute_command, args=(command,)).start()
            self.command_input.delete(0, tk.END)

    def show_previous_command(self, event):
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.command_input.delete(0, tk.END)
            self.command_input.insert(0, self.command_history[self.history_index])

    def show_next_command(self, event):
        if self.command_history and self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.command_input.delete(0, tk.END)
            self.command_input.insert(0, self.command_history[self.history_index])

    def execute_command(self, command):
        try:
            command_parts = shlex.split(command)
            if not command_parts:
                return

            if command_parts[0] == "cd":
                try:
                    path = command_parts[1]
                    os.chdir(path)
                    self.current_directory = os.getcwd()
                    self.output_area.insert(
                        tk.END, f"Changed directory to: {self.current_directory}\n"
                    )
                except IndexError:
                    self.output_area.insert(tk.END, "cd: missing operand\n")
                except FileNotFoundError:
                    self.output_area.insert(tk.END, "cd: no such file or directory\n")
            elif command_parts[0] == "ls":
                try:
                    files = os.listdir(self.current_directory)
                    for file in files:
                        self.output_area.insert(tk.END, f"{file}\n")
                except Exception as e:
                    self.output_area.insert(tk.END, f"ls: {e}\n")
            # 处理其他命令
            else:
                # For safety, we prefer using list-based Popen which avoids the shell
                # unless special shell characters are detected.
                shell_chars = {
                    "|",
                    "&",
                    ";",
                    "<",
                    ">",
                    "$",
                    "*",
                    "?",
                    "(",
                    ")",
                    "[",
                    "]",
                    "!",
                    "#",
                    "~",
                }
                has_shell_meta = any(char in command for char in shell_chars)

                if not has_shell_meta:
                    # Simple command, run directly
                    process = subprocess.Popen(
                        command_parts,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=self.current_directory,
                    )
                else:
                    # Complex command, use shell but with caution
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=self.current_directory,
                    )

                for line in process.stdout:
                    self.output_area.insert(tk.END, line)
                for line in process.stderr:
                    self.output_area.insert(tk.END, line)
                process.wait()
                self.output_area.insert(tk.END, "\n")
        except Exception as e:
            self.output_area.insert(tk.END, f"Error: {e}\n")
        self.output_area.see(tk.END)

    def on_file_drop(self, event):
        file_path = event.data.strip("{}")
        self.command_input.insert(tk.END, file_path)


class TerminalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        if HAS_DND:
            try:
                # Try to initialize DnD if available
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception:
                pass
        self.title("Terminal Panel")
        self.geometry("800x600")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill=tk.BOTH)

        # 创建第一个标签页
        self.add_terminal_tab()

        # 创建新标签页按钮
        self.new_tab_button = tk.Button(self, text="+", command=self.add_terminal_tab)
        self.new_tab_button.pack(side=tk.TOP, padx=5, pady=5)

    def add_terminal_tab(self):
        new_tab = TerminalTab(self.notebook)
        self.notebook.add(new_tab, text=f"Tab {len(self.notebook.tabs()) + 1}")


def run(*args, **kwargs):
    app = TerminalApp()
    app.mainloop()


if __name__ == "__main__":
    app = TerminalApp()
    app.mainloop()
