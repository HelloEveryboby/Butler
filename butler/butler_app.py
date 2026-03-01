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
from butler.core.habit_manager import habit_manager
from butler.usb_screen import USBScreen
from butler.resource_manager import ResourceManager, PerformanceMode
from plugin.long_memory.redis_long_memory import RedisLongMemory
from plugin.long_memory.zvec_long_memory import ZvecLongMemory
from plugin.long_memory.chroma_long_memory import SQLiteLongMemory
from plugin.long_memory.long_memory_interface import LongMemoryItem
from butler.core.intent_dispatcher import intent_registry
from butler.core import legacy_commands # Ensure legacy intents are registered
from butler.interpreter import interpreter
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
        self._interaction_count = 0

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
        elif cmd.startswith("/py ") or cmd.startswith("/python "):
            code = cmd.split(maxsplit=1)[1]
            self._execute_with_interpreter("python", code)
        elif cmd.startswith("/sh ") or cmd.startswith("/shell "):
            command = cmd.split(maxsplit=1)[1]
            self._execute_with_interpreter("shell", command)
        elif cmd == "/profile":
            self.ui_print(habit_manager.get_profile_summary(), tag='system_message')
        elif cmd == "/profile-reset":
            habit_manager.reset_profile()
            self.ui_print("用户画像与习惯已重置。", tag='system_message')
        elif cmd.startswith("记住这一点：") or cmd.startswith("记住：") or cmd.startswith("Remember this:"):
            self._handle_manual_habit_learning(cmd)
        else:
            # Check if we should use Interpreter for general queries (Auto-detect)
            if self._should_use_interpreter(cmd):
                self._execute_with_llm_interpreter(cmd)
            else:
                # Default to legacy command handling (intent-based)
                self._handle_legacy_command(cmd)

        # Trigger reflection every 3 interactions or if it's a complex tool interaction
        # to save API costs and avoid over-reflection.
        self._interaction_count += 1
        is_complex = self._should_use_interpreter(cmd)
        if self._interaction_count % 3 == 0 or is_complex:
            threading.Thread(target=self._reflect_on_interaction, daemon=True).start()

    def _should_use_interpreter(self, command):
        # Basic heuristic: if command mentions files, calculations, or complex tasks
        keywords = ['文件', '计算', '报销', '总结', '文件夹', 'excel', 'word', 'pdf', '分析']
        return any(k in command.lower() for k in keywords)

    def _execute_with_interpreter(self, lang, code):
        self.ui_print(f"Executing {lang} code...", tag='system_message')
        success, output = interpreter.run(lang, code)

        # Format for Modern UI
        # Check if we are running under Modern UI (where ui_print is overridden)
        # or if we have a panel attached.
        is_modern = hasattr(self, 'ui_print') and 'onAIStreamChunk' in str(self.ui_print)

        if is_modern or self.panel:
             self.ui_print(json.dumps({
                 "type": "code_block",
                 "language": lang,
                 "code": code,
                 "output": output
             }), tag='code_block')
        else:
             self.ui_print(f"Output:\n{output}")

    def _execute_with_llm_interpreter(self, command):
        """Uses LLM to generate and run code (Open Interpreter style)."""
        self.ui_print("AI 正在思考并编写代码...", tag='system_message')

        system_prompt = (
            "You are a desktop agent that solves tasks by writing Python code. "
            "You have access to the local file system and office software. "
            "Available tools: \n"
            "- package.document.office_automator: create_excel_report, create_word_document, fill_pdf_fields, open_in_native_app.\n"
            "- package.document.expense_report_engine: expense_genius.process_receipts(data).\n"
            "- package.document.cross_folder_analyzer: analyzer.analyze_folders(folders, query).\n"
            "Libraries: pandas, python-docx, openpyxl, PIL. "
            "When asked to edit Word/Excel, write code to modify them and then use "
            "package.document.office_automator.open_in_native_app(path) to show the result. "
            "ALWAYS output code in a block starting with ```python. "
            "If the task is complete, end your message with 'The task is done.' or '任务已完成'。"
        )

        history = self.long_memory.get_recent_history(10)
        max_iterations = 5
        current_input = command

        for i in range(max_iterations):
            prompt = f"{system_prompt}\n\nUser Question: {current_input}"
            response = self.nlu_service.ask_llm(prompt, history)

            # Extract code block
            code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
            if code_match:
                code = code_match.group(1)
                self.ui_print(f"AI 正在执行第 {i+1} 步操作...", tag='system_message')
                success, output = interpreter.run("python", code)

                # Format for Modern UI
                is_modern = hasattr(self, 'ui_print') and 'onAIStreamChunk' in str(self.ui_print)
                if is_modern or self.panel:
                     self.ui_print(json.dumps({
                         "type": "code_block",
                         "language": "python",
                         "code": code,
                         "output": output
                     }), tag='code_block')
                else:
                     self.ui_print(f"Output:\n{output}")

                if "task is done" in response.lower() or "任务已完成" in response:
                    break

                # Feedback loop: feed output back to AI
                current_input = f"Execution Output from step {i+1}:\n{output}\n\nPlease proceed to the next step or fix any errors. If finished, say 'The task is done.'"
                # We update history to keep the context
                history.append({"role": "assistant", "content": response})
            else:
                self.ui_print(response) # Just a text response
                break

    def _handle_legacy_command(self, legacy_command):
        """以旧版模式处理命令。"""
        self.ui_print(f"正在处理: {legacy_command}")
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
                from package.device import os_utils
                screenshot_b64 = os_utils.capture_screen()
                self.panel.update_screenshot(screenshot_b64)
            elif action == "left_click":
                coord = payload.get("coordinate")
                if coord: pyautogui.click(coord[0], coord[1])
                else: pyautogui.click()
            elif action == "type":
                text = payload.get("text")
                if text: pyautogui.write(text)

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

    def _reflect_on_interaction(self):
        """
        Reflects on the recent interaction to extract user habits and preferences.
        Updates the HabitManager based on these insights.
        """
        try:
            # Get recent context from memory
            history = self.long_memory.get_recent_history(4) # Last few turns are enough for reflection

            reflection_prompt = (
                "你是一个观察敏锐且追求默契的助手。请深度分析以下对话，提取用户的'隐形习惯'与'协作默契点'。\n"
                "特别关注以下细节：\n"
                "1. **快捷需求**: 用户是否有特定的缩写、口头禅或模糊指令（例如'老样子'指代什么）？\n"
                "2. **工具偏好**: 用户是否在处理某类任务时总是倾向于某个特定工具或参数？\n"
                "3. **雷区与痛点**: 用户曾纠正过你什么？用户不喜欢什么样的反馈？\n"
                "4. **工作流**: 用户的任务通常包含哪些固定的前后置步骤？\n\n"
                "请返回一个 JSON 格式的对象，包含以下可选键：\n"
                "- `preferences`: 字典。记录明确偏好（如：'preferred_language': 'Python'）和默契点（如：'auto_open_browser': true）。\n"
                "- `interaction_style`: 字符串。用户的沟通风格及情感偏好。\n"
                "- `common_tasks`: 列表。用户的高频任务描述。\n"
                "- `preferred_tools`: 列表。用户偏好的工具名。\n\n"
                "只返回 JSON，确保简洁精准。如果没有新发现，请返回空对象 {}。"
            )

            response = self.nlu_service.ask_llm(reflection_prompt, history, use_habit=False)

            # Use regex to find JSON block for better robustness
            json_match = re.search(r"(\{.*\})", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    insights = json.loads(json_str)
                    if insights:
                        self.logger.info(f"Reflected on interaction and found insights: {insights}")
                        habit_manager.update_from_reflection(insights)
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse reflected insights: {json_str}")

        except Exception as e:
            self.logger.error(f"Reflection process failed: {e}")

    def _handle_manual_habit_learning(self, command: str):
        """Processes manual habit learning requests from the user."""
        content = command.split('：', 1)[-1].split(':', 1)[-1].strip()
        self.ui_print(f"正在将 '{content}' 存入核心记忆...", tag='system_message')

        # We use the reflection mechanism but with high priority for this specific turn
        history = [
            {"role": "user", "content": command},
            {"role": "assistant", "content": "好的，我已经将此条目加入我的核心协作协议。"}
        ]

        # Use a more direct extraction for manual learning
        extraction_prompt = (
            "用户要求你记住一条特定的协作偏好或习惯. 请将其转换为我们的习惯画像 JSON 格式。\n"
            "输入内容: " + content + "\n"
            "只返回包含 `preferences` 或 `common_tasks` 的 JSON。"
        )

        try:
            response = self.nlu_service.ask_llm(extraction_prompt, history, use_habit=False)
            json_match = re.search(r"(\{.*\})", response, re.DOTALL)
            if json_match:
                insights = json.loads(json_match.group(1))
                habit_manager.update_from_reflection(insights)
                self.ui_print("核心记忆已更新。您可以输入 `/profile` 查看结果。", tag='system_message')
            else:
                # Fallback to simple preference
                habit_manager.update_preference("custom_note", content)
                self.ui_print("已将此条目作为自定义备注存入画像。", tag='system_message')
        except Exception as e:
            self.logger.error(f"Manual habit learning failed: {e}")
            self.ui_print("手动记忆失败，请稍后再试。", tag='error')

    def _handle_exit(self):
        self.logger.info("程序已退出")
        self.speak("再见")
        self.running = False
        self.voice_service.stop_listening()
        if self.root: self.root.quit()

    def main(self):
        self._cleanup_temp_files()
        self.voice_service.start_listening()

        # Start Autonomous Switchboard (Self-healing system)
        try:
            from package.core_utils.autonomous_switch import AutonomousSwitch
            switch = AutonomousSwitch()
            switch.start(background=True)
            self.logger.info("Autonomous Switchboard started.")
        except Exception as e:
            self.logger.error(f"Failed to start Autonomous Switchboard: {e}")

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
    parser.add_argument("--modern", action="store_true", help="使用精致 Web UI 启动 (默认)")
    parser.add_argument("--classic", "--admin", action="store_true", dest="classic", help="启动 Tkinter 经典/管理界面")
    args = parser.parse_args()

    # Initialize common components
    usb_screen = USBScreen(40, 8)

    # Priority: Headless > Classic/Admin > Modern (Default)
    if args.headless:
        jarvis = Jarvis(None, usb_screen)
        jarvis.main()
        while jarvis.running: time.sleep(1)
        return

    if not args.classic:
        try:
            from frontend.program import modern_app
            modern_app.main()
            return
        except Exception as e:
            print(f"Failed to start Modern UI: {e}. Falling back to Classic UI...")
            # Fall through to classic UI

    # Classic/Admin UI or Fallback
    root = tk.Tk()
    root.title("Jarvis 助手 [管理模式]")
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
