try:
    import tkinter as tk
    from tkinter import messagebox, filedialog
except ImportError:
    tk = None
    messagebox = filedialog = None

import os
from package.core_utils.log_manager import LogManager
from package.network.image_search_tool import ImageSearchTool

logger = LogManager.get_logger(__name__)

class PictureRecognition:
    """物体/图片识别与搜索工具类"""
    def __init__(self):
        self._tool = None

    @property
    def tool(self):
        if self._tool is None:
            self._tool = ImageSearchTool()
        return self._tool

    def search_image(self, query_or_path: str):
        if os.path.exists(query_or_path):
            return self.tool.reverse_search(query_or_path)
        return self.tool.search_by_text(query_or_path)

    def search_folder(self, folder_path: str):
        return self.tool.search_local_images(folder_path)

    def run(self, *args, **kwargs):
        run(*args, **kwargs)

def run(*args, **kwargs):
    if not tk:
        logger.error("Tkinter is not available in this environment.")
        return
    logger.info("PictureRecognition tool started")
    window = tk.Tk()
    window.title("图片搜索")

    entry = tk.Entry(window)
    entry.pack()

    search_button = tk.Button(window, text="搜索", command=lambda: search_image(entry, result_label))
    search_button.pack()

    local_search_button = tk.Button(window, text="搜索文件夹", command=lambda: search_folder(entry, result_label))
    local_search_button.pack()

    close_button = tk.Button(window, text="X", command=window.destroy)
    close_button.pack()

    result_label = tk.Label(window, text="")
    result_label.pack()

    if hasattr(window, 'drop_target_register'):
        window.drop_target_register('DND_FILES')
        window.dnd_bind("<<Drop>>", lambda event: drop(event, entry))

    def on_button_click(button):
        button.config(relief=tk.SUNKEN)

    def on_button_release(button):
        button.config(relief=tk.RAISED)

    search_button.bind("<Button-1>", lambda event: on_button_click(search_button))
    search_button.bind("<ButtonRelease-1>", lambda event: on_button_release(search_button))

    close_button.bind("<Button-1>", lambda event: on_button_click(close_button))
    close_button.bind("<ButtonRelease-1>", lambda event: on_button_release(close_button))

    window.mainloop()

def search_folder(entry, result_label):
    try:
        folder_path = entry.get()
        if not folder_path or not os.path.isdir(folder_path):
            if filedialog:
                folder_path = filedialog.askdirectory()
                entry.delete(0, tk.END)
                entry.insert(0, folder_path)

        if folder_path:
            tool = ImageSearchTool()
            found = tool.search_local_images(folder_path)
            result_label.config(text=f"在文件夹中找到 {len(found)} 张图片:\n" + "\n".join([os.path.basename(f) for f in found[:10]]))
        else:
            if messagebox:
                messagebox.showwarning("Warning", "Please select a directory.")
    except Exception as e:
        logger.error(f"Error searching folder: {e}")
        if messagebox:
            messagebox.showerror("Error", str(e))

def search_image(entry, result_label):
    try:
        input_val = entry.get()
        logger.info(f"Searching for: {input_val}")

        if input_val:
            tool = ImageSearchTool()
            if os.path.exists(input_val):
                res = tool.reverse_search(input_val)
                if res:
                    result_label.config(text=f"搜索结果页面: {res['results_url']}")
                else:
                    result_label.config(text="搜索失败")
            else:
                images = tool.search_by_text(input_val)
                if images:
                    result_label.config(text=f"找到 {len(images)} 张图片:\n" + "\n".join(images[:5]))
                else:
                    result_label.config(text="未找到相关图片")
        else:
            logger.warning("No image file selected.")
            if messagebox:
                messagebox.showwarning("Warning", "Please select an image file.")
    except Exception as e:
        logger.error(f"An error occurred during image search: {e}", exc_info=True)
        if messagebox:
            messagebox.showerror("Error", f"An error occurred: {e}")

def drop(event, entry):
    file_path = event.data
    logger.info(f"Image dropped: {file_path}")
    entry.delete(0, tk.END)
    entry.insert(0, file_path)
