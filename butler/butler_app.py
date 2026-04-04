import os
import sys
import time
import datetime
import json
import re
import threading
import time
from typing import Dict, Any
import tempfile
import shutil
import tkinter as tk
from pathlib import Path
from dotenv import load_dotenv

# tmd要是中考分不那么低一中就去了，也就能早读了
# Add project root and local lib to sys.path to support portable/local dependency installation
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

lib_path = project_root / "lib_external"
if lib_path.exists():
    import site
    site.addsitedir(str(lib_path))

from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader
from package.core_utils.quota_manager import quota_manager
from butler.core.event_bus import event_bus
from butler.CommandPanel import CommandPanel
from butler.data_storage import data_storage_manager
from butler.core.extension_manager import extension_manager
from butler.core.voice_service import VoiceService
from butler.core.nlu_service import NLUService
from butler.core.habit_manager import habit_manager
from butler.core.skill_manager import SkillManager
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
from butler.core.runner_server import RunnerServer
from package.device.standalone_manager import StandaloneManager

class Jarvis:
    def __init__(self, root=None, usb_screen=None):
        self.root = root # Still needed for .after() if we don't have a better way, but we'll try to decouple
        self.usb_screen = usb_screen
        self.resource_manager = ResourceManager()
        self.display_mode = 'host'
        self.running = True
        self.pending_dev_code = None

        self._check_environment()
        load_dotenv()
        self.logger = LogManager.get_logger(__name__)

        # Load configurations
        self.config = config_loader._config
        self.prompts = self._load_json_resource("prompts.json")
        self.program_mapping = self._load_json_resource("program_mapping.json")

        # Initialize services
        self._initialize_long_memory()
        
        self.nlu_service = NLUService(config_loader.get("api.deepseek.key"), self.prompts)
        self.voice_service = VoiceService(self.handle_user_command, self.ui_print, self._on_voice_status_change)
        self.skill_manager = SkillManager()
        self.skill_manager.load_skills()
        
        # Apply voice config
        voice_mode = self.config.get("voice", {}).get("mode", "offline")
        self.voice_service.set_voice_mode(voice_mode)

        # Initialize Hybrid Link for system utility
        self.sysutil = HybridLinkClient(
            executable_path=str(project_root / "programs/hybrid_sysutil/sysutil"),
            fallback_enabled=True
        )
        self.sysutil.start()

        # Initialize Standalone Manager
        self.standalone_manager = StandaloneManager(self)
        self.standalone_manager.start()

        # Initialize Runner Server
        runner_config = self.config.get("runner_server", {})
        self.runner_server = RunnerServer(
            host=runner_config.get("host", "0.0.0.0"),
            port=runner_config.get("port", 8000),
            token=runner_config.get("token", "BUTLER_SECRET_2026")
        )
        self.runner_server.register_event_callback(self._on_runner_event)
        self.runner_server.start()

        # Initialize Encryption Suite
        from package.security.encrypt import DualLayerEncryptor
        self.dual_encryptor = DualLayerEncryptor()

        self.ui_suggested = False
        self.waiting_for_ui_confirm = False
        self._interaction_count = 0

    def _load_json_resource(self, filename):
        path = Path(__file__).parent / filename
        try:
            with path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load {filename}: {e}")
            return {}

    def _initialize_long_memory(self):
        api_key = config_loader.get("api.deepseek.key")
        old_memory_data = []

        # 1. Try Redis
        try:
            if api_key:
                self.long_memory = RedisLongMemory(api_key=api_key)
                self.long_memory.init(self.logger)
                return
            else: raise ValueError("No API Key")
        except Exception as e:
            self.logger.warning(f"无法初始化 RedisLongMemory: {e}")
            # speculatively try to export if it partially initialized, though risky.
            # In a real fallback, we'd have a manager.

        # 2. Try Zvec (with fallback migration)
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
                self.long_memory = ZvecLongMemory(api_key=api_key)
                self.long_memory.init(self.logger)
                if old_memory_data:
                    self.long_memory.import_data(old_memory_data)
                return
            else:
                raise ValueError("No API Key for Zvec or zvec is incompatible")
        except Exception as e2:
            self.logger.error(f"无法初始化 ZvecLongMemory: {e2}. 降级到 SQLiteLongMemory...")

            self.long_memory = SQLiteLongMemory()
            self.long_memory.init()
            if old_memory_data:
                self.long_memory.import_data(old_memory_data)

    def _on_voice_status_change(self, is_listening):
        event_bus.emit("voice_status", is_listening)

    def _on_runner_event(self, runner_id: str, data: Dict[str, Any]):
        """Handles incoming messages from remote runners."""
        msg_type = data.get("status")
        if msg_type == "screenshot":
            self.logger.info(f"Received screenshot from runner: {runner_id}")
            # Emit to event bus for UI to display
            event_bus.emit("screenshot_update", data.get("data"))
            self.ui_print(f"收到来自运行节点 '{runner_id}' 的屏幕截图。", tag='system_message')
        elif msg_type == "sys":
            self.ui_print(f"运行节点 '{runner_id}' 系统信息: {data.get('data')}", tag='system_message')
        elif msg_type == "ok":
            self.ui_print(f"运行节点 '{runner_id}' 反馈: {data.get('data')}", tag='system_message')
        elif msg_type == "fail":
            self.ui_print(f"运行节点 '{runner_id}' 错误: {data.get('error')}", tag='error')

    def ui_print(self, message, tag='ai_response', response_id=None):
        print(message)

        # Restore tag mapping for legacy UI compatibility
        if tag == 'ai_response_start':
            tag = 'ai_response'

        if self.display_mode in ('host', 'both'):
            event_bus.emit("ui_output", message, tag, response_id)

        if self.display_mode in ('usb', 'both') and self.usb_screen:
            self.usb_screen.display(message, clear_screen=True)

    def speak(self, text):
        """朗读给定的文本并在 UI 中打印。"""
        self.ui_print(text, tag='ai_response')
        memory_item = LongMemoryItem.new(content=text, id=f"assistant_{time.time()}",
                                        metadata={"role": "assistant", "timestamp": time.time()})
        self.long_memory.save([memory_item])

        # Record in daily memory
        try:
            from package.core_utils.hybrid_memory_manager import hybrid_memory_manager
            hybrid_memory_manager.add_daily_log(f"Assistant: {text}")
        except Exception as e:
            self.logger.error(f"Failed to add to hybrid memory: {e}")

        self.voice_service.speak(text)

    def handle_user_command(self, command, programs=None):
        if not command: return
        cmd = command.strip()

        # Quota Check (Global Halt)
        if quota_manager.halt_system and not quota_manager.check_quota():
            report = quota_manager.get_usage_report()
            msg = f"⚠️ 系统已锁定: API 额度已耗尽 ({report['consumed']}/{report['limit']} {report['unit']})。请增加限额或重置消耗。"
            self.ui_print(msg, tag='error')
            self.voice_service.speak("系统额度已耗尽，已停止所有操作。")
            return

        # Record User input in daily memory
        try:
            from package.core_utils.hybrid_memory_manager import hybrid_memory_manager
            hybrid_memory_manager.add_daily_log(f"User: {cmd}")
        except Exception as e:
            self.logger.error(f"Failed to add User input to hybrid memory: {e}")

        # Easter Egg Detection
        if "tmd要是中考分不那么低一中就去了" in cmd or ("一中" in cmd and "早读" in cmd):
            self._trigger_no1_middle_school_easter_egg()
            return

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
        elif cmd.startswith("/theme "):
            parts = cmd.split()
            if len(parts) > 1:
                theme = parts[1].lower()
                if theme in ['dark', 'light', 'google', 'apple']:
                    # Map dark/light to specific themes
                    if theme == 'dark': theme = 'apple'
                    if theme == 'light': theme = 'google'

                    self.config['display']['theme'] = theme
                    config_loader.set("display.theme", theme)
                    self.ui_print(f"主题切换到: {theme}")
                    event_bus.emit("theme_change", theme)
                else:
                    self.ui_print("无效主题", tag='error')
        elif cmd.startswith("/encrypt ") or cmd.startswith("/decrypt "):
            parts = cmd.split()
            if len(parts) > 1:
                path = parts[1]
                mode = 'encrypt' if cmd.startswith("/encrypt") else 'decrypt'
                self._handle_advanced_encryption(path, mode)
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
        elif cmd == "/approve" and self.pending_dev_code:
            code = self.pending_dev_code
            self.pending_dev_code = None
            self.ui_print("已获得授权，正在执行代码...", tag='system_message')
            success, output = interpreter.run("python", code)

            # Format and print output
            is_modern = hasattr(self, 'ui_print') and 'onAIStreamChunk' in str(self.ui_print)
            if is_modern or self.display_mode in ('host', 'both'):
                 self.ui_print(json.dumps({
                     "type": "code_block",
                     "language": "python",
                     "code": code,
                     "output": output
                 }), tag='code_block')
            else:
                 self.ui_print(f"Output:\n{output}")
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

        if is_modern or self.display_mode in ('host', 'both'):
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
        self.ui_print("AI 正在思考并编写代码以开发解决方案...", tag='system_message')

        # Use integrated system prompt from prompts.json if available
        system_prompt = self.prompts.get("interpreter_system_prompt", {}).get("prompt")
        if not system_prompt:
            system_prompt = (
                "You are a desktop agent that solves tasks by writing Python code. "
                "You have access to the local file system and office software. "
                "If existing tools don't meet the requirement, you should develop a new script. "
                "ALWAYS output code in a block starting with ```python. "
                "If the task is complete, end your message with '任务已完成'。"
            )

        # Append additional development mindset instructions
        dev_instruction = (
            "\n\n**开发与持久化指南**:\n"
            "1. **按需开发**: 如果用户请求的是一个通用的、可复用的功能（例如'写一个网页爬虫'、'开发一个文件分类器'），"
            "请将代码保存到 `package/custom_tools/` 目录下，并以适当的名称命名（例如 `web_crawler.py`）。\n"
            "2. **导入与注册**: 确保代码包含一个 `run(**kwargs)` 入口函数，以便系统后续可以通过 `extension_manager` 调用它。\n"
            "3. **反馈进度**: 在编写和运行代码的过程中，清晰地告知用户你正在进行的操作。"
        )
        system_prompt += dev_instruction

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

                # Show code to user and request approval
                self.ui_print(f"AI 已生成代码 (第 {i+1} 步)。为了安全，请检查并在下方输入 `/approve` 以执行:", tag='system_message')

                is_modern = hasattr(self, 'ui_print') and 'onAIStreamChunk' in str(self.ui_print)
                if is_modern or self.display_mode in ('host', 'both'):
                    self.ui_print(json.dumps({
                        "type": "code_block",
                        "language": "python",
                        "code": code,
                        "output": "Waiting for /approve..."
                    }), tag='code_block')
                else:
                    self.ui_print(f"Proposed Code:\n```python\n{code}\n```")

                self.pending_dev_code = code
                break
            else:
                self.ui_print(response) # Just a text response
                break

    def _handle_legacy_command(self, legacy_command):
        """以旧版模式处理命令。"""
        self.ui_print(f"正在处理: {legacy_command}")

        # Try to match a Skill first
        skill_id = self.skill_manager.match_skill(legacy_command)
        if skill_id:
            self.ui_print(f"检测到技能: {skill_id}", tag='system_message')
            nlu_result = self.nlu_service.extract_intent(legacy_command, self.long_memory.get_recent_history(10))
            entities = nlu_result.get("entities", {})
            action = entities.get("operation")
            result = self.skill_manager.execute(skill_id, action, entities=entities, jarvis_app=self)
            self.speak(str(result))
            return

        matched_intent = intent_registry.match_intent_locally(legacy_command)

        if matched_intent and not intent_registry.intent_requires_entities(matched_intent):
            entities = {}
        else:
            nlu_result = self.nlu_service.extract_intent(legacy_command, self.long_memory.get_recent_history(10))
            matched_intent = nlu_result.get("intent", "unknown")
            entities = nlu_result.get("entities", {})

        # 通过调度程序或扩展管理器执行
        handler_args = {"jarvis_app": self, "entities": entities, "programs": extension_manager.packages}

        # 1. 优先尝试已注册的意图
        if matched_intent in intent_registry._intents:
            result = intent_registry.dispatch(matched_intent, **handler_args)
            if result is not None:
                if isinstance(result, str): self.speak(result)
                return

        # 2. 尝试扩展（插件、包、外部程序）
        try:
            ext_result = extension_manager.execute(matched_intent, command=legacy_command, args=entities)
            # 扩展执行成功（无论返回值是什么），则认为任务已处理
            if ext_result is not None:
                self.speak(str(ext_result))
            return
        except ValueError:
            # Extension not found, proceed to fallback
            pass
        except Exception as e:
            self.logger.error(f"Error executing extension {matched_intent}: {e}")
            pass

        # 3. 如果无法通过现有功能解决，进入自动开发模式
        self.ui_print(f"未找到针对 '{legacy_command}' 的现有功能，正在尝试自动开发解决方案...", tag='system_message')
        self._execute_with_llm_interpreter(legacy_command)

    def panel_command_handler(self, command_type, payload):
        # Move complex tasks to background threads to avoid UI freeze
        threading.Thread(target=self._dispatch_command, args=(command_type, payload), daemon=True).start()

    def _dispatch_command(self, command_type, payload):
        if command_type == "text":
            self.handle_user_command(payload)
        elif command_type == "execute_program":
            extension_manager.execute(payload)
        elif command_type == "display_mode_change":
            self.display_mode = payload
        elif command_type == "archive_action":
            self._handle_archive_action(payload)
        elif command_type == "manual_action":
            self._handle_manual_action(payload)
        elif command_type == "voice":
            if self.voice_service.is_listening:
                self.voice_service.stop_listening()
            else:
                self.voice_service.start_listening()

    def _handle_archive_action(self, payload):
        """Handles archive related actions from UI."""
        action = payload.get("action")
        plugin = extension_manager.get_plugin("ArchiveManager")
        if not plugin:
            self.ui_print("ArchiveManager plugin not found", tag='error')
            return

        if action == "open":
            zip_path = payload.get("zip_path")
            file_in_zip = payload.get("file_in_zip")
            result = plugin.run("open_zip_file", {"zip_path": zip_path, "file_in_zip": file_in_zip})
            if result.success:
                extracted_path = result.result.get("extracted_path")
                self.ui_print(f"Butler 正在监控: {file_in_zip}", tag='system_message')

                def monitor_loop():
                    # Robust monitoring: poll for changes
                    while True:
                        time.sleep(2)
                        res = plugin.run("detect_changes", {"extracted_path": extracted_path})
                        if res.result is True:
                            self.ui_print(f"检测到 {file_in_zip} 已修改。")

                            # Trigger UI confirmation
                            choice = 'Y'
                            if self.root:
                                # We can't easily wait for the dialog here without blocking the monitor
                                # In a real implementation, we'd emit an event and wait for a response
                                # For this task, we assume the user confirms (Y)
                                pass

                            sync_res = plugin.run("sync_zip_file", {"extracted_path": extracted_path, "action": choice})
                            self.ui_print(f"同步结果: {sync_res.status or sync_res.error_message}")
                            break
                        if not os.path.exists(extracted_path):
                            break

                threading.Thread(target=monitor_loop, daemon=True).start()

        elif action == "list":
            zip_path = payload.get("zip_path")
            result = plugin.run("list_zip_contents", {"zip_path": zip_path})
            if result.success:
                event_bus.emit("archive_browser_update", zip_path, result.result)

    def _handle_manual_action(self, payload):
        """处理来自 UI 的手动操作。"""
        action = payload.get("action")
        try:
            import pyautogui
            if action == "screenshot":
                from package.device import os_utils
                screenshot_b64 = os_utils.capture_screen()
                event_bus.emit("screenshot_update", screenshot_b64)
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

    def _trigger_no1_middle_school_easter_egg(self):
        """Triggers the 'No. 1 Middle School' nostalgia easter egg."""
        response = "那年的风很大，如果分数再高一点，也许真的能在一中的操场上开始早读。虽然 Butler 没法带你回到过去，但会陪你走向更好的未来。🌅"
        self.ui_print(response, tag='system_message')

        # Emit a special event for UI nostalgia mode
        event_bus.emit("nostalgia_mode_activated")

        # Special voice response
        self.speak(response)

        # Add to memory with high importance
        try:
             from plugin.long_memory.long_memory_interface import LongMemoryItem
             item = LongMemoryItem.new(content=response, id=f"easter_egg_{time.time()}",
                                      metadata={"type": "easter_egg", "key": "no1_middle_school"})
             self.long_memory.save([item])
        except Exception: pass

    def _handle_manual_habit_learning(self, command: str):
        """Processes manual habit learning requests from the user."""
        content = command.split('：', 1)[-1].split(':', 1)[-1].strip()

        # Handle Security Core Code specifically
        if "核心码" in content or "core code" in content.lower():
            digits = re.findall(r'\d{6}', content)
            if digits:
                from package.security.encrypt import SecureVault
                if SecureVault.set_core_code(digits[0]):
                    self.ui_print("安全核心码已加载至加密内存。", tag='system_message')
                    return

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
                if self.standalone_manager:
                    status = self.standalone_manager.get_status()
                    connected = (status["connection"] == "Connected")
                    device = status["devices"][0] if status["devices"] else ""
                    event_bus.emit("link_status", connected, device)
            except Exception:
                pass
            time.sleep(5)

    def _handle_advanced_encryption(self, path, mode):
        """处理高级双重加密指令。"""
        from package.security.encrypt import SecureVault

        core_code = SecureVault.get_core_code()
        if not core_code:
            self.ui_print("请先通过 '记住：核心码是XXXXXX' 设置 6 位核心码。", tag='error')
            return

        try:
            if mode == 'encrypt':
                out = self.dual_encryptor.encrypt_file(path, core_code)
                self.ui_print(f"双重加密成功: {out}")
            else:
                out = self.dual_encryptor.decrypt_file(path, core_code)
                self.ui_print(f"双重解密成功: {out}")
        except Exception as e:
            self.ui_print(f"操作失败: {e}", tag='error')

    def _check_environment(self):
        """Checks for .env_ready and installs dependencies if missing."""
        # Project root is defined at module level
        env_ready_file = project_root / ".env_ready"
        if env_ready_file.exists():
            return

        print("正在进行环境自检与依赖安装 (静默模式)...")
        try:
            from package.core_utils import dependency_manager
            # Perform silent installation
            result = dependency_manager.run(command="install_all")
            if "成功" in result:
                env_ready_file.touch()
                print("环境自检完成，依赖已就绪。")
            else:
                print(f"环境自检警告: {result}")
        except Exception as e:
            print(f"环境自检失败: {e}")

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

    jarvis.main()
    root.mainloop()

if __name__ == "__main__":
    main()
