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


class TerminalTab(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.current_directory = os.getcwd()
        self.command_history = []
        self.history_index = -1

        # 创建命令输出区域
        self.output_area = tk.Text(self, wrap="word", bg="black", fg="white")
        self.output_area.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 5), pady=(5, 5))

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
                self.command_input.dnd_bind('<<Drop>>', self.on_file_drop)
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
            if command.startswith("cd"):
                try:
                    path = command.split(maxsplit=1)[1]
                    os.chdir(path)
                    self.current_directory = os.getcwd()
                    self.output_area.insert(tk.END, f"Changed directory to: {self.current_directory}\n")
                except IndexError:
                    self.output_area.insert(tk.END, "cd: missing operand\n")
                except FileNotFoundError:
                    self.output_area.insert(tk.END, f"cd: no such file or directory: {path}\n")
            elif command == "ls":
                try:
                    files = os.listdir(self.current_directory)
                    for file in files:
                        self.output_area.insert(tk.END, f"{file}\n")
                except Exception as e:
                    self.output_area.insert(tk.END, f"ls: {e}\n")
            # 处理其他命令
            else:
                if command.startswith("python"):
                    # 运行Python脚本
                    script_name = command.split(maxsplit=1)[1]
                    process = subprocess.Popen(["python", script_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.current_directory)
                elif command.startswith("gcc"):
                    # 编译并运行C程序
                    file_name = command.split()[1]
                    safe_file_name = shlex.quote(file_name)
                    # Using shell=True for complex command with &&, but ensuring safe filenames
                    process = subprocess.Popen(f"gcc {safe_file_name} -o {safe_file_name}.exe && ./{safe_file_name}.exe", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.current_directory)
                elif command.startswith("g++"):
                    # 编译并运行C++程序
                    file_name = command.split()[1]
                    safe_file_name = shlex.quote(file_name)
                    process = subprocess.Popen(f"g++ {safe_file_name} -o {safe_file_name}.exe && ./{safe_file_name}.exe", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.current_directory)
                elif command.startswith("go run"):
                    # 运行Go程序
                    script_name = command.split(maxsplit=2)[2]
                    process = subprocess.Popen(["go", "run", script_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.current_directory)
                elif command.startswith("javac"):
                    # 编译Java程序
                    file_name = command.split()[1]
                    safe_file_name = shlex.quote(file_name)
                    process = subprocess.Popen(f"javac {safe_file_name} && java {shlex.quote(file_name.split('.')[0])}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.current_directory)
                else:
                    # 默认使用shell运行命令
                    # 注意：由于这是终端模拟器，我们直接运行用户输入的整个命令字符串
                    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.current_directory)
            
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
        file_path = event.data.strip('{}')
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
        self.notebook.add(new_tab, text=f"Tab {len(self.notebook.tabs())+1}")


def run(*args, **kwargs):
    app = TerminalApp()
    app.mainloop()

if __name__ == "__main__":
    app = TerminalApp()
    app.mainloop()
