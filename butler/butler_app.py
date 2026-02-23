import os
import sys

# Add project root and local lib to sys.path to support portable/local dependency installation
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

lib_path = os.path.join(project_root, "lib_external")
if os.path.exists(lib_path) and lib_path not in sys.path:
    sys.path.insert(0, lib_path)

import time
import datetime
import json
import re
import threading
import tempfile
import shutil
import tkinter as tk
from dotenv import load_dotenv

from package.core_utils.log_manager import LogManager
from butler.CommandPanel import CommandPanel
from butler.data_storage import data_storage_manager
from butler.core.extension_manager import extension_manager
from butler.core.voice_service import VoiceService
from butler.core.nlu_service import NLUService
from butler.usb_screen import USBScreen
from butler.resource_manager import ResourceManager, PerformanceMode
from local_interpreter.interpreter import Interpreter
from plugin.long_memory.redis_long_memory import RedisLongMemory
from plugin.long_memory.zvec_long_memory import ZvecLongMemory
from plugin.long_memory.chroma_long_memory import SQLiteLongMemory
from plugin.long_memory.long_memory_interface import LongMemoryItem
from butler.core.intent_dispatcher import intent_registry
from butler.core import legacy_commands # Ensure legacy intents are registered
from butler.core.hybrid_link import HybridLinkClient
from package.device.standalone_manager import StandaloneManager

class Jarvis:
    def __init__(self, root, usb_screen=None):
        self.root = root
        self.usb_screen = usb_screen
        self.resource_manager = ResourceManager()
        self.display_mode = 'host'
        self.running = True
        self.panel = None

        load_dotenv()
        self.logger = LogManager.get_logger(__name__)

        # Load configurations
        self.config = self._load_config()
        self.prompts = self._load_json_resource("prompts.json")
        self.program_mapping = self._load_json_resource("program_mapping.json")

        # Initialize services
        self._initialize_long_memory()
        
        self.nlu_service = NLUService(os.getenv("DEEPSEEK_API_KEY"), self.prompts)
        self.voice_service = VoiceService(self.handle_user_command, self.ui_print, self._on_voice_status_change)
        
        # Apply voice config
        voice_mode = self.config.get("voice", {}).get("mode", "offline")
        self.voice_service.set_voice_mode(voice_mode)

        self.interpreter = Interpreter(
            safety_mode=self.config.get("interpreter", {}).get("safety_mode", True),
            max_iterations=self.config.get("interpreter", {}).get("max_iterations", 10)
        )

        # Initialize Hybrid Link for system utility
        self.sysutil = HybridLinkClient(
            executable_path=os.path.join(project_root, "programs/hybrid_sysutil/sysutil"),
            fallback_enabled=True
        )
        self.sysutil.start()

        # Initialize Standalone Manager
        self.standalone_manager = StandaloneManager(self)
        self.standalone_manager.start()

        self.ui_suggested = False
        self.waiting_for_ui_confirm = False

    def _load_config(self):
        config_path = os.path.join(project_root, "config", "system_config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            print(f"Failed to load system_config.json: {e}")
            return {}

    def _load_json_resource(self, filename):
        path = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load {filename}: {e}")
            return {}

    def _initialize_long_memory(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        try:
            if api_key:
                # 优先尝试使用 Redis (如果已配置且运行中)
                self.long_memory = RedisLongMemory(api_key=api_key)
                self.long_memory.init(self.logger)
            else: raise ValueError("No API Key")
        except Exception as e:
            self.logger.warning(f"无法初始化 RedisLongMemory: {e}。尝试使用轻量级 ZvecLongMemory...")

            # 安全检查 zvec 是否可用且不会导致 Illegal Instruction
            zvec_safe = False
            try:
                import subprocess
                res = subprocess.run([sys.executable, "-c", "import zvec"],
                                     capture_output=True, timeout=2)
                zvec_safe = (res.returncode == 0)
            except Exception:
                zvec_safe = False

            try:
                if api_key and zvec_safe:
                    # 如果 Redis 不可用，则尝试使用 zvec (极速本地向量库)
                    self.long_memory = ZvecLongMemory(api_key=api_key)
                    self.long_memory.init(self.logger)
                else:
                    raise ValueError("No API Key for Zvec or zvec is incompatible with this CPU")
            except Exception as e2:
                self.logger.error(f"无法初始化 ZvecLongMemory: {e2}。降级到 SQLiteLongMemory...")
                self.long_memory = SQLiteLongMemory()
                self.long_memory.init()

    def set_panel(self, panel):
        self.panel = panel

    def _on_voice_status_change(self, is_listening):
        if self.panel:
            self.root.after(0, self.panel.update_listen_button_state, is_listening)

    def ui_print(self, message, tag='ai_response', response_id=None):
        print(message)
        if self.display_mode in ('host', 'both') and self.panel:
            if tag == 'ai_response_start':
                self.panel.append_to_history(message, 'ai_response', response_id=response_id)
            else:
                self.panel.append_to_history(message, tag)
        if self.display_mode in ('usb', 'both') and self.usb_screen:
            self.usb_screen.display(message, clear_screen=True)

    def speak(self, text):
        """朗读给定的文本并在 UI 中打印。"""
        self.ui_print(text, tag='ai_response')
        memory_item = LongMemoryItem.new(content=text, id=f"assistant_{time.time()}",
                                        metadata={"role": "assistant", "timestamp": time.time()})
        self.long_memory.save([memory_item])
        self.voice_service.speak(text)

    def handle_user_command(self, command, programs=None):
        if not command: return
        cmd = command.strip()

        # Handle UI confirmation prompt
        if self.waiting_for_ui_confirm:
            if any(word in cmd.lower() for word in ['是', '好', '打开', '需要', 'yes', 'ok', 'open']):
                self.waiting_for_ui_confirm = False
                self.ui_print("正在为您打开 UI 界面...")
                self._activate_full_ui()
                return
            elif any(word in cmd.lower() for word in ['不', '否', '取消', 'no', 'cancel']):
                self.waiting_for_ui_confirm = False
                self.ui_print("已取消 UI 启动。")
                return

        # Command Dispatching
        if cmd.startswith("/voice-mode "):
            mode = cmd.split()[1].lower()
            if self.voice_service.set_voice_mode(mode):
                self.ui_print(f"语音模式切换到: {mode}")
            else:
                self.ui_print("无效模式", tag='error')
        elif cmd.startswith("/safety "):
            self.interpreter.safety_mode = (cmd.split()[1].lower() == 'on')
            self.ui_print(f"安全模式: {'开启' if self.interpreter.safety_mode else '关闭'}")
        elif cmd == "/approve":
            if self.interpreter.last_code_for_approval and self.panel:
                text = self.panel.output_text.get("1.0", tk.END)
                code_blocks = re.findall(r"```python\n(.*?)\n```", text, re.DOTALL)
                if code_blocks:
                    edited_code = code_blocks[-1].strip()
                    if edited_code != self.interpreter.last_code_for_approval.strip():
                        self.logger.info("在 UI 中检测到编辑的代码。使用编辑后的版本。")
                        self.interpreter.last_code_for_approval = edited_code
            self.stream_interpreter_response(cmd, approved=True)
        elif cmd.startswith("/os-mode "):
            self.interpreter.os_mode = (cmd.split()[1].lower() == 'on')
            self.ui_print(f"OS 模式: {'开启' if self.interpreter.os_mode else '关闭'}")
        elif cmd == "/cleanup":
            self.ui_print("正在执行系统数据回收...")
            try:
                from package import data_recycler
                summary = data_recycler.run()
                self.ui_print(summary)
            except Exception as e:
                self.ui_print(f"数据回收失败: {e}", tag='error')
        elif cmd.startswith("/legacy "):
            self._handle_legacy_command(cmd[8:])
        else:
            if self.interpreter.is_ready:
                self.stream_interpreter_response(cmd)
            else:
                self.ui_print("解释器未就绪，请检查 API Key", tag='error')

    def _handle_legacy_command(self, legacy_command):
        """以旧版模式处理命令。"""
        self.ui_print(f"正在以旧版模式处理: {legacy_command}")
        matched_intent = intent_registry.match_intent_locally(legacy_command)

        if matched_intent and not intent_registry.intent_requires_entities(matched_intent):
            entities = {}
        else:
            nlu_result = self.nlu_service.extract_intent(legacy_command, self.long_memory.get_recent_history(10))
            matched_intent = nlu_result.get("intent", "unknown")
            entities = nlu_result.get("entities", {})

        # 通过调度程序或扩展管理器执行
        handler_args = {"jarvis_app": self, "entities": entities, "programs": extension_manager.packages}
        result = intent_registry.dispatch(matched_intent, **handler_args)

        if result is None:
            # 尝试扩展
            try:
                ext_result = extension_manager.execute(matched_intent, command=legacy_command, args=entities)
                if ext_result: self.speak(str(ext_result))
            except Exception:
                self.speak("抱歉，我不明白您的意思。")

    def stream_interpreter_response(self, command, approved=False):
        response_id = f"res_{time.time()}"
        self.root.after(0, self.ui_print, "Jarvis:", 'ai_response_start', response_id)

        def run():
            stream = self.interpreter.run_approved_code() if approved else self.interpreter.run(command)
            final_answer = ""
            for event, payload in stream:
                if event == "code_chunk":
                    self.root.after(0, self.panel.append_to_response, payload, response_id)
                elif event == "result":
                    self.root.after(0, self.panel.append_to_response, f"\n\n{payload}\n\n", response_id)
                    if "**Final Answer:**" in payload:
                        final_answer = payload.split("**Final Answer:**")[-1].strip()
                elif event == "screenshot":
                    self.root.after(0, self.panel.update_screenshot, payload)
            if final_answer: self.root.after(0, self.speak, final_answer)

        threading.Thread(target=run, daemon=True).start()

    def panel_command_handler(self, command_type, payload):
        if command_type == "text":
            self.handle_user_command(payload)
        elif command_type == "execute_program":
            extension_manager.execute(payload)
        elif command_type == "display_mode_change":
            self.display_mode = payload
        elif command_type == "manual_action":
            self._handle_manual_action(payload)
        elif command_type == "voice":
            if self.voice_service.is_listening:
                self.voice_service.stop_listening()
            else:
                self.voice_service.start_listening()

    def _handle_manual_action(self, payload):
        """处理来自 UI 的手动操作。"""
        action = payload.get("action")
        try:
            import pyautogui
            if action == "screenshot":
                from local_interpreter.tools import os_tools
                screenshot_b64 = os_tools.capture_screen()
                self.panel.update_screenshot(screenshot_b64)
            elif action == "left_click":
                coord = payload.get("coordinate")
                if coord: pyautogui.click(coord[0], coord[1])
                else: pyautogui.click()
            elif action == "type":
                text = payload.get("text")
                if text: pyautogui.write(text)

            # 记录到解释器历史记录
            self.interpreter.conversation_history.append({
                "role": "assistant",
                "content": f"用户执行了手动操作: {action} {payload.get('coordinate', '')} {payload.get('text', '')}"
            })
        except Exception as e:
            self.logger.error(f"Manual action error: {e}")

    def _handle_open_program(self, entities, programs):
        program_name = entities.get("program_name")
        if program_name:
            try:
                extension_manager.execute(program_name)
            except Exception as e:
                self.speak(f"无法打开程序 {program_name}: {e}")
        else:
            self.speak("未指定程序名称")

    def _handle_exit(self):
        self.logger.info("程序已退出")
        self.speak("再见")
        self.running = False
        self.voice_service.stop_listening()
        if self.root: self.root.quit()

    def main(self):
        self._cleanup_temp_files()
        self.voice_service.start_listening()
        self.speak("Jarvis 已启动并就绪")

        # Start general monitoring thread
        threading.Thread(target=self._update_ui_loop, daemon=True).start()

    def suggest_ui_activation(self):
        """Called by StandaloneManager when a display is detected."""
        if not self.ui_suggested and self.display_mode in ('usb', 'host'):
            if self.root is None: # We are in headless mode
                 self.speak("检测到可用屏幕。是否需要开启图形界面程序？")
                 self.waiting_for_ui_confirm = True
                 self.ui_suggested = True

    def _activate_full_ui(self):
        """Dynamically launches the Tkinter UI if running in headless mode."""
        if self.root:
            self.ui_print("UI 已经处于运行状态。", tag='system_message')
            return

        def launch():
            try:
                self.logger.info("Starting UI thread...")
                # In a real scenario, we might need to restart the process or launch a subprocess
                # For this implementation, we simulate the 'CommandPanel' initialization
                self.speak("提示：在当前终端环境下直接启动 Tkinter 可能需要有效的 X11/Wayland 转发。")
                # If we had a mechanism to relaunch with UI, we'd trigger it here.
                # For now, we update state.
                self.display_mode = 'host'
            except Exception as e:
                self.logger.error(f"Failed to launch UI: {e}")

        threading.Thread(target=launch, daemon=True).start()

    def _update_ui_loop(self):
        """Regularly updates the UI state based on hardware status."""
        while self.running:
            try:
                if self.standalone_manager and self.panel:
                    status = self.standalone_manager.get_status()
                    connected = (status["connection"] == "Connected")
                    device = status["devices"][0] if status["devices"] else ""
                    self.root.after(0, self.panel.update_link_status, connected, device)
            except Exception:
                pass
            time.sleep(5)

    def _cleanup_temp_files(self):
        temp_dir = tempfile.gettempdir()
        for f in os.listdir(temp_dir):
            if f.startswith("jarvis_temp_"):
                try:
                    path = os.path.join(temp_dir, f)
                    if os.path.isfile(path): os.remove(path)
                    else: shutil.rmtree(path)
                except Exception: pass

        # Integrated Data Recycler
        try:
            from package import data_recycler
            data_recycler.run()
        except Exception as e:
            self.logger.error(f"Startup cleanup failed: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="以无头模式运行")
    args = parser.parse_args()

    usb_screen = USBScreen(40, 8)
    if args.headless:
        jarvis = Jarvis(None, usb_screen)
        jarvis.main()
        while jarvis.running: time.sleep(1)
    else:
        root = tk.Tk()
        root.title("Jarvis 助手")
        jarvis = Jarvis(root, usb_screen)

        # Get tools for panel
        all_tools = {t['name']: t.get('path', t.get('module')) for t in extension_manager.get_all_tools()}

        panel = CommandPanel(root, program_mapping=jarvis.program_mapping,
                             programs=all_tools, command_callback=jarvis.panel_command_handler)
        panel.pack(fill=tk.BOTH, expand=True)
        jarvis.set_panel(panel)
        jarvis.main()
        root.mainloop()

if __name__ == "__main__":
    main()
