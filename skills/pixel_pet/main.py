import os
import sys
import json
import socket
import threading
import subprocess
import logging
import time

logger = logging.getLogger("PixelPet")

# Constants
UDP_HOST = "127.0.0.1"
UDP_PORT = 50007
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_context = None

def send_udp_event(payload):
    """Sends a JSON-encoded event over UDP to port 50007."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        message = json.dumps(payload).encode("utf-8")
        sock.sendto(message, (UDP_HOST, UDP_PORT))
        sock.close()
    except Exception as e:
        logger.debug(f"Failed to send UDP event: {e}")

class EventThrottler:
    """Throttles high-frequency streaming events to prevent UI and socket flooding."""
    def __init__(self, interval=0.1):
        self.interval = interval
        self.last_sent = 0.0
        self.lock = threading.Lock()
        self.pending_payload = None
        self.timer = None

    def throttle(self, payload):
        event_type = payload.get("event")
        if event_type != "ai_streaming":
            # Immediate send for non-streaming events, cancel pending timers
            with self.lock:
                if self.timer:
                    self.timer.cancel()
                    self.timer = None
                self.pending_payload = None
            send_udp_event(payload)
            return

        with self.lock:
            self.pending_payload = payload
            now = time.time()
            elapsed = now - self.last_sent
            if elapsed >= self.interval:
                self._send_pending()
            else:
                if self.timer is None:
                    remaining = self.interval - elapsed
                    self.timer = threading.Timer(remaining, self._timer_callback)
                    self.timer.start()

    def _timer_callback(self):
        with self.lock:
            self.timer = None
            self._send_pending()

    def _send_pending(self):
        if self.pending_payload:
            send_udp_event(self.pending_payload)
            self.pending_payload = None
            self.last_sent = time.time()

throttler = EventThrottler(interval=0.1)

def on_pet_event(payload):
    """Callback for global event_bus events."""
    throttler.throttle(payload)

def initialize_core(context) -> None:
    """
    Hook called by SkillManager upon load.
    Runs inside the main Butler process.
    """
    global _context
    _context = context
    logger.info("Pixel Pet core plugin successfully initialized in main process.")

    # 1. Subscribe to the global Python event bus
    _context.event_bus.subscribe("pet_event", on_pet_event)

    # 2. Spawn the transparent UI window in a separate Python subprocess to avoid webview thread lock conflicts.
    try:
        entry_script = os.path.join(SKILL_DIR, "main.py")
        subprocess.Popen([sys.executable, entry_script, str(os.getpid())], cwd=SKILL_DIR, start_new_session=True)
        logger.info("Pixel Pet UI subprocess spawned successfully.")
    except Exception as e:
        logger.error(f"Failed to spawn Pixel Pet UI subprocess: {e}")

def handle_request(action: str, **kwargs):
    """Fallback execution handler and API launcher."""
    if action == "trigger_state":
        event = kwargs.get("event", "ai_thinking")
        msg = kwargs.get("message", "Triggered via action")
        send_udp_event({"event": event, "message": msg})
        return {"status": "success", "message": f"State triggered: {event}"}
    elif action in ("open", "launch"):
        try:
            entry_script = os.path.join(SKILL_DIR, "main.py")
            subprocess.Popen([sys.executable, entry_script, str(os.getpid())], cwd=SKILL_DIR, start_new_session=True)
            return {"status": "success", "message": "电子宠物启动成功"}
        except Exception as e:
            return {"status": "error", "message": f"启动失败: {e}"}
    return {"status": "ok", "message": "Pixel Pet core skill is active."}


# --- UI Subprocess Code ---

class PetAPI:
    """Javascript API exposed to pywebview window."""
    def __init__(self):
        self.window = None

    def toggle_mode(self, is_panel):
        logger.info(f"toggle_mode called with is_panel={is_panel}")
        if not self.window:
            return {"status": "error", "message": "Window not initialized"}

        # Dimensions matching Scheme C
        w = 320 if is_panel else 90
        h = 520 if is_panel else 150

        try:
            import webview
            self.window.resize(w, h)
            # Re-position slightly to keep it in the bottom right corner of the screen
            screens = webview.screens
            if screens:
                primary = screens[0]
                pos_x = primary.width - w - 20
                pos_y = primary.height - h - 60
                self.window.move(pos_x, pos_y)
            return {"status": "success", "mode": "panel" if is_panel else "widget"}
        except Exception as e:
            logger.error(f"Failed to resize/move window: {e}")
            return {"status": "error", "message": str(e)}

def start_udp_listener(window):
    """Runs inside the UI subprocess to receive events and evaluate JS on the webview window."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((UDP_HOST, UDP_PORT))
    except Exception as e:
        logger.error(f"Failed to bind UDP listener on port {UDP_PORT}: {e}")
        return

    logger.info(f"UDP event listener bound to {UDP_HOST}:{UDP_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            if not data:
                continue
            payload = json.loads(data.decode("utf-8"))

            # Forward event to UI
            js_code = f"if (window.ButlerPet) {{ window.ButlerPet.onEvent({json.dumps(payload)}); }}"
            window.evaluate_js(js_code)
        except Exception as e:
            logger.error(f"Error in UDP receiver loop: {e}")
            time.sleep(1)

def run_ui(parent_pid=None):
    """Builds and runs the transparent PyWebview desktop window."""
    import webview

    html_path = os.path.join(SKILL_DIR, "ui", "index.html")
    if not os.path.exists(html_path):
        logger.error(f"HTML entrypoint not found at: {html_path}")
        return

    # Window sizes (Aesthetic Scheme C: default micro-width 90px, height 150px)
    w_width = 90
    w_height = 150

    api = PetAPI()

    # Create the window with zero background color, frameless and transparent settings
    window = webview.create_window(
        title="Butler Pixel Pet",
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

    # Start the UDP Listener background thread
    listener_thread = threading.Thread(target=start_udp_listener, args=(window,), daemon=True)
    listener_thread.start()

    # Start the Parent PID Survival Monitor daemon thread
    if parent_pid is not None:
        def monitor_parent():
            logger.info(f"Subprocess started with Parent PID Monitor for PID: {parent_pid}")
            import os
            import signal
            while True:
                time.sleep(1.0)
                # Check if parent is still alive
                alive = False
                try:
                    if sys.platform == "win32":
                        # Windows PID checking using tasklist or ctypes openprocess
                        import ctypes
                        kernel32 = ctypes.windll.kernel32
                        PROCESS_QUERY_INFORMATION = 0x0400
                        process_handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, parent_pid)
                        if process_handle:
                            # If we can query, it exists
                            kernel32.CloseHandle(process_handle)
                            alive = True
                    else:
                        # POSIX PID checking using kill(pid, 0)
                        os.kill(parent_pid, 0)
                        alive = True
                except Exception:
                    alive = False

                if not alive:
                    logger.warning(f"Parent process PID {parent_pid} has died. Self-terminating Subprocess...")
                    try:
                        window.destroy()
                    except Exception:
                        pass
                    # Hard exit to prevent any leaks
                    os._exit(0)

        monitor_thread = threading.Thread(target=monitor_parent, daemon=True)
        monitor_thread.start()

    # Move to bottom right corner once started
    def on_loaded():
        try:
            screens = webview.screens
            if screens:
                primary = screens[0]
                # Offset slightly from taskbars
                pos_x = primary.width - w_width - 20
                pos_y = primary.height - w_height - 60
                window.move(pos_x, pos_y)
        except Exception as e:
            logger.error(f"Failed to position window: {e}")

    window.events.loaded += on_loaded

    # Run PyWebview main thread blocking loop
    webview.start(debug=True)

if __name__ == '__main__':
    # Initialize basic logging for standalone execution
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parent_pid = None
    if len(sys.argv) > 1:
        try:
            parent_pid = int(sys.argv[1])
        except ValueError:
            pass

    run_ui(parent_pid=parent_pid)
