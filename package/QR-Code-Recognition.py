"""
二维码识别工具。支持通过摄像头或屏幕截图识别二维码，并处理其中的 URL（如打开网页或下载文件）。
"""
import cv2
import requests
import os
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from threading import Thread, Lock
import time
import queue
import logging
import numpy as np
import pyautogui
import pygetwindow as gw
from PIL import ImageGrab, Image
import mss
import mss.tools

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("qr_scanner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("QRScanner")

# 设置默认保存路径
DEFAULT_SAVE_FOLDER = "./my_package/downloaded"
if not os.path.exists(DEFAULT_SAVE_FOLDER):
    os.makedirs(DEFAULT_SAVE_FOLDER)

# 全局锁用于线程安全
camera_lock = Lock()
action_queue = queue.Queue()

def select_save_folder(default_save_folder):
    """选择文件保存目录"""
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(
        initialdir=default_save_folder, 
        title="选择保存文件夹"
    )
    root.destroy()
    return folder if folder else default_save_folder

def download_file(url, save_folder):
    """下载文件到指定目录"""
    try:
        # 创建安全文件名
        filename = os.path.basename(url.split('?')[0])
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        local_path = os.path.join(save_folder, safe_filename)
        
        logger.info(f"开始下载: {url} -> {local_path}")
        
        with requests.get(url, stream=True, timeout=10) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # 过滤空块
                        f.write(chunk)
        
        logger.info(f"文件下载完成: {local_path}")
        return True, local_path
    except requests.RequestException as e:
        logger.error(f"下载失败: {e}")
        return False, str(e)

def open_url(url):
    """在浏览器中打开URL"""
    try:
        import webbrowser
        webbrowser.open(url)
        logger.info(f"已打开URL: {url}")
        return True
    except Exception as e:
        logger.error(f"打开URL失败: {e}")
        return False

def handle_actions():
    """处理动作队列中的请求"""
    while True:
        action, url, save_folder = action_queue.get()
        if action == "shutdown":
            break
            
        root = tk.Tk()
        root.withdraw()
        
        if action == "download":
            result = messagebox.askyesno(
                "下载确认", 
                f"您想从以下链接下载文件吗？\n{url}\n\n保存到: {save_folder}"
            )
            if result:
                success, message = download_file(url, save_folder)
                if success:
                    messagebox.showinfo("下载成功", f"文件已保存到:\n{message}")
                else:
                    messagebox.showerror("下载失败", f"下载失败: {message}")
        
        elif action == "open":
            result = messagebox.askyesno(
                "打开 URL 确认", 
                f"您想打开以下网址吗？\n{url}?"
            )
            if result:
                if open_url(url):
                    messagebox.showinfo("成功", "URL已在浏览器中打开")
                else:
                    messagebox.showerror("错误", "无法打开URL")
        
        root.destroy()
        action_queue.task_done()

def detect_and_handle_qr_code(image, save_folder, source="camera"):
    """检测图像中的二维码并处理结果"""
    try:
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(image)
        
        if bbox is not None and data:
            # 绘制二维码边界
            bbox = bbox[0].astype(int)
            for i in range(4):
                start_point = tuple(bbox[i])
                end_point = tuple(bbox[(i + 1) % 4])
                cv2.line(image, start_point, end_point, (0, 255, 0), 3)
            
            # 在图像上显示URL
            cv2.putText(
                image, data, (30, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            
            if data.startswith(('http://', 'https://')):
                logger.info(f"检测到URL({source}): {data}")
                action_queue.put(("download", data, save_folder))
                return True, data, image
            
        return False, None, image
    except Exception as e:
        logger.error(f"二维码检测错误: {e}")
        return False, None, image

def scan_qr_code_camera(save_folder):
    """使用摄像头扫描二维码"""
    try:
        with camera_lock:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logger.error("无法打开摄像头")
                return
            
            window_name = '摄像头扫描 - 按ESC退出'
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 800, 600)
            
            last_detection_time = 0
            detected_url = None
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("无法从摄像头获取帧")
                    time.sleep(0.1)
                    continue
                
                # 检测二维码
                detected, url, processed_frame = detect_and_handle_qr_code(
                    frame.copy(), save_folder, "camera"
                )
                
                current_time = time.time()
                if detected:
                    # 防止同一二维码连续触发
                    if url != detected_url or current_time - last_detection_time > 3:
                        detected_url = url
                        last_detection_time = current_time
                        frame = processed_frame
                        # 检测到二维码后暂停1秒
                        time.sleep(1)
                
                # 显示帧
                cv2.imshow(window_name, processed_frame if detected else frame)
                
                # 检查退出键 (ESC 或 'q')
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    break
                
                time.sleep(0.05)  # 减少CPU使用率
        
    except Exception as e:
        logger.exception("摄像头扫描时发生错误")
    finally:
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()

def scan_qr_code_screen(save_folder):
    """扫描屏幕上的二维码"""
    try:
        window_name = '屏幕扫描 - 按ESC退出'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)
        
        # 获取屏幕尺寸
        screen_width, screen_height = pyautogui.size()
        logger.info(f"屏幕尺寸: {screen_width}x{screen_height}")
        
        # 创建截图区域（整个屏幕）
        monitor = {"top": 0, "left": 0, "width": screen_width, "height": screen_height}
        
        last_detection_time = 0
        detected_url = None
        
        with mss.mss() as sct:
            while True:
                # 截取屏幕
                sct_img = sct.grab(monitor)
                
                # 转换为OpenCV格式
                img = np.array(sct_img)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # 检测二维码
                detected, url, processed_img = detect_and_handle_qr_code(
                    img.copy(), save_folder, "screen"
                )
                
                current_time = time.time()
                if detected:
                    # 防止同一二维码连续触发
                    if url != detected_url or current_time - last_detection_time > 3:
                        detected_url = url
                        last_detection_time = current_time
                        img = processed_img
                        # 检测到二维码后暂停1秒
                        time.sleep(1)
                
                # 显示帧
                cv2.imshow(window_name, processed_img if detected else img)
                
                # 检查退出键 (ESC 或 'q')
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    break
                
                time.sleep(0.3)  # 降低扫描频率
                
    except Exception as e:
        logger.exception("屏幕扫描时发生错误")
    finally:
        cv2.destroyAllWindows()

def on_exit(root):
    """处理程序退出"""
    if messagebox.askokcancel("退出确认", "您确定要退出程序吗？"):
        # 通知动作处理线程关闭
        action_queue.put(("shutdown", "", ""))
        root.quit()

class QRScannerApp:
    """二维码扫描器应用程序"""
    def __init__(self, root):
        self.root = root
        self.root.title("多功能二维码扫描器")
        self.root.geometry("500x300")
        self.root.resizable(True, True)
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 模式选择
        mode_frame = ttk.LabelFrame(main_frame, text="扫描模式", padding=10)
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.scan_mode = tk.StringVar(value="camera")
        
        ttk.Radiobutton(
            mode_frame, text="摄像头扫描", 
            variable=self.scan_mode, value="camera"
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Radiobutton(
            mode_frame, text="屏幕扫描", 
            variable=self.scan_mode, value="screen"
        ).pack(side=tk.LEFT, padx=10)
        
        # 保存路径
        path_frame = ttk.LabelFrame(main_frame, text="保存设置", padding=10)
        path_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.save_folder = tk.StringVar(value=DEFAULT_SAVE_FOLDER)
        
        ttk.Label(path_frame, text="下载路径:").pack(side=tk.LEFT)
        ttk.Entry(path_frame, textvariable=self.save_folder, width=40).pack(
            side=tk.LEFT, padx=(5, 10), fill=tk.X, expand=True
        )
        
        ttk.Button(
            path_frame, text="更改", 
            command=self.change_save_folder
        ).pack(side=tk.RIGHT)
        
        # 状态区域
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(
            status_frame, textvariable=self.status_var,
            foreground="blue", font=("Arial", 10)
        ).pack(side=tk.LEFT)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        ttk.Button(
            button_frame, text="开始扫描", 
            command=self.start_scan, width=15
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, text="退出程序", 
            command=lambda: on_exit(root), width=15
        ).pack(side=tk.RIGHT)
        
        # 启动动作处理线程
        Thread(target=handle_actions, daemon=True).start()
    
    def change_save_folder(self):
        """更改保存文件夹"""
        folder = filedialog.askdirectory(
            initialdir=self.save_folder.get(),
            title="选择保存文件夹"
        )
        if folder:
            self.save_folder.set(folder)
            self.status_var.set(f"保存路径已更新: {folder}")
    
    def start_scan(self):
        """开始扫描"""
        save_folder = self.save_folder.get()
        mode = self.scan_mode.get()
        
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
        
        if mode == "camera":
            self.status_var.set("正在启动摄像头扫描...")
            Thread(target=scan_qr_code_camera, args=(save_folder,), daemon=True).start()
        else:
            self.status_var.set("正在扫描屏幕内容...")
            Thread(target=scan_qr_code_screen, args=(save_folder,), daemon=True).start()

def run(**kwargs):
    """
    运行二维码识别工具。
    """
    root = tk.Tk()
    app = QRScannerApp(root)
    
    root.protocol("WM_DELETE_WINDOW", lambda: on_exit(root))
    root.mainloop()

def main():
    run()

if __name__ == "__main__":
    run()
