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
from package.file_system.guard import FileSystemGuard
from package.file_system.migration_engine import SmartMigrationEngine
from package.device.hardware_manager import HardwareManager
from package.core_utils.task_master.progress_tracker import ProgressTracker
from butler.core.event_bus import event_bus
from butler.core.notifier_system import notifier

class ModernBridge:
    def __init__(self, jarvis, window):
        self.jarvis = jarvis
        self.window = window
        self.logger = LogManager.get_logger(__name__)
        self.terminal_process = None

        # Initialize components
        self.guard = FileSystemGuard()
        self.migration_engine = SmartMigrationEngine()
        self.hardware = HardwareManager() # Default to auto-detect later or config
        self.progress_tracker = ProgressTracker(self.hardware)

        # Subscribe to progress updates
        event_bus.subscribe("PROGRESS_UPDATE", self._on_progress_update)
        # Subscribe to notifications
        event_bus.subscribe("NOTIFICATION_PUSH", self._on_notification_push)
        event_bus.subscribe("NOTIFICATION_CLOSE", self._on_notification_close)

    def _on_progress_update(self, data):
        self.window.evaluate_js(f"window.onProgressSync({json.dumps(data)})")

    def _on_notification_push(self, event):
        self.window.evaluate_js(f"window.onNotificationPush({json.dumps(event)})")

    def _on_notification_close(self, data):
        self.window.evaluate_js(f"window.onNotificationClose({json.dumps(data)})")

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

            # We need to capture the output from Jarvis.
            # Jarvis usually prints to its panel. We'll override its ui_print momentarily or pass a custom one.
            original_ui_print = self.jarvis.ui_print

            def web_ui_print(message, tag='ai_response', response_id=None):
                if tag == 'status_update':
                     # Handle progress bars for Modern UI
                     try:
                         data = json.loads(message)
                         if data.get("type") == "progress":
                             self.window.evaluate_js(f"window.onProgressUpdate({data['value']})")
                     except:
                         pass
                elif tag == 'code_block':
                    self.window.evaluate_js(f"window.onAIStreamChunk({json.dumps(message)})")
                elif tag == 'data_table':
                    self.window.evaluate_js(f"window.onAIStreamChunk({json.dumps(message)})")
                elif tag == 'chart':
                    self.window.evaluate_js(f"window.onAIStreamChunk({json.dumps(message)})")
                elif tag == 'translation':
                    self.window.evaluate_js(f"window.onAIStreamChunk({json.dumps(message)})")
                elif tag != 'ai_response_start':
                    self.window.evaluate_js(f"window.onAIStreamChunk({json.dumps(message)})")

            self.jarvis.ui_print = web_ui_print

            # Execute command
            self.jarvis.handle_user_command(command)

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

    # --- New APIs for File Management ---
    def list_files(self, path="."):
        """Lists files with protection status."""
        try:
            full_path = os.path.join(project_root, path)
            items = os.listdir(full_path)
            result = []
            for item in items:
                item_path = os.path.join(path, item)
                is_protected = self.guard.is_protected(item_path)
                is_dir = os.path.isdir(os.path.join(full_path, item))
                result.append({
                    "name": item,
                    "path": item_path,
                    "is_protected": is_protected,
                    "is_dir": is_dir
                })
            return result
        except Exception as e:
            return {"error": str(e)}

    def delete_file(self, path):
        success, msg = self.guard.safe_delete(path)
        return {"success": success, "message": msg}

    def migrate_file(self, path, segment):
        success, msg = self.migration_engine.migrate_file(path, segment)
        return {"success": success, "message": msg}

    # --- Voice Engine APIs ---
    def set_voice_engine(self, engine_mode):
        return self.jarvis.voice_service.set_voice_mode(engine_mode)

    # --- New APIs for Volume & Hardware ---
    def set_volume(self, volume):
        self.hardware.set_volume(int(volume))
        return True

    def set_volume_mode(self, mode):
        self.hardware.set_volume_mode(mode)
        return True

    def set_volume_preset(self, level):
        self.hardware.set_preset(level)
        return True

    def get_hardware_status(self):
        return {
            "mode": self.hardware.volume_mode,
            "distance": self.hardware.env_distance,
            "freq": self.hardware.env_noise_freq
        }

    def get_media_library(self):
        """Fetches the media library using the media_manager skill."""
        try:
            return self.jarvis.skill_manager.execute("media_manager", "get_library")
        except Exception as e:
            self.logger.error(f"Failed to fetch media library: {e}")
            return []

    # --- Skills Management APIs ---
    def get_skills_list(self):
        """Returns a formatted list of skills or raw data."""
        try:
            # We reuse the backend logic we just implemented
            result = self.jarvis.skill_manager.execute("manage_skills", "list")
            # The list result is a markdown string. For UI, we might want to parse it or just return it.
            # Let's also provide a way to get raw status if needed, but for now, the report is fine.
            return result
        except Exception as e:
            return f"Error fetching skills: {str(e)}"

    def call_skill(self, skill_id, action, params=None):
        """Generic skill caller for frontend."""
        if params is None:
            params = {}
        try:
            return self.jarvis.skill_manager.execute(skill_id, action, **params)
        except Exception as e:
            self.logger.error(f"Skill call failed: {skill_id}.{action} - {e}")
            return {"error": str(e)}

    def install_skill(self, url, name=None):
        """Installs a skill from a URL."""
        try:
            return self.jarvis.skill_manager.execute("manage_skills", "install", url=url, skill_name=name)
        except Exception as e:
            return f"Error installing skill: {str(e)}"

    def uninstall_skill(self, name):
        """Uninstalls a skill by name."""
        try:
            return self.jarvis.skill_manager.execute("manage_skills", "uninstall", skill_name=name)
        except Exception as e:
            return f"Error uninstalling skill: {str(e)}"

    def get_quota_report(self):
        """Returns the current API quota usage report."""
        from package.core_utils.quota_manager import quota_manager
        report = quota_manager.get_usage_report()
        # Transform for the frontend renderQuotaInSettings function
        return {
            "items": [
                {
                    "name": "API 总额度 (RMB)",
                    "used": report["consumed"],
                    "total": report["limit"]
                }
            ]
        }

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

    # Listen for nostalgia mode event
    from butler.core.event_bus import event_bus
    def on_nostalgia():
        window.evaluate_js("window.onNostalgiaMode()")

    def on_theme_change(theme):
        window.evaluate_js(f"window.setTheme({json.dumps(theme)})")

    event_bus.subscribe("nostalgia_mode_activated", on_nostalgia)
    event_bus.subscribe("theme_change", on_theme_change)

    # Apply initial theme from config
    initial_theme = jarvis.config.get("display", {}).get("theme", "google")
    window.evaluate_js(f"window.setTheme({json.dumps(initial_theme)})")

    webview.start(debug=True)

if __name__ == "__main__":
    main()
