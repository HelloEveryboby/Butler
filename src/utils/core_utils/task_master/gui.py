import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .task import Task
from .task_manager import TaskManager
from .smart_splitter import SmartSplitter

class TaskMasterGUI(tk.Toplevel):
    """
    为任务大师模块提供一个完整的图形用户界面。
    """
    def __init__(self, master):
        super().__init__(master)
        self.title("Task Master - 任务大师")
        self.geometry("1000x650")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 初始化后端组件
        self.task_manager = TaskManager()
        self.smart_splitter = SmartSplitter()

        # 创建并布局所有UI组件
        self.create_widgets()
        # 将任务数据显示在UI上
        self.populate_task_tree()

    def create_widgets(self):
        """创建并配置窗口中的所有UI组件。"""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 左侧：任务树和操作按钮 ---
        left_pane = ttk.Frame(main_frame)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 任务树视图
        self.task_tree = ttk.Treeview(left_pane, columns=("status",), show="tree headings")
        self.task_tree.heading("#0", text="任务标题")
        self.task_tree.heading("status", text="状态")
        self.task_tree.column("#0", width=300)
        self.task_tree.column("status", width=80, anchor=tk.CENTER)
        self.task_tree.pack(fill=tk.BOTH, expand=True)
        self.task_tree.bind("<<TreeviewSelect>>", self.show_task_details)

        # 任务操作按钮
        button_frame = ttk.Frame(left_pane)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="添加主任务", command=self.add_task).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(button_frame, text="添加子任务", command=lambda: self.add_task(is_subtask=True)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(button_frame, text="编辑任务", command=self.edit_task).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(button_frame, text="删除任务", command=self.delete_task).pack(side=tk.LEFT, expand=True, fill=tk.X)

        # --- 右侧：详情、状态和智能分解 ---
        right_pane = ttk.Frame(main_frame)
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 任务详情区域
        details_frame = ttk.LabelFrame(right_pane, text="任务详情", padding="10")
        details_frame.pack(fill=tk.BOTH, expand=True)
        self.task_details_text = tk.Text(details_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.task_details_text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(details_frame, text="保存描述", command=self.save_task_description).pack(fill=tk.X, pady=(5, 0))

        # 状态更新区域
        status_frame = ttk.LabelFrame(right_pane, text="更新状态", padding="10")
        status_frame.pack(fill=tk.X, pady=10)
        self.status_var = tk.StringVar()
        status_options = ["todo", "in_progress", "done"]
        for status in status_options:
            ttk.Radiobutton(status_frame, text=status, variable=self.status_var, value=status, command=self.update_task_status).pack(side=tk.LEFT, expand=True)

        # 智能分解区域
        splitter_frame = ttk.LabelFrame(right_pane, text="智能分解任务", padding="10")
        splitter_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(splitter_frame, text="输入复杂任务:").pack(fill=tk.X)
        self.splitter_input = ttk.Entry(splitter_frame)
        self.splitter_input.pack(fill=tk.X, pady=(0, 5))

        self.splitter_mode = tk.StringVar(value="online")
        mode_frame = ttk.Frame(splitter_frame)
        mode_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Radiobutton(mode_frame, text="在线模式 (AI)", variable=self.splitter_mode, value="online").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="离线模式", variable=self.splitter_mode, value="offline").pack(side=tk.LEFT, padx=10)

        ttk.Button(splitter_frame, text="开始分解", command=self.run_smart_split).pack(fill=tk.X)

    def populate_task_tree(self, tasks=None, parent_item=""):
        """递归地将任务数据填充到树状视图中。"""
        if tasks is None:
            # 清空旧数据
            for item in self.task_tree.get_children():
                self.task_tree.delete(item)
            tasks = self.task_manager.get_all_tasks()

        for task in tasks:
            item = self.task_tree.insert(parent_item, tk.END, text=task.title, values=(task.status,), iid=task.id, open=True)
            if task.subtasks:
                self.populate_task_tree(task.subtasks, parent_item=item)

    def add_task(self, is_subtask=False):
        """处理添加新任务或子任务的逻辑。"""
        parent_id = None
        if is_subtask:
            selected_item = self.get_selected_item()
            if not selected_item:
                messagebox.showwarning("选择错误", "请先选择一个父任务。")
                return
            parent_id = selected_item

        title = simpledialog.askstring("输入", "请输入任务标题：", parent=self)
        if title:
            new_task = Task(title=title)
            self.task_manager.add_task(new_task, parent_id)
            self.populate_task_tree()

    def edit_task(self):
        """处理编辑选中任务的逻辑。"""
        task_id = self.get_selected_item()
        if not task_id:
            messagebox.showwarning("选择错误", "请先选择一个要编辑的任务。")
            return

        task = self.task_manager.find_task(task_id)
        new_title = simpledialog.askstring("编辑", "请输入新的任务标题：", initialvalue=task.title, parent=self)
        if new_title:
            self.task_manager.update_task(task_id, title=new_title)
            self.populate_task_tree()

    def delete_task(self):
        """处理删除选中任务的逻辑。"""
        task_id = self.get_selected_item()
        if not task_id:
            messagebox.showwarning("选择错误", "请先选择一个要删除的任务。")
            return

        if messagebox.askyesno("确认", "确定要删除这个任务及其所有子任务吗？"):
            self.task_manager.delete_task(task_id)
            self.populate_task_tree()
            self.task_details_text.config(state=tk.NORMAL)
            self.task_details_text.delete(1.0, tk.END)
            self.task_details_text.config(state=tk.DISABLED)


    def show_task_details(self, event=None):
        """当用户在树中选择一个任务时，显示其详细信息。"""
        task_id = self.get_selected_item()
        if not task_id:
            return

        task = self.task_manager.find_task(task_id)
        if task:
            self.task_details_text.config(state=tk.NORMAL)
            self.task_details_text.delete(1.0, tk.END)
            self.task_details_text.insert(tk.END, task.description)
            self.task_details_text.config(state=tk.NORMAL) # 允许编辑
            self.status_var.set(task.status)

    def save_task_description(self):
        """保存任务描述文本框中的内容。"""
        task_id = self.get_selected_item()
        if not task_id:
            messagebox.showwarning("选择错误", "请先选择一个任务。")
            return

        new_description = self.task_details_text.get(1.0, tk.END).strip()
        self.task_manager.update_task(task_id, description=new_description)
        messagebox.showinfo("成功", "任务描述已保存。")

    def update_task_status(self):
        """更新选中任务的状态。"""
        task_id = self.get_selected_item()
        if not task_id:
            messagebox.showwarning("选择错误", "请先选择一个任务以更新其状态。")
            return

        new_status = self.status_var.get()
        self.task_manager.update_task(task_id, status=new_status)
        self.populate_task_tree()

    def run_smart_split(self):
        """执行智能分解并显示结果。"""
        task_title = self.splitter_input.get()
        if not task_title:
            messagebox.showwarning("输入错误", "请输入要分解的任务。")
            return

        mode = self.splitter_mode.get()
        if mode == "online":
            subtasks = self.smart_splitter.split_task_online(task_title)
        else:
            subtasks = self.smart_splitter.split_task_offline(task_title)

        if subtasks and "错误：" in subtasks[0]:
            messagebox.showerror("分解失败", subtasks[0])
            return

        # 创建一个新的主任务，并将分解结果作为子任务添加
        main_task = Task(title=task_title)
        for sub_title in subtasks:
            main_task.add_subtask(Task(title=sub_title))

        self.task_manager.add_task(main_task)
        self.populate_task_tree()
        self.splitter_input.delete(0, tk.END) # 清空输入框

    def get_selected_item(self):
        """获取当前在树状视图中选中的项的ID。"""
        selection = self.task_tree.selection()
        return selection[0] if selection else None

    def on_close(self):
        """在关闭窗口时执行的操作。"""
        if messagebox.askokcancel("退出", "确定要关闭任务大师吗？"):
            self.destroy()