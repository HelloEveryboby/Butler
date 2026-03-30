import tkinter as tk
from tkinter import messagebox, filedialog
import os
from package.core_utils.log_manager import LogManager
from package.network.image_search_tool import ImageSearchTool

logger = LogManager.get_logger(__name__)


def run(*args, **kwargs):
    logger.info("PictureRecognition tool started")
    # 创建 Tkinter 窗口
    window = tk.Tk()
    window.title("图片搜索")

    # 创建输入框
    entry = tk.Entry(window)
    entry.pack()

    # 创建搜索按钮
    search_button = tk.Button(
        window, text="搜索", command=lambda: search_image(entry, result_label)
    )
    search_button.pack()

    # 创建本地文件夹搜索按钮
    local_search_button = tk.Button(
        window, text="搜索文件夹", command=lambda: search_folder(entry, result_label)
    )
    local_search_button.pack()

    # 创建关闭按钮
    close_button = tk.Button(window, text="X", command=window.destroy)
    close_button.pack()

    # 创建结果显示标签
    result_label = tk.Label(window, text="")
    result_label.pack()

    # 设置拖放功能
    window.drop_target_register("DND_FILES")
    window.dnd_bind("<<Drop>>", lambda event: drop(event, entry))

    # 添加按钮点击效果
    def on_button_click(button):
        """
        按钮点击效果函数。
        """
        button.config(relief=tk.SUNKEN)  # 设置按钮为凹陷状态

    def on_button_release(button):
        """
        按钮释放效果函数。
        """
        button.config(relief=tk.RAISED)  # 设置按钮为凸起状态

    # 为搜索按钮添加点击效果
    search_button.bind("<Button-1>", lambda event: on_button_click(search_button))
    search_button.bind(
        "<ButtonRelease-1>", lambda event: on_button_release(search_button)
    )

    # 为关闭按钮添加点击效果
    close_button.bind("<Button-1>", lambda event: on_button_click(close_button))
    close_button.bind(
        "<ButtonRelease-1>", lambda event: on_button_release(close_button)
    )

    # 运行窗口
    window.mainloop()


def search_folder(entry, result_label):
    """
    搜索本地文件夹中的图片。
    """
    try:
        folder_path = entry.get()
        if not folder_path or not os.path.isdir(folder_path):
            folder_path = filedialog.askdirectory()
            entry.delete(0, tk.END)
            entry.insert(0, folder_path)

        if folder_path:
            tool = ImageSearchTool()
            found = tool.search_local_images(folder_path)
            result_label.config(
                text=f"在文件夹中找到 {len(found)} 张图片:\n"
                + "\n".join([os.path.basename(f) for f in found[:10]])
            )
        else:
            messagebox.showwarning("Warning", "Please select a directory.")
    except Exception as e:
        logger.error(f"Error searching folder: {e}")
        messagebox.showerror("Error", str(e))


# 使用整合的图片搜索工具
def search_image(entry, result_label):
    """
    使用 ImageSearchTool 搜索图片相关信息。
    """
    try:
        input_val = entry.get()
        logger.info(f"Searching for: {input_val}")

        if input_val:
            tool = ImageSearchTool()
            if os.path.exists(input_val):
                # 以图搜图
                res = tool.reverse_search(input_val)
                if res:
                    result_label.config(text=f"搜索结果页面: {res['results_url']}")
                else:
                    result_label.config(text="搜索失败")
            else:
                # 关键词搜图
                images = tool.search_by_text(input_val)
                if images:
                    result_label.config(
                        text=f"找到 {len(images)} 张图片:\n" + "\n".join(images[:5])
                    )
                else:
                    result_label.config(text="未找到相关图片")
        else:
            logger.warning("No image file selected.")
            messagebox.showwarning("Warning", "Please select an image file.")
    except Exception as e:
        logger.error(f"An error occurred during image search: {e}", exc_info=True)
        messagebox.showerror("Error", f"An error occurred: {e}")


# 处理拖放事件
def drop(event, entry):
    """
    处理拖放事件，获取拖放的图片路径。
    """
    file_path = event.data
    logger.info(f"Image dropped: {file_path}")
    entry.delete(0, tk.END)  # 清空输入框
    entry.insert(0, file_path)  # 在输入框中插入图片路径
