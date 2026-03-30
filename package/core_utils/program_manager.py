import os
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import winreg
except ImportError:
    winreg = None
from datetime import datetime
import locale
import threading


class ProgramManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Program Manager 3.0")
        self.root.geometry("900x650")

        # 设置中文显示
        locale.setlocale(locale.LC_ALL, "zh_CN")

        # 设置主题
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Treeview
        self.tree = ttk.Treeview(
            self.main_frame, columns=("name", "size", "install_date"), show="headings"
        )

        # 定义列
        self.tree.heading(
            "name", text="程序名称", command=lambda: self.sort_column("name", False)
        )
        self.tree.heading(
            "size", text="大小", command=lambda: self.sort_column("size", False)
        )
        self.tree.heading(
            "install_date",
            text="安装时间",
            command=lambda: self.sort_column("install_date", False),
        )

        # 设置列宽
        self.tree.column("name", width=400)
        self.tree.column("size", width=100)
        self.tree.column("install_date", width=150)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            self.main_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 布局
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 状态栏
        self.status_bar = ttk.Label(
            self.root, relief=tk.SUNKEN, anchor=tk.W, padding=(5, 2)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 添加控制按钮
        self.control_frame = ttk.Frame(self.root, padding="10")
        self.control_frame.pack(fill=tk.X)

        self.refresh_button = ttk.Button(
            self.control_frame, text="刷新列表", command=self.load_programs
        )
        self.refresh_button.pack(side=tk.LEFT, padx=5)

        self.delete_button = ttk.Button(
            self.control_frame,
            text="删除文件夹中的所有文件",
            command=self.on_delete_files,
        )
        self.delete_button.pack(side=tk.LEFT, padx=5)

        self.uninstall_button = ttk.Button(
            self.control_frame, text="卸载选定的软件", command=self.on_uninstall
        )
        self.uninstall_button.pack(side=tk.LEFT, padx=5)

        # 搜索框
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_search)
        self.search_entry = ttk.Entry(
            self.control_frame, textvariable=self.search_var, width=30
        )
        self.search_entry.pack(side=tk.RIGHT, padx=5)
        ttk.Label(self.control_frame, text="搜索:").pack(side=tk.RIGHT)

        # Jarvis控制
        self.jarvis_frame = ttk.Frame(self.root, padding="10")
        self.jarvis_frame.pack(fill=tk.X)

        self.jarvis = None

        self.voice_button = ttk.Button(
            self.jarvis_frame, text="语音控制", command=self.voice_control
        )
        self.voice_button.pack(side=tk.LEFT, padx=5)

        self.command_entry = ttk.Entry(self.jarvis_frame, width=50)
        self.command_entry.pack(side=tk.LEFT, padx=5)

        self.execute_button = ttk.Button(
            self.jarvis_frame, text="执行命令", command=self.execute_command
        )
        self.execute_button.pack(side=tk.LEFT, padx=5)

        # 加载程序数据
        self.load_programs()

    def get_program_size(self, path):
        """获取程序占用空间"""
        try:
            if os.path.exists(path):
                size = os.path.getsize(path)
                for unit in ["B", "KB", "MB", "GB"]:
                    if size < 1024:
                        return f"{size:.2f} {unit}"
                    size /= 1024
            return "未知"
        except Exception:
            return "未知"

    def get_install_date(self, key_path):
        """获取程序安装日期"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                key_path,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            install_date = winreg.QueryValueEx(key, "InstallDate")[0]
            winreg.CloseKey(key)
            date = datetime.strptime(str(install_date), "%Y%m%d")
            return date.strftime("%Y年%m月%d日")
        except Exception:
            return "未知"

    def load_programs(self):
        """加载已安装程序信息"""
        self.status_bar.config(text="正在加载程序列表...")
        self.refresh_button.config(state="disabled")

        def load():
            for item in self.tree.get_children():
                self.tree.delete(item)

            total_size = 0
            program_count = 0

            keys = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ]

            for key_path in keys:
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        key_path,
                        0,
                        winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                    )

                    subkey_count = winreg.QueryInfoKey(key)[0]

                    for i in range(subkey_count):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey_path = f"{key_path}\\{subkey_name}"
                            subkey = winreg.OpenKey(
                                winreg.HKEY_LOCAL_MACHINE,
                                subkey_path,
                                0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                            )

                            try:
                                program_name = winreg.QueryValueEx(
                                    subkey, "DisplayName"
                                )[0]
                                install_location = winreg.QueryValueEx(
                                    subkey, "InstallLocation"
                                )[0]

                                size = self.get_program_size(install_location)
                                if size != "未知":
                                    total_size += float(size.split()[0])

                                install_date = self.get_install_date(subkey_path)

                                self.tree.insert(
                                    "",
                                    tk.END,
                                    values=(program_name, size, install_date),
                                )
                                program_count += 1

                            except Exception:
                                continue

                            winreg.CloseKey(subkey)

                        except Exception:
                            continue

                    winreg.CloseKey(key)

                except Exception:
                    continue

            self.root.after(
                0,
                lambda: self.status_bar.config(
                    text=f"共计 {program_count} 个程序占用空间 {total_size:.2f} GB"
                ),
            )
            self.root.after(0, lambda: self.refresh_button.config(state="normal"))

        threading.Thread(target=load).start()

    def on_delete_files(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            confirm = messagebox.askyesno(
                "确认", f"确定要删除 {folder_path} 中的所有文件吗？"
            )
            if confirm:
                try:
                    for filename in os.listdir(folder_path):
                        file_path = os.path.join(folder_path, filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            print(f"Failed to delete {file_path}. Reason: {e}")
                    messagebox.showinfo("成功", f"{folder_path} 中的所有文件已删除。")
                except Exception as e:
                    messagebox.showerror("错误", f"删除文件时发生错误: {str(e)}")

    def on_uninstall(self):
        selected_items = self.tree.selection()
        if selected_items:
            programs = [self.tree.item(item, "values")[0] for item in selected_items]
            confirm = messagebox.askyesno(
                "确认", f"确定要卸载以下程序吗？\n{', '.join(programs)}"
            )
            if confirm:
                for item in selected_items:
                    program_name = self.tree.item(item, "values")[0]
                    try:
                        # Harden the wmic call by using a list and avoiding shell=True.
                        # We also ensure the program_name doesn't contain single quotes that could break the query.
                        safe_program_name = program_name.replace("'", "")
                        subprocess.run(
                            [
                                "wmic",
                                "product",
                                "where",
                                f"name='{safe_program_name}'",
                                "call",
                                "uninstall",
                                "/nointeractive",
                            ],
                            check=True,
                        )
                        self.tree.delete(item)
                    except subprocess.CalledProcessError:
                        messagebox.showerror("错误", f"卸载 {program_name} 时发生错误")
                messagebox.showinfo("成功", "选定的程序已被卸载。")
                self.load_programs()

    def sort_column(self, col, reverse):
        """排序表格列"""
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        l.sort(reverse=reverse)
        for index, (val, k) in enumerate(l):
            self.tree.move(k, "", index)
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def update_search(self, *args):
        """更新搜索结果"""
        search = self.search_var.get().lower()
        for item in self.tree.get_children():
            if search in self.tree.item(item)["values"][0].lower():
                self.tree.item(item, tags=("match",))
            else:
                self.tree.item(item, tags=("",))
        self.tree.tag_configure("match", background="yellow")

    def voice_control(self):
        """启动语音控制"""
        command = self.jarvis.takecommand()
        self.command_entry.delete(0, tk.END)
        self.command_entry.insert(0, command)
        self.execute_command()

    def execute_command(self):
        """执行Jarvis命令"""
        command = self.command_entry.get()
        if command:
            result = self.jarvis.execute(command)
            messagebox.showinfo("Jarvis执行结果", result)
        else:
            messagebox.showwarning("警告", "请输入命令")


def main():
    root = tk.Tk()
    app = ProgramManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()
