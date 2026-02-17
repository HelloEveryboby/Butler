import os
import logging
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class WebGateway:
    def __init__(self, jarvis_app):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'jarvis_secret')
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.jarvis = jarvis_app
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.socketio.on('connect')
        def handle_connect():
            logger.info("Web client connected")
            emit('system_message', {'message': 'Connected to Jarvis Brain'})

        @self.socketio.on('user_command')
        def handle_command(data):
            msg = data.get('message')
            if msg:
                logger.info(f"Received web command: {msg}")
                # 注入一个回调，以便将 AI 的回复传回 Web 端
                # 注意：Jarvis.handle_user_command 通常是异步的或通过线程处理
                # 这里我们假设 Jarvis 会调用 speak 或 ui_print，我们需要拦截它们
                self.jarvis.handle_user_command(msg)

    def notify_ai_response(self, text):
        """将 AI 的回复推送到所有连接的 Web 客户端。"""
        self.socketio.emit('ai_response', {'message': text})

    def start(self, host='0.0.0.0', port=5000):
        logger.info(f"Starting Web Gateway on {host}:{port}")
        # 使用 eventlet 作为服务器
        import eventlet
        import eventlet.wsgi
        eventlet.wsgi.server(eventlet.listen((host, port)), self.app)

def run_server(gateway):
    gateway.start()
