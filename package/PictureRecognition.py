import tkinter as tk
from tkinter import filedialog, messagebox
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import base64
from package.log_manager import LogManager

"""
图片识别与搜索工具。通过上传本地图片到搜索引擎（如 Bing）来获取相关的识别信息、描述及相似图片。
"""
logger = LogManager.get_logger(__name__)

def run(**kwargs):
    logger.info("PictureRecognition tool started")
    # 创建 Tkinter 窗口
    window = tk.Tk()
    window.title("图片搜索")

    # 创建输入框
    entry = tk.Entry(window)
    entry.pack()

    # 创建搜索按钮
    search_button = tk.Button(window, text="搜索", command=lambda: search_image(entry, result_label))
    search_button.pack()

    # 创建关闭按钮
    close_button = tk.Button(window, text="X", command=window.destroy)
    close_button.pack()

    # 创建结果显示标签
    result_label = tk.Label(window, text="")
    result_label.pack()

    # 设置拖放功能
    window.drop_target_register('DND_FILES')
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
    search_button.bind("<ButtonRelease-1>", lambda event: on_button_release(search_button))

    # 为关闭按钮添加点击效果
    close_button.bind("<Button-1>", lambda event: on_button_click(close_button))
    close_button.bind("<ButtonRelease-1>", lambda event: on_button_release(close_button))

    # 运行窗口
    window.mainloop()

# 使用 Bing 图片搜索 API
def search_image(entry, result_label):
    """
    使用 Bing 图片搜索 API 搜索图片相关信息。
    """
    try:
        image_path = entry.get()  # 获取输入框中的图片路径
        logger.info(f"Searching for image: {image_path}")

        if image_path:
            # 将图片转换为 Base64 编码
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
            encoded_image = base64.b64encode(image_data).decode("utf-8")

            # Bing 图片搜索 API 请求 URL
            api_url = "https://www.bing.com/images/search"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "TE": "trailers",
            }
            data = {
                "q": "imgurl:" + encoded_image,
                "form": "HDRSC2",
            }

            # 发送请求
            response = requests.post(api_url, headers=headers, data=data)
            response.raise_for_status()  # 检查请求是否成功
            logger.info(f"Bing search returned status code: {response.status_code}")

            # 解析搜索结果页面
            soup = BeautifulSoup(response.content, "html.parser")

            # 提取搜索结果信息
            results = {
                "url": response.url,
                "title": soup.find("title").text if soup.find("title") else "No title",
                "description": soup.find("meta", attrs={"name": "description"}).get("content") if soup.find("meta", attrs={"name": "description"}) else "No description",
                "images": [img.get("src") for img in soup.find_all("img", attrs={"src": True})],
            }
            logger.info(f"Found {len(results['images'])} images.")

            # 在GUI中显示搜索结果
            result_label.config(text=f"URL: {results['url']}\nTitle: {results['title']}\nDescription: {results['description']}\nImages: {', '.join(results['images'])}")

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
