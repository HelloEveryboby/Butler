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

# Support portable/local dependency installation
lib_path = os.path.join(project_root, "lib_external")
if os.path.exists(lib_path):
    import site
    site.addsitedir(lib_path)

from butler.butler_app import Jarvis
from package.core_utils.log_manager import LogManager
from butler.core.asset_loader import asset_loader
from package.file_system.guard import FileSystemGuard
from package.file_system.migration_engine import SmartMigrationEngine
from package.device.hardware_manager import HardwareManager
from package.core_utils.task_master.progress_tracker import ProgressTracker
import keyboard
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
        # 记录词频
        try:
            from butler.core.memory.input_memory import input_memory
            for word in command.split():
                if len(word) > 1: # 仅记录长度大于 1 的词汇
                    input_memory.record_word(word)
        except Exception as e:
            self.logger.error(f"Failed to record input memory: {e}")

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
        from butler.core.window_registry import window_registry
        # 命令/程序执行期间，主界面对应的呼吸灯快闪
        bl_task = window_registry.bind_task(
            "win:main", threading.current_thread(), kind="thread", label=str(command)[:40])
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
                elif tag == 'focus_start':
                    self.window.evaluate_js(f"window.onFocusStart({json.dumps(message)})")
                elif tag == 'focus_stop':
                    self.window.evaluate_js(f"window.onFocusStop()")
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
        finally:
            window_registry.unbind_task("win:main", bl_task)

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
                    try:
                        from butler.core.window_registry import window_registry
                        window_registry.touch("view:terminal")
                    except Exception:
                        pass
                    self.window.evaluate_js(f"window.onTerminalOutput({json.dumps(output)})")

            self.terminal_client.register_event_callback(on_event)
            self.terminal_client.call("start_terminal", {})

    def terminal_input(self, data):
        # 终端有输入/输出 → 呼吸灯将"终端"子界面标记为活动（快闪）
        try:
            from butler.core.window_registry import window_registry
            window_registry.touch("view:terminal")
        except Exception:
            pass
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
        from butler.core.naming_policy import contains_cjk, make_unique_name
        from butler.core.alias_store import alias_store

        data_dir = os.path.join(project_root, "data")
        # 中文文件名 → 真实名保持英文/拼音，并登记中文显示名（别名层）
        if contains_cjk(filename):
            real_name = make_unique_name(data_dir, filename)
        else:
            real_name = filename
        save_path = os.path.join(data_dir, real_name)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)
        if real_name != filename:
            alias_store.set_alias(save_path, filename, created_by="auto")
        return save_path

    # --- New APIs for File Management ---
    def get_file_base64(self, path):
        """Reads a file and returns it as a base64 encoded string."""
        import base64
        try:
            # Path safety check
            full_path = os.path.abspath(os.path.join(project_root, path))
            if os.path.commonpath([full_path, os.path.abspath(project_root)]) != os.path.abspath(project_root):
                return {"error": "Access denied: Path is outside project root."}

            with open(full_path, 'rb') as f:
                data = f.read()
                return base64.b64encode(data).decode('utf-8')
        except Exception as e:
            return {"error": str(e)}

    def list_files(self, path="."):
        """Lists files with protection status."""
        try:
            # Path safety check
            full_path = os.path.abspath(os.path.join(project_root, path))
            if os.path.commonpath([full_path, os.path.abspath(project_root)]) != os.path.abspath(project_root):
                return {"error": "Access denied: Path is outside project root."}

            items = os.listdir(full_path)
            result = []
            from butler.core.alias_store import alias_store
            for item in items:
                item_path = os.path.join(path, item)
                is_protected = self.guard.is_protected(item_path)
                is_dir = os.path.isdir(os.path.join(full_path, item))
                result.append({
                    # 别名层: 界面显示中文名，真实文件名不变（操作仍用 path）
                    "name": alias_store.resolve_display(item_path, item),
                    "real_name": item,
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
        # Auto-inject jarvis_app instance for full integration compatibility
        params.setdefault("jarvis_app", self.jarvis)
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

    def get_ui_skills(self):
        """Returns a list of skills that have a frontend UI."""
        ui_skills = []
        for s_id, manifest in self.jarvis.skill_manager.manifests.items():
            if manifest.get('has_frontend'):
                ui_skills.append({
                    "id": s_id,
                    "name": manifest.get('name', s_id),
                    "icon": manifest.get('icon', 'fa-puzzle-piece'),
                    "frontend_path": manifest.get('frontend_path')
                })
        return ui_skills

    def launch_ai_subtitles(self):
        """Launches the floating AI Subtitles overlay window."""
        try:
            return self.jarvis.skill_manager.execute("ai_subtitles", "launch")
        except Exception as e:
            self.logger.error(f"Failed to launch AI Subtitles: {e}")
            return {"status": "error", "message": str(e)}

    def launch_screen_capture(self):
        """Launches the Screen Capture & Recording floating panel."""
        try:
            self.window.evaluate_js("if (window.ScreenCapture) window.ScreenCapture.openPanel();")
            return {"status": "ok"}
        except Exception as e:
            self.logger.error(f"Failed to launch Screen Capture: {e}")
            return {"status": "error", "message": str(e)}

    def load_skill_frontend(self, frontend_path: str):
        """Navigate the webview container to a skill's frontend HTML file."""
        import os
        abs_path = os.path.abspath(frontend_path)
        if os.path.exists(abs_path):
            self.window.load_url(f"file://{abs_path}")
            return {"status": "ok"}
        return {"error": f"Frontend not found: {abs_path}"}

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

    def get_time_machine_range(self, start, end, category=None):
        """获取时光机历史数据"""
        from butler.core.time_machine import time_machine
        return time_machine.get_range(float(start), float(end), category)

    def get_realtime_metrics(self):
        """获取实时系统指标供热力图背景使用"""
        from butler.core.algorithms import dras_manager
        return dras_manager.get_system_stats()

    # --- AI Model Configuration APIs ---
    def get_model_config(self):
        """获取当前 AI 大模型配置（含已遮蔽/安全的 API Key 字符串）"""
        from butler.core.config_manager import config_manager
        from butler.core.config_model import PROVIDER_KEY_PATHS
        import os

        provider = config_manager.get('api.provider', 'deepseek') or 'deepseek'
        base_url = config_manager.get('api.base_url', '') or os.getenv('API_BASE_URL', '')
        model_name = config_manager.get('api.model_name', '') or os.getenv('MODEL_NAME', '')
        provider_label = config_manager.get('api.provider_label', '') or os.getenv('CUSTOM_PROVIDER_NAME', '')

        # 根据 provider 提取对应的 key
        cfg_path, env_name, _field = PROVIDER_KEY_PATHS.get(provider, PROVIDER_KEY_PATHS['deepseek'])
        api_key = config_manager.get(cfg_path, '') or os.getenv(env_name, '')

        baidu_secret_key = config_manager.get('api.baidu_secret_key', '') or os.getenv('BAIDU_SECRET_KEY', '')
        baidu_app_id = config_manager.get('api.baidu_app_id', '') or os.getenv('BAIDU_APP_ID', '')
        temperature = config_manager.get('api.temperature', 0.7)
        max_tokens = config_manager.get('api.max_tokens', 4096)

        return {
            "provider": provider,
            "base_url": base_url,
            "model_name": model_name,
            "provider_label": provider_label,
            "api_key": api_key,
            "secret_key": baidu_secret_key,
            "app_id": baidu_app_id,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

    def test_model_connection(self, config):
        """在线连通性测试 (Test Connection)

        Args:
            config: 字典包含 provider, api_key, base_url, model_name, secret_key, app_id 等
        """
        from butler.core.api_validator import APIValidator
        return APIValidator.test_model_provider(config)

    def save_model_config(self, config):
        """保存 AI 大模型提供商配置并实时生效

        Args:
            config: 字典包含 provider, api_key, base_url, model_name, provider_label, secret_key, app_id, temperature, max_tokens
        """
        from butler.core.config_manager import config_manager
        from butler.core.config_model import PROVIDER_KEY_PATHS

        provider = config.get('provider', 'deepseek')
        base_url = config.get('base_url', '')
        model_name = config.get('model_name', '')
        api_key = config.get('api_key', '')
        provider_label = config.get('provider_label', '')
        secret_key = config.get('secret_key', '')
        app_id = config.get('app_id', '')
        temperature = config.get('temperature', 0.7)
        max_tokens = config.get('max_tokens', 4096)

        config_manager.set('api.provider', provider, persist=True)
        config_manager.set('api.base_url', base_url, persist=True)
        config_manager.set('api.model_name', model_name, persist=True)
        config_manager.set('api.provider_label', provider_label, persist=True)
        config_manager.set('api.temperature', float(temperature), persist=True)
        config_manager.set('api.max_tokens', int(max_tokens), persist=True)

        if provider == 'baidu' or provider == 'qianfan':
            if secret_key:
                config_manager.set('api.baidu_secret_key', secret_key, persist=True)
            if app_id:
                config_manager.set('api.baidu_app_id', app_id, persist=True)

        # 写入当前 selected provider 的 key
        cfg_path, _env_name, _field = PROVIDER_KEY_PATHS.get(provider, PROVIDER_KEY_PATHS['deepseek'])
        config_manager.set(cfg_path, api_key, persist=True)

        # 重新加载 config_manager 确保运行时单例同步
        config_manager.reload()

        self.logger.info(f"AI Model configuration updated: provider={provider}, model={model_name}")
        return {"status": "success", "message": "大模型配置已保存并无缝生效。"}

    # --- Flash Input Support ---
    def submit_flash_command(self, command):
        """Called from flash_input.html."""
        self.jarvis.ui_print(f"⚡ [Flash] {command}", tag='system_message')
        threading.Thread(target=self._run_command, args=(command,), daemon=True).start()
        self.hide_flash()

    def get_input_suggestions(self, prefix):
        """获取输入联想建议"""
        try:
            from butler.core.memory.input_memory import input_memory
            return input_memory.suggest(prefix)
        except Exception as e:
            self.logger.error(f"Failed to get suggestions: {e}")
            return []

    def hide_flash(self):
        """Hides the flash input window."""
        event_bus.emit("flash_hide")

    # --- Breathing Lights (子界面呼吸灯) ---
    def breath_light_states(self):
        """前端拉取子界面状态（呼吸灯初始渲染）。"""
        from butler.core.window_registry import window_registry
        return window_registry.snapshot()

    def breath_light_view(self, view_id, title, is_open):
        """主界面内子面板开/关上报（open/close 各一次）。"""
        from butler.core.window_registry import window_registry
        if is_open:
            window_registry.register_view(view_id, title or view_id)
        else:
            window_registry.remove(view_id)
        return {"status": "ok"}

    def breath_light_touch(self, view_id):
        """子界面活动上报（该灯在静默窗口内保持快闪）。"""
        from butler.core.window_registry import window_registry
        window_registry.set_active(view_id)
        window_registry.touch(view_id)
        return {"status": "ok"}

    def breath_light_focus(self, entry_id):
        """点击呼吸灯：OS 窗口走 pywebview 置顶，面板交由前端置顶。"""
        from butler.core.window_registry import window_registry
        return window_registry.focus(entry_id)

    def breath_light_set_mode(self, mode):
        """显示模式：inline(主界面左上角) / hud(全屏置顶) / off；持久化到配置。"""
        from butler.core.config_manager import config_manager
        if mode not in ("inline", "hud", "off"):
            mode = "inline"
        config_manager.set("display.breath_light.mode", mode, persist=True)
        event_bus.emit("breath_light_mode", {"mode": mode})
        return {"status": "ok", "mode": mode}

    def breath_light_get_mode(self):
        from butler.core.config_manager import config_manager
        return config_manager.get("display.breath_light.mode", "inline")

    # --- Alias Layer (中文显示名 / 英文真实名) ---
    def alias_set(self, path, display_name):
        """为文件/文件夹设置中文显示名（真实文件名不变）。"""
        from butler.core.alias_store import alias_store
        try:
            return alias_store.set_alias(path, display_name)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def alias_get(self, path):
        from butler.core.alias_store import alias_store
        return alias_store.get(path) or {}

    def alias_remove(self, path):
        from butler.core.alias_store import alias_store
        return {"status": "ok", "removed": alias_store.remove(path)}

    def alias_list(self):
        from butler.core.alias_store import alias_store
        return alias_store.list_all()

    def alias_batch_suggest(self, path="."):
        """扫描目录给出中文显示名建议（只翻译认识的词）；确认后用 alias_apply_batch。"""
        from butler.core.alias_store import alias_store
        full = path if os.path.isabs(path) else os.path.join(project_root, path)
        return alias_store.batch_suggest(full)

    def alias_apply_batch(self, mapping):
        """应用 {real_path: display_name} 映射（用户确认后调用）。"""
        from butler.core.alias_store import alias_store
        count = alias_store.apply_batch(mapping or {})
        return {"status": "ok", "applied": count}

def main():
    # Initialize Jarvis in headless mode (no Tkinter root)
    jarvis = Jarvis(root=None)

    # Load HTML via AssetLoader
    html_path = asset_loader.resolve_path("ui://index.html")
    flash_path = asset_loader.resolve_path("ui://flash_input.html")

    window = webview.create_window(
        'Butler - Modern UI',
        url=html_path,
        width=1200,
        height=800,
        background_color='#1e1e1e'
    )

    # Create Flash Input Window (Initially hidden)
    flash_window = webview.create_window(
        'Butler - Flash Input',
        url=flash_path,
        width=700,
        height=150,
        frameless=True,
        on_top=True,
        hidden=True,
        transparent=True,
        background_color='#00000000' # Fully transparent
    )

    bridge = ModernBridge(jarvis, window)
    window.expose(bridge)
    flash_window.expose(bridge)

    # --- Breathing Lights: 子界面注册表 + 可选全屏置顶 HUD 窗口 ---
    from butler.core.window_registry import window_registry
    from butler.core.config_manager import config_manager
    window_registry.start()
    bl_mode = config_manager.get("display.breath_light.mode", "inline")

    hud_window = webview.create_window(
        'Butler - Breath Lights HUD',
        url=asset_loader.resolve_path("ui://breath_hud.html"),
        width=480,
        height=56,
        frameless=True,
        on_top=True,
        hidden=(bl_mode != "hud"),
        transparent=True,
        background_color='#00000000'
    )
    hud_window.expose(bridge)

    def push_breath_states(payload):
        data = json.dumps(payload, ensure_ascii=False)
        try:
            window.evaluate_js(f"window.onWindowStates({data})")
        except Exception:
            pass
        try:
            if not hud_window.hidden:
                hud_window.evaluate_js(f"window.onWindowStates({data})")
        except Exception:
            pass

    def on_breath_mode(payload):
        mode = (payload or {}).get("mode", "inline")
        try:
            if mode == "hud":
                hud_window.show()
                try:
                    hud_window.move(12, 12)  # 尽量贴屏幕左上角；旧版 pywebview 无 move 则忽略
                except Exception:
                    pass
            else:
                hud_window.hide()
        except Exception:
            pass
        try:
            window.evaluate_js(f"window.applyBreathLightMode({json.dumps(mode)})")
        except Exception:
            pass

    event_bus.subscribe("breath_light_states", push_breath_states)
    event_bus.subscribe("breath_light_mode", on_breath_mode)

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

    # Flash Input Controls
    def toggle_flash():
        if flash_window.hidden:
            # Center on screen
            flash_window.show()
            flash_window.evaluate_js("document.getElementById('main-input').focus()")
        else:
            flash_window.hide()

    def hide_flash():
        flash_window.hide()

    event_bus.on("flash_hide", hide_flash)

    # Global Hotkey (Alt + Space)
    try:
        keyboard.add_hotkey('alt+space', toggle_flash)
    except Exception as e:
        print(f"Failed to register hotkey: {e}")

    # Apply initial theme from config
    initial_theme = jarvis.config.get("display", {}).get("theme", "google")
    window.evaluate_js(f"window.setTheme({json.dumps(initial_theme)})")

    webview.start(debug=True)

if __name__ == "__main__":
    main()
