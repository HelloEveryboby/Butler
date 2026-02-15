"""
网络工具。支持启动简单的 HTTP 服务器、执行 HTTP GET 请求以及上传文件到 FTP 服务器。
"""
import requests
from http.server import SimpleHTTPRequestHandler, HTTPServer
from ftplib import FTP
from package.log_manager import LogManager

# 配置日志记录
logging = LogManager.get_logger(__name__)

# HTTP 服务器
class CustomHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Hello, World!</h1></body></html>")
        logging.info("处理了一个 GET 请求")

def run_http_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, CustomHandler)
    logging.info(f"HTTP 服务器正在运行，端口: {port}")
    httpd.serve_forever()

# HTTP 客户端
def fetch_data(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            logging.info("成功获取数据")
            return response.text
        else:
            logging.error("请求失败，状态码: %s", response.status_code)
            return None
    except Exception as e:
        logging.error("发生错误: %s", str(e))
        return None

# FTP 客户端
def upload_file(ftp_server, username, password, file_to_upload):
    try:
        ftp = FTP(ftp_server)
        ftp.login(user=username, passwd=password)
        with open(file_to_upload, 'rb') as f:
            ftp.storbinary(f'STOR {file_to_upload}', f)
        ftp.quit()
        logging.info(f"文件 '{file_to_upload}' 上传成功.")
    except Exception as e:
        logging.error("FTP 上传失败: %s", str(e))

def run(**kwargs):
    """
    运行网络工具。
    """
    network()

# 主程序
def network():
    while True:
        print("\n请选择操作:")
        print("1. 启动 HTTP 服务器")
        print("2. 执行 HTTP 请求")
        print("3. 上传文件到 FTP 服务器")
        print("4. 退出")

        choice = input("输入选项 (1/2/3/4): ")

        if choice == '1':
            run_http_server()
        elif choice == '2':
            url = input("请输入要请求的 URL: ")
            data = fetch_data(url)
            if data:
                print("响应内容:", data)
        elif choice == '3':
            ftp_server = input("输入 FTP 服务器地址: ")
            username = input("输入用户名: ")
            password = input("输入密码: ")
            file_to_upload = input("输入要上传的文件名: ")
            upload_file(ftp_server, username, password, file_to_upload)
        elif choice == '4':
            break
        else:
            print("无效选项，请重试.")
