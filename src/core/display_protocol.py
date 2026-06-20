import socket
import threading
import json
import logging

logger = logging.getLogger("DisplayProtocol")

class SocketDisplayServer:
    """
    轻量级显示协议服务器 (P3)
    允许 ESP32 等独立硬件通过 Wi-Fi 获取渲染指令。
    """
    def __init__(self, host="0.0.0.0", port=9000):
        self.host = host
        self.port = port
        self.running = False
        self.clients = []

    def start(self):
        self.running = True
        thread = threading.Thread(target=self._run_server, daemon=True)
        thread.start()
        logger.info(f"Display Protocol Server started on {self.port}")

    def _run_server(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(5)

        while self.running:
            try:
                server_sock.settimeout(1.0)
                client, addr = server_sock.accept()
                self.clients.append(client)
                logger.info(f"Display client connected: {addr}")
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Display server error: {e}")
                break

    def push_update(self, data):
        """推送更新到所有副屏"""
        msg = json.dumps(data) + "\n"
        for client in self.clients[:]:
            try:
                client.sendall(msg.encode('utf-8'))
            except:
                self.clients.remove(client)

display_server = SocketDisplayServer()
