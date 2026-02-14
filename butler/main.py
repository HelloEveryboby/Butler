import os
import sys
import time
import datetime
import json
import re
import threading
import tempfile
import shutil
import tkinter as tk
from dotenv import load_dotenv

from package.log_manager import LogManager
from butler.CommandPanel import CommandPanel
from butler.data_storage import data_storage_manager
from butler.core.extension_manager import extension_manager
from butler.core.voice_service import VoiceService
from butler.core.nlu_service import NLUService
from butler.usb_screen import USBScreen
from butler.resource_manager import ResourceManager, PerformanceMode
from local_interpreter.interpreter import Interpreter
from plugin.long_memory.redis_long_memory import RedisLongMemory
from plugin.long_memory.chroma_long_memory import SQLiteLongMemory
from plugin.long_memory.long_memory_interface import LongMemoryItem
from butler.core.intent_dispatcher import intent_registry
from butler.core import legacy_commands # Ensure legacy intents are registered

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

        # Initialize services
        self._initialize_long_memory()
        self.prompts = self._load_json_resource("prompts.json")
        self.program_mapping = self._load_json_resource("program_mapping.json")
        
        self.nlu_service = NLUService(os.getenv("DEEPSEEK_API_KEY"), self.prompts)
        self.voice_service = VoiceService(self.handle_user_command, self.ui_print)
        self.interpreter = Interpreter()
        
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
                self.long_memory = RedisLongMemory(api_key=api_key)
                self.long_memory.init(self.logger)
            else: raise ValueError("No API Key")
        except Exception:
            self.long_memory = SQLiteLongMemory()
            self.long_memory.init()

    def set_panel(self, panel):
        self.panel = panel

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
        self.ui_print(text, tag='ai_response')
        memory_item = LongMemoryItem.new(content=text, id=f"assistant_{time.time()}",
                                        metadata={"role": "assistant", "timestamp": time.time()})
        self.long_memory.save([memory_item])
        self.voice_service.speak(text)

    def handle_user_command(self, command, programs=None):
        if not command: return
        cmd = command.strip()

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
                        self.logger.info("Detected edited code in UI. Using edited version.")
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
        self.ui_print(f"正在以旧版模式处理: {legacy_command}")
        matched_intent = intent_registry.match_intent_locally(legacy_command)

        if matched_intent and not intent_registry.intent_requires_entities(matched_intent):
            entities = {}
        else:
            nlu_result = self.nlu_service.extract_intent(legacy_command, self.long_memory.get_recent_history(10))
            matched_intent = nlu_result.get("intent", "unknown")
            entities = nlu_result.get("entities", {})

        # Execution via dispatcher or extension_manager
        handler_args = {"jarvis_app": self, "entities": entities, "programs": extension_manager.packages}
        result = intent_registry.dispatch(matched_intent, **handler_args)

        if result is None:
            # Try extensions
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

    def _handle_manual_action(self, payload):
        """Handles manual actions from the UI."""
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

            # Log to interpreter history
            self.interpreter.conversation_history.append({
                "role": "assistant",
                "content": f"User performed manual action: {action} {payload.get('coordinate', '')} {payload.get('text', '')}"
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
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    usb_screen = USBScreen(40, 8)
    if args.headless:
        jarvis = Jarvis(None, usb_screen)
        jarvis.main()
        while jarvis.running: time.sleep(1)
    else:
        root = tk.Tk()
        root.title("Jarvis Assistant")
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
