import os
import sys
import threading
import time
import webview
import json

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.butler_app import Jarvis
from package.core_utils.log_manager import LogManager
from butler.core.asset_loader import asset_loader

class ModernBridge:
    def __init__(self, jarvis, window):
        self.jarvis = jarvis
        self.window = window
        self.logger = LogManager.get_logger(__name__)
        self.terminal_process = None

    def handle_command(self, command):
        self.logger.info(f"Modern UI Command: {command}")
        if command == "/voice-toggle":
            self.toggle_voice()
            return
        if command.startswith("/editor "):
             content = command[8:]
             self.window.evaluate_js(f"window.openEditor({json.dumps(content)}, 'Draft.md')")
             return
        # Use a thread to avoid blocking the UI
        threading.Thread(target=self._run_command, args=(command,), daemon=True).start()

    def toggle_voice(self):
        if self.jarvis.voice_service.is_listening:
            self.jarvis.voice_service.stop_listening()
        else:
            self.jarvis.voice_service.start_listening()

    def _run_command(self, command):
        try:
            self.window.evaluate_js("window.onAIStreamStart()")

            # Override ui_print to send logs/blocks to Web UI during streaming
            original_ui_print = self.jarvis.ui_print
            def web_ui_print(message, tag='ai_response', response_id=None):
                payload = message
                if tag in ['code_block', 'data_table', 'chart']:
                    # Pass complex objects as JSON
                    pass
                self.window.evaluate_js(f"window.onAIStreamChunk({json.dumps(payload)})")

            self.jarvis.ui_print = web_ui_print

            # Execute command (which now returns a generator)
            response_gen = self.jarvis.handle_user_command(command)

            if response_gen:
                for chunk in response_gen:
                    self.window.evaluate_js(f"window.onAIStreamChunk({json.dumps(chunk)})")

            # Restore
            self.jarvis.ui_print = original_ui_print
            self.window.evaluate_js("window.onAIStreamEnd()")
        except Exception as e:
            self.logger.error(f"Error in ModernBridge: {e}")
            self.window.evaluate_js(f"window.onAIStreamChunk(' Error: {str(e)}')")
            self.window.evaluate_js("window.onAIStreamEnd()")

    def pause_output(self):
        # Implementation to pause/stop Jarvis interpreter
        self.logger.info("Pause requested")
        # For now, just a placeholder. Real implementation would signal the interpreter to stop.
        if hasattr(self.jarvis, 'interpreter'):
            self.jarvis.interpreter.stop_execution = True

    def start_terminal(self):
        if not self.terminal_process:
            from butler.core.hybrid_link import HybridLinkClient
            terminal_path = os.path.join(project_root, "programs/hybrid_terminal/terminal_service")

            # Check if it exists, if not, we might need to build it or it was built in previous step
            if not os.path.exists(terminal_path):
                 self.logger.error("Terminal service binary not found!")
                 return

            self.terminal_client = HybridLinkClient(
                executable_path=terminal_path,
                fallback_enabled=False
            )
            self.terminal_client.start()

            # Register callback for terminal output
            def on_event(event):
                if event.get("method") == "terminal_output":
                    output = event.get("params")
                    self.window.evaluate_js(f"window.onTerminalOutput({json.dumps(output)})")

            self.terminal_client.register_event_callback(on_event)
            self.terminal_client.call("start_terminal", {})

    def terminal_input(self, data):
        if hasattr(self, 'terminal_client'):
            self.terminal_client.call("write_input", {"data": data})

    def open_office(self, file_path):
        import os
        import platform
        if os.path.exists(file_path):
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':
                import subprocess
                subprocess.run(['open', file_path])
            else:
                import subprocess
                subprocess.run(['xdg-open', file_path])
            return True
        return False

    def save_editor_content(self, content, filename):
        save_path = os.path.join(project_root, "data", filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return save_path

def main():
    # Initialize Jarvis in headless mode (no Tkinter root)
    jarvis = Jarvis(root=None)

    # Load HTML via AssetLoader
    html_path = asset_loader.resolve_path("ui://index.html")

    window = webview.create_window(
        'Butler - Modern UI',
        url=html_path,
        width=1200,
        height=800,
        background_color='#1e1e1e'
    )

    bridge = ModernBridge(jarvis, window)
    window.expose(bridge)

    # Override voice service callback to update UI
    original_voice_callback = jarvis._on_voice_status_change
    def modern_voice_callback(is_listening):
        original_voice_callback(is_listening)
        window.evaluate_js(f"window.onVoiceStatusChange({str(is_listening).lower()})")

    jarvis._on_voice_status_change = modern_voice_callback

    # Start Jarvis core
    jarvis.main()

    webview.start(debug=True)

if __name__ == "__main__":
    main()
