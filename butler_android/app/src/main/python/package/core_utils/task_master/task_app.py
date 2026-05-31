from .gui import TaskMasterGUI

# 用于保存GUI窗口的引用，以防止打开多个实例
_task_master_window = None

def run():
    """
    Task Master 模块的入口点。
    Butler 主程序会调用此函数来启动我们的模块。
    """
    global _task_master_window

    # 如果窗口已经存在并且没有被关闭，则将其带到前台，而不是创建一个新窗口
    if _task_master_window and _task_master_window.winfo_exists():
        _task_master_window.lift()
        _task_master_window.focus_force()
        return

    # 创建GUI窗口。由于主程序已经有一个正在运行的Tk根窗口，
    # 我们创建的Toplevel窗口会自动附加到该根窗口上。
    _task_master_window = TaskMasterGUI(master=None)

    # 主程序已经在运行mainloop()，所以我们在这里不需要调用它。