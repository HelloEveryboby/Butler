import os
import sys
import json
import socket
import threading
import subprocess
import logging
import time

logger = logging.getLogger("AISubtitles")

# Constants
UDP_HOST = "127.0.0.1"
UDP_PORT = 50008
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_context = None
_subtitle_engine = None

class SubtitleEngine:
    """Core subtitle processing & translation state manager."""
    def __init__(self):
        self.is_running = False
        self.source_lang = "auto"
        self.target_lang = "zh"
        self.show_bilingual = True
        self.active_stream_thread = None

    def start_stream(self, callback):
        """Starts real-time subtitle stream emitting simulated or live ASR + translation chunks."""
        if self.is_running:
            return
        self.is_running = True
        self.active_stream_thread = threading.Thread(target=self._stream_loop, args=(callback,), daemon=True)
        self.active_stream_thread.start()

    def stop_stream(self):
        self.is_running = False

    def _stream_loop(self, callback):
        # Demo subtitle phrases for testing and simulation
        phrases = [
            ("Welcome to Butler AI Desktop Assistant.", "欢迎使用 Butler AI 桌面智能助手。"),
            ("Real-time AI subtitles and stream translation are now active.", "实时 AI 字幕与流式翻译现已激活。"),
            ("Designed with modern frosted glass and liquid glass aesthetic.", "专为现代毛玻璃与液态玻璃美学风格打造。"),
            ("You can customize font size, opacity, and bilingual display.", "您可以自定义字号大小、透明度以及双语对照显示。"),
            ("Butler seamless integration provides high accuracy and low latency.", "Butler 无缝集成提供了高精度和低延迟表现。")
        ]
        idx = 0
        while self.is_running:
            original, translated = phrases[idx % len(phrases)]
            # First send partial original
            words = original.split(" ")
            partial_orig = ""
            for i, word in enumerate(words):
                if not self.is_running:
                    break
                partial_orig += (" " if partial_orig else "") + word
                callback({
                    "type": "subtitle_partial",
                    "original": partial_orig,
                    "translated": translated[:int(len(translated) * ((i + 1) / len(words)))],
                    "is_final": False
                })
                time.sleep(0.3)

            if self.is_running:
                callback({
                    "type": "subtitle_final",
                    "original": original,
                    "translated": translated,
                    "is_final": True
                })
                idx += 1
                time.sleep(2.5)

_subtitle_engine = SubtitleEngine()

def send_udp_event(payload):
    """Sends JSON event to UDP port 50008."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = json.dumps(payload).encode("utf-8")
        sock.sendto(msg, (UDP_HOST, UDP_PORT))
        sock.close()
    except Exception as e:
        logger.debug(f"Failed to send UDP event: {e}")

def initialize_core(context) -> None:
    """Hook called by Butler SkillManager upon system initialization."""
    global _context
    _context = context
    logger.info("AI Subtitles core plugin initialized.")

def handle_request(action: str, **kwargs):
    """Execution handler for AI Subtitles skill."""
    if action in ("open", "launch", "start"):
        try:
            entry_script = os.path.join(SKILL_DIR, "main.py")
            subprocess.Popen([sys.executable, entry_script, str(os.getpid())], cwd=SKILL_DIR, start_new_session=True)
            return {"status": "success", "message": "AI 字幕悬浮窗已成功启动"}
        except Exception as e:
            return {"status": "error", "message": f"启动字幕悬浮窗失败: {e}"}
    elif action == "push_subtitle":
        orig = kwargs.get("original", "")
        trans = kwargs.get("translated", "")
        is_final = kwargs.get("is_final", True)
        send_udp_event({
            "type": "subtitle_final" if is_final else "subtitle_partial",
            "original": orig,
            "translated": trans,
            "is_final": is_final
        })
        return {"status": "success"}

    return {"status": "ok", "message": "AI Subtitles service active."}

# --- UI Subprocess Code ---

class SubtitleAPI:
    """JavaScript API exposed to pywebview window."""
    def __init__(self):
        self.window = None
        self.engine = _subtitle_engine

    def toggle_stream(self, enable):
        """Starts or stops subtitle stream generation."""
        if enable:
            def on_subtitle(data):
                send_udp_event(data)
            self.engine.start_stream(on_subtitle)
        else:
            self.engine.stop_stream()
        return {"status": "success", "is_running": self.engine.is_running}

    def resize_window(self, width, height):
        if self.window:
            try:
                self.window.resize(width, height)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Window not ready"}

    def set_click_through(self, pass_through):
        """Toggles click-through / mouse interactivity if supported."""
        return {"status": "success", "pass_through": pass_through}

def start_udp_listener(window):
    """UDP event receiver in UI subprocess."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((UDP_HOST, UDP_PORT))
    except Exception as e:
        logger.error(f"Failed to bind UDP listener on {UDP_PORT}: {e}")
        return

    logger.info(f"AI Subtitles UDP bound to {UDP_HOST}:{UDP_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(8192)
            if not data:
                continue
            payload = json.loads(data.decode("utf-8"))
            js_code = f"if (window.ButlerSubtitles) {{ window.ButlerSubtitles.onEvent({json.dumps(payload)}); }}"
            window.evaluate_js(js_code)
        except Exception as e:
            logger.error(f"Error in subtitle UDP listener: {e}")
            time.sleep(1)

def run_ui(parent_pid=None):
    """Builds and launches PyWebview floating glass subtitle window."""
    import webview

    html_path = os.path.join(SKILL_DIR, "ui", "index.html")
    if not os.path.exists(html_path):
        logger.error(f"Subtitle HTML not found at: {html_path}")
        return

    # Default floating subtitle bar dimensions
    w_width = 720
    w_height = 180

    api = SubtitleAPI()

    window = webview.create_window(
        title="Butler AI Subtitles",
        url=f"file://{html_path}",
        transparent=True,
        frameless=True,
        on_top=True,
        background_color='#000000',
        width=w_width,
        height=w_height,
        js_api=api
    )
    api.window = window

    # Start UDP receiver thread
    udp_thread = threading.Thread(target=start_udp_listener, args=(window,), daemon=True)
    udp_thread.start()

    # Start parent process monitor
    if parent_pid is not None:
        def monitor_parent():
            import ctypes
            while True:
                time.sleep(1.0)
                alive = False
                try:
                    if sys.platform == "win32":
                        kernel32 = ctypes.windll.kernel32
                        handle = kernel32.OpenProcess(0x0400, False, parent_pid)
                        if handle:
                            kernel32.CloseHandle(handle)
                            alive = True
                    else:
                        os.kill(parent_pid, 0)
                        alive = True
                except Exception:
                    alive = False

                if not alive:
                    logger.warning(f"Parent process {parent_pid} terminated. Exiting AI Subtitles...")
                    try:
                        window.destroy()
                    except Exception:
                        pass
                    os._exit(0)

        monitor_thread = threading.Thread(target=monitor_parent, daemon=True)
        monitor_thread.start()

    # Position centered near bottom of primary screen
    def on_loaded():
        try:
            screens = webview.screens
            if screens:
                primary = screens[0]
                pos_x = max(20, (primary.width - w_width) // 2)
                pos_y = primary.height - w_height - 80
                window.move(pos_x, pos_y)
        except Exception as e:
            logger.error(f"Failed positioning subtitle window: {e}")

    window.events.loaded += on_loaded

    # Auto start subtitle simulation loop when standalone
    def auto_start():
        time.sleep(1)
        api.toggle_stream(True)

    threading.Thread(target=auto_start, daemon=True).start()

    webview.start(debug=True)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parent_pid = None
    if len(sys.argv) > 1:
        try:
            parent_pid = int(sys.argv[1])
        except ValueError:
            pass
    run_ui(parent_pid=parent_pid)
