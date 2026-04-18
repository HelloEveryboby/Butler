import os
import sys
import time
import datetime
import json
import re
import threading
import logging
from typing import Dict, Any, List
import tempfile
import shutil
import tkinter as tk
from pathlib import Path
from dotenv import load_dotenv

# Add project root and local lib to sys.path to support portable/local dependency installation
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

lib_path = project_root / "lib_external"
if lib_path.exists():
    import site
    site.addsitedir(str(lib_path))

from butler.core.environment import run_preflight_check
# Run environment check as early as possible
run_preflight_check()

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
from butler.core.task_manager import task_manager
from butler.core.message_bus import message_bus
from butler.core.team_manager import TeamManager
from butler.core.battery_manager import battery_manager
from butler.core.cron_scheduler import cron_scheduler
from butler.core.dream_engine import DreamEngine
from butler.core.proactive_agent import ProactiveAgent
from butler.core.focus_mode import FocusMode
from butler.core.sensing_api import init_sensing_api
from butler.core.display_protocol import display_server
from butler.usb_screen import USBScreen
from butler.resource_manager import ResourceManager, PerformanceMode
from plugin.memory_engine import (
    RedisLongMemory, ZvecLongMemory, SQLiteLongMemory,
    LongMemoryItem, UnifiedMemoryEngine, hybrid_memory_manager
)
from butler.core.intent_dispatcher import intent_registry
from butler.core import legacy_commands # Ensure legacy intents are registered
from butler.interpreter import interpreter
from butler.core.hybrid_link import HybridLinkClient
from butler.core.runner_server import RunnerServer
from package.device.standalone_manager import StandaloneManager

class Jarvis:
    def __init__(self, root=None, usb_screen=None):
        self.root = root
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
        self.team_manager = TeamManager.get_instance(self)

        # Inject resource manager into battery manager for mode awareness
        battery_manager.res_mgr = self.resource_manager

        # Initialize KAIROS Suite
        self.dream_engine = DreamEngine(self)
        self.proactive_agent = ProactiveAgent(self)
        self.focus_mode = FocusMode(self)
        self.sensing_api = init_sensing_api(self)
        display_server.start()
        self._setup_kairos_tasks()
        
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
        """初始化统一记忆引擎。"""
        api_key = config_loader.get("api.deepseek.key")
        backend = None

        # 1. 尝试 Redis
        try:
            if api_key:
                backend = RedisLongMemory(api_key=api_key)
                backend.init(self.logger)
        except Exception as e:
            self.logger.warning(f"无法初始化 RedisLongMemory: {e}")

        # 2. 尝试 Zvec
        if not backend:
            try:
                import zvec
                if api_key:
                    backend = ZvecLongMemory(api_key=api_key)
                    backend.init(self.logger)
            except Exception as e2:
                self.logger.error(f"无法初始化 ZvecLongMemory: {e2}")

        # 3. 降级到 SQLite
        if not backend:
            self.logger.info("降级到 SQLiteLongMemory...")
            backend = SQLiteLongMemory()
            backend.init(self.logger)

        # 封装为统一记忆引擎 (Unified Memory Engine)
        self.long_memory = UnifiedMemoryEngine(backend, hybrid_memory_manager)
        self.long_memory.init(self.logger)

    def _on_voice_status_change(self, is_listening):
        event_bus.emit("voice_status", is_listening)

    def _setup_kairos_tasks(self):
        """配置 KAIROS 自动化任务"""
        # 1. 记忆整合 (每 24 小时检查一次)
        cron_scheduler.add_task("dream", interval_seconds=3600*4, permanent=True)
        event_bus.on("cron:dream", self.dream_engine.dream)

        # 2. 主动模式 Tick (每 1 小时检查一次)
        cron_scheduler.add_task("proactive-tick", interval_seconds=3600, permanent=True)
        event_bus.on("cron:proactive-tick", self.proactive_agent.tick)

        # 启动调度器
        cron_scheduler.start()

    def _on_runner_event(self, runner_id: str, data: Dict[str, Any]):
        """Handles incoming messages from remote runners."""
        msg_type = data.get("status")
        if msg_type == "screenshot":
            event_bus.emit("screenshot_update", data.get("data"))
            self.ui_print(f"收到来自运行节点 '{runner_id}' 的屏幕截图。", tag='system_message')
        elif msg_type == "sys":
            self.ui_print(f"运行节点 '{runner_id}' 系统信息: {data.get('data')}", tag='system_message')
        elif msg_type == "ok":
            self.ui_print(f"运行节点 '{runner_id}' 反馈: {data.get('data')}", tag='system_message')
        elif msg_type == "fail":
            self.ui_print(f"运行节点 '{runner_id}' 错误: {data.get('error')}", tag='error')

    def ui_print(self, message, tag='ai_response', response_id=None):
        # Log all UI output to structured log
        lvl = logging.ERROR if tag == 'error' else logging.INFO
        self.logger.log(lvl, f"[UI:{tag}] {message}")

        if tag == 'ai_response_start':
            tag = 'ai_response'

        # Internal emit helper to ensure UI operations happen in the main thread
        def do_emit():
            if self.display_mode in ('host', 'both'):
                event_bus.emit("ui_output", message, tag, response_id)

            # Sync to hardware displays
            if self.display_mode in ('usb', 'both'):
                if self.usb_screen:
                    self.usb_screen.display(message, clear_screen=True)
                display_server.push_update({"type": "text", "content": message, "tag": tag})

        if self.root:
            self.root.after(0, do_emit)
        else:
            do_emit()

    def speak(self, text):
        """朗读给定的文本并在 UI 中打印。同时利用统一引擎记录至事实数据库和日志系统。"""
        self.ui_print(text, tag='ai_response')

        # 使用统一引擎的一键存储功能实现数据共享
        self.long_memory.save_fact(text, metadata={"role": "assistant"})

        self.voice_service.speak(text)

    def handle_user_command(self, command, programs=None):
        if not command: return
        cmd = command.strip()

        # Notify proactive agent of activity
        self.proactive_agent.update_activity()

        # Quota Check (Global Halt)
        if quota_manager.halt_system and not quota_manager.check_quota():
            report = quota_manager.get_usage_report()
            msg = f"⚠️ 系统已锁定: API 额度已耗尽。"
            self.ui_print(msg, tag='error')
            self.voice_service.speak("系统额度已耗尽，已停止所有操作。")
            return

        # 利用统一引擎记录用户交互（日志 + 事实同步）
        self.long_memory.logs.add_daily_log(f"User: {cmd}")

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
                    if theme == 'dark': theme = 'apple'
                    if theme == 'light': theme = 'google'
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
        elif cmd == "/kairos":
            percent, plugged = battery_manager.get_status()
            mode = self.resource_manager.get_mode().value
            status = (
                f"🌟 Butler KAIROS 状态:\n"
                f"- 性能模式: {mode}\n"
                f"- 电池电量: {percent}% ({'已插电' if plugged else '电池供电'})\n"
                f"- 节流状态: {'节流中' if battery_manager.should_throttle() else '全速'}\n"
                f"- 响应倍数: {battery_manager.get_sleep_multiplier()}x\n"
                f"- 协作队友: {len([m for m in self.team_manager.members if m['status'] != 'shutdown'])} 个活跃\n"
                f"- 自动做梦: 已就绪"
            )
            self.ui_print(status, tag='system_message')
        elif cmd.startswith("/performance "):
            mode_str = cmd.split()[1].lower()
            if mode_str == "high":
                self.resource_manager.set_mode(PerformanceMode.HIGH_PERFORMANCE)
                self.ui_print("性能模式已切换至: 高性能 (HIGH_PERFORMANCE)")
            elif mode_str == "eco":
                self.resource_manager.set_mode(PerformanceMode.ECO)
                self.ui_print("性能模式已切换至: 低功耗 (ECO)")
            elif mode_str == "normal":
                self.resource_manager.set_mode(PerformanceMode.NORMAL)
                self.ui_print("性能模式已切换至: 标准 (NORMAL)")
            else:
                self.ui_print("无效模式。可选: high, eco, normal", tag='error')
        elif cmd == "/dream":
            self.ui_print("正在手动启动做梦引擎...", tag='system_message')
            threading.Thread(target=self.dream_engine.dream, daemon=True).start()
        elif cmd.startswith("/focus"):
            parts = cmd.split()
            duration = int(parts[1]) if len(parts) > 1 else 25
            msg = self.focus_mode.start(duration)
            self.ui_print(msg, tag='system_message')
        elif cmd == "/focus-stop":
            msg = self.focus_mode.stop()
            self.ui_print(msg, tag='system_message')
        elif cmd == "/tasks":
            tasks = task_manager.list_business_tasks()
            report = "📋 **持久化任务看板**:\n"
            if not tasks:
                report += "当前无任务。"
            for t in tasks:
                m = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
                owner = f" @{t['owner']}" if t.get("owner") else ""
                report += f"{m} #{t['id']}: {t['subject']}{owner}\n"
            self.ui_print(report, tag='system_message')
        elif cmd == "/team":
            self.ui_print(self.team_manager.list_teammates(), tag='system_message')
        elif cmd == "/approve" and self.pending_dev_code:
            code = self.pending_dev_code
            self.pending_dev_code = None
            self.ui_print("已获得授权，正在执行代码...", tag='system_message')
            success, output = interpreter.run("python", code)
            self.ui_print(json.dumps({"type": "code_block", "language": "python", "code": code, "output": output}), tag='code_block')
        elif cmd.startswith("记住这一点：") or cmd.startswith("记住：") or cmd.startswith("Remember this:"):
            self._handle_manual_habit_learning(cmd)
        else:
            # Entry point for the new Autonomous Agent Loop
            threading.Thread(target=self._autonomous_agent_loop, args=(cmd,), daemon=True).start()

        self._interaction_count += 1
        if self._interaction_count % 3 == 0 or self._should_use_interpreter(cmd):
            threading.Thread(target=self._reflect_on_interaction, daemon=True).start()

    def _should_use_interpreter(self, command):
        keywords = ['文件', '计算', '报销', '总结', '文件夹', 'excel', 'word', 'pdf', '分析']
        return any(k in command.lower() for k in keywords)

    def _execute_with_interpreter(self, lang, code):
        self.ui_print(f"Executing {lang} code...", tag='system_message')
        success, output = interpreter.run(lang, code)
        self.ui_print(json.dumps({"type": "code_block", "language": lang, "code": code, "output": output}), tag='code_block')

    def _execute_with_llm_interpreter(self, command):
        """Uses LLM to generate and run code (Open Interpreter style)."""
        self.ui_print("AI 正在思考并编写代码以开发解决方案...", tag='system_message')
        system_prompt = self.prompts.get("interpreter_system_prompt", {}).get("prompt")
        if not system_prompt:
            system_prompt = (
                "You are a desktop agent that solves tasks by writing Python code. "
                "ALWAYS output code in a block starting with ```python. "
                "If the task is complete, end your message with '任务已完成'。"
            )
        dev_instruction = (
            "\n\n**开发与持久化指南**:\n"
            "1. **按需开发**: 如果用户请求的是一个通用的功能，请将代码保存到 `package/custom_tools/` 目录下。\n"
            "2. **导入与注册**: 确保代码包含一个 `run(**kwargs)` 入口函数。\n"
            "3. **反馈进度**: 在编写和运行代码的过程中，清晰地告知用户你正在进行的操作。"
        )
        system_prompt += dev_instruction

        history = self.long_memory.get_recent_history(10)
        max_iterations = 5
        current_input = command

        for i in range(max_iterations):
            prompt = f"{system_prompt}\n\nUser Question: {current_input}"
            response = self.nlu_service.ask_llm(prompt, history)
            code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
            if code_match:
                code = code_match.group(1)
                self.ui_print(f"AI 已生成代码 (第 {i+1} 步)。为了安全，请检查并在下方输入 `/approve` 以执行:", tag='system_message')
                self.ui_print(json.dumps({"type": "code_block", "language": "python", "code": code, "output": "Waiting for /approve..."}), tag='code_block')
                self.pending_dev_code = code
                break
            else:
                self.ui_print(response)
                break

    def _handle_legacy_command(self, legacy_command):
        """以旧版模式处理命令。"""
        self.ui_print(f"正在处理: {legacy_command}")
        skill_id = self.skill_manager.match_skill(legacy_command)
        if skill_id:
            nlu_result = self.nlu_service.extract_intent(legacy_command, self.long_memory.get_recent_history(10))
            entities = nlu_result.get("entities", {})
            result = self.skill_manager.execute(skill_id, entities.get("operation"), entities=entities, jarvis_app=self)
            self.speak(str(result))
            return

        matched_intent = intent_registry.match_intent_locally(legacy_command)
        if not matched_intent:
            nlu_result = self.nlu_service.extract_intent(legacy_command, self.long_memory.get_recent_history(10))
            matched_intent = nlu_result.get("intent", "unknown")
            entities = nlu_result.get("entities", {})
        else:
            entities = {}

        handler_args = {"jarvis_app": self, "entities": entities, "programs": extension_manager.packages}
        if matched_intent in intent_registry._intents:
            result = intent_registry.dispatch(matched_intent, **handler_args)
            if result is not None:
                if isinstance(result, str): self.speak(result)
                return
        try:
            ext_result = extension_manager.execute(matched_intent, command=legacy_command, args=entities)
            if ext_result is not None: self.speak(str(ext_result))
            return
        except ValueError:
            pass
        self._execute_with_llm_interpreter(legacy_command)

    def panel_command_handler(self, command_type, payload):
        threading.Thread(target=self._dispatch_command, args=(command_type, payload), daemon=True).start()

    def _dispatch_command(self, command_type, payload):
        if command_type == "text": self.handle_user_command(payload)
        elif command_type == "execute_program": extension_manager.execute(payload)
        elif command_type == "display_mode_change": self.display_mode = payload
        elif command_type == "archive_action": self._handle_archive_action(payload)
        elif command_type == "manual_action": self._handle_manual_action(payload)
        elif command_type == "voice":
            if self.voice_service.is_listening: self.voice_service.stop_listening()
            else: self.voice_service.start_listening()

    def _handle_archive_action(self, payload):
        action = payload.get("action")
        plugin = extension_manager.get_plugin("ArchiveManager")
        if not plugin: return
        if action == "open":
            zip_path, file_in_zip = payload.get("zip_path"), payload.get("file_in_zip")
            result = plugin.run("open_zip_file", {"zip_path": zip_path, "file_in_zip": file_in_zip})
            if result.success:
                extracted_path = result.result.get("extracted_path")
                def monitor_loop():
                    while True:
                        time.sleep(2)
                        res = plugin.run("detect_changes", {"extracted_path": extracted_path})
                        if res.result is True:
                            plugin.run("sync_zip_file", {"extracted_path": extracted_path, "action": 'Y'})
                            break
                        if not os.path.exists(extracted_path): break
                threading.Thread(target=monitor_loop, daemon=True).start()
        elif action == "list":
            result = plugin.run("list_zip_contents", {"zip_path": payload.get("zip_path")})
            if result.success: event_bus.emit("archive_browser_update", payload.get("zip_path"), result.result)

    def _handle_manual_action(self, payload):
        action = payload.get("action")
        try:
            import pyautogui
            if action == "screenshot":
                from package.device import os_utils
                event_bus.emit("screenshot_update", os_utils.capture_screen())
            elif action == "left_click":
                coord = payload.get("coordinate")
                if coord: pyautogui.click(coord[0], coord[1])
                else: pyautogui.click()
            elif action == "type":
                if payload.get("text"): pyautogui.write(payload.get("text"))
        except Exception as e: self.logger.error(f"Manual action error: {e}")

    def _reflect_on_interaction(self):
        try:
            history = self.long_memory.get_recent_history(4)
            reflection_prompt = (
                "你是一个观察敏锐且追求默契的助手。请深度分析以下对话，提取用户的'隐形习惯'与'协作默契点'。\n"
                "特别关注以下细节：\n"
                "1. **快捷需求**: 用户是否有特定的缩写、口头禅或模糊指令？\n"
                "2. **工具偏好**: 用户是否在处理某类任务时总是倾向于某个特定工具或参数？\n"
                "3. **雷区与痛点**: 用户曾纠正过你什么？用户不喜欢什么样的反馈？\n"
                "4. **工作流**: 用户的任务通常包含哪些固定的前后置步骤？\n\n"
                "请返回一个 JSON 格式的对象，包含以下可选键：\n"
                "- `preferences`: 字典。记录明确偏好和默契点。\n"
                "- `interaction_style`: 字符串。用户的沟通风格及情感偏好。\n"
                "- `common_tasks`: 列表。用户的高频任务描述。\n"
                "- `preferred_tools`: 列表。用户偏好的工具名。\n\n"
                "只返回 JSON，确保简洁精准。如果没有新发现，请返回空对象 {}。"
            )
            response = self.nlu_service.ask_llm(reflection_prompt, history, use_habit=False)
            json_match = re.search(r"(\{.*\})", response, re.DOTALL)
            if json_match:
                insights = json.loads(json_match.group(1))
                if insights: habit_manager.update_from_reflection(insights)
        except Exception as e: self.logger.error(f"Reflection failed: {e}")

    def _trigger_no1_middle_school_easter_egg(self):
        """Triggers the 'No. 1 Middle School' nostalgia easter egg."""
        response = "那年的风很大，如果分数再高一点，也许真的能在一中的操场上开始早读。虽然 Butler 没法带你回到过去，但会陪你走向更好的未来。🌅"
        self.ui_print(response, tag='system_message')
        event_bus.emit("nostalgia_mode_activated")
        self.speak(response)
        try:
             item = LongMemoryItem.new(content=response, id=f"easter_egg_{time.time()}",
                                      metadata={"type": "easter_egg", "key": "no1_middle_school"})
             self.long_memory.save([item])
        except Exception: pass

    def _handle_manual_habit_learning(self, command: str):
        content = command.split('：', 1)[-1].split(':', 1)[-1].strip()
        if "核心码" in content:
            digits = re.findall(r'\d{6}', content)
            if digits:
                from package.security.encrypt import SecureVault
                if SecureVault.set_core_code(digits[0]):
                    self.ui_print("安全核心码已加载至加密内存。", tag='system_message'); return
        self.ui_print(f"正在将 '{content}' 存入核心记忆...", tag='system_message')
        try:
            response = self.nlu_service.ask_llm(f"Convert to habit JSON: {content}", [], use_habit=False)
            json_match = re.search(r"(\{.*\})", response, re.DOTALL)
            if json_match:
                habit_manager.update_from_reflection(json.loads(json_match.group(1)))
                self.ui_print("核心记忆已更新。", tag='system_message')
            else:
                habit_manager.update_preference("custom_note", content)
                self.ui_print("已作为自定义备注存入画像。", tag='system_message')
        except Exception as e: self.logger.error(f"Manual learning failed: {e}")

    def _handle_exit(self):
        self.speak("再见"); self.running = False; self.voice_service.stop_listening()
        if self.root: self.root.quit()

    def main(self):
        self._cleanup_temp_files(); self.voice_service.start_listening()
        try:
            from package.core_utils.autonomous_switch import AutonomousSwitch
            AutonomousSwitch().start(background=True)
        except Exception: pass
        self.speak("Jarvis 已启动并就绪")
        threading.Thread(target=self._update_ui_loop, daemon=True).start()

    def suggest_ui_activation(self):
        if not self.ui_suggested and self.display_mode in ('usb', 'host') and self.root is None:
             self.speak("检测到可用屏幕。是否需要开启图形界面程序？")
             self.waiting_for_ui_confirm = True; self.ui_suggested = True

    def _activate_full_ui(self):
        if self.root: return
        def launch():
            try:
                self.speak("提示：在当前终端环境下直接启动 Tkinter 可能需要有效的 X11/Wayland 转发。")
                self.display_mode = 'host'
            except Exception: pass
        threading.Thread(target=launch, daemon=True).start()

    def _update_ui_loop(self):
        while self.running:
            try:
                if self.standalone_manager:
                    status = self.standalone_manager.get_status()
                    event_bus.emit("link_status", status["connection"] == "Connected", status["devices"][0] if status["devices"] else "")
            except Exception: pass

            # KAIROS Nap: 根据电池状态动态调整 UI 刷新频率
            nap_time = 5 * battery_manager.get_sleep_multiplier()
            time.sleep(nap_time)

    def _handle_advanced_encryption(self, path, mode):
        from package.security.encrypt import SecureVault
        code = SecureVault.get_core_code()
        if not code:
            self.ui_print("请先设置 6 位核心码。", tag='error'); return
        try:
            out = self.dual_encryptor.encrypt_file(path, code) if mode == 'encrypt' else self.dual_encryptor.decrypt_file(path, code)
            self.ui_print(f"成功: {out}")
        except Exception as e: self.ui_print(f"失败: {e}", tag='error')

    def _check_environment(self):
        if (project_root / ".env_ready").exists(): return
        try:
            from package.core_utils import dependency_manager
            if "成功" in dependency_manager.run(command="install_all"): (project_root / ".env_ready").touch()
        except Exception: pass

    def _cleanup_temp_files(self):
        temp_dir = tempfile.gettempdir()
        for f in os.listdir(temp_dir):
            if f.startswith("jarvis_temp_"):
                try:
                    path = os.path.join(temp_dir, f)
                    if os.path.isfile(path): os.remove(path)
                    else: shutil.rmtree(path)
                except Exception: pass
        try:
            from package import data_recycler
            data_recycler.run()
        except Exception: pass

    def _autonomous_agent_loop(self, command: str):
        """Autonomous agent loop with tool use and persistence."""
        history = self.long_memory.get_recent_history(10)
        messages = []
        for h in history:
            role = h.metadata.get('role', 'user') if hasattr(h, 'metadata') else 'user'
            content = h.content if hasattr(h, 'content') else str(h)
            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": command})

        max_turns = 10
        for turn in range(max_turns):
            # 0. Micro-compression of results
            messages = self.nlu_service.micro_compact(messages)

            # 1. Check Inbox
            inbox = message_bus.read_inbox("lead")
            if inbox:
                messages.append({"role": "user", "content": f"<inbox>{json.dumps(inbox, ensure_ascii=False)}</inbox>"})

            # 2. Token Check & Compression
            if self.nlu_service.estimate_tokens(messages) > 3000:
                messages = self.nlu_service.compress_history(messages)

            # 3. LLM Call (Intent & Strategy)
            self.ui_print(f"Butler 正在思考 (第 {turn+1} 轮)...", tag='system_message')
            nlu_result = self.nlu_service.extract_intent(messages[-1]["content"], history=messages[:-1])
            intent = nlu_result.get("intent", "unknown")
            entities = nlu_result.get("entities", {})

            if intent == "unknown":
                # Fallback to general chat if no clear tool intent
                resp = self.nlu_service.ask_llm(messages[-1]["content"], history=messages[:-1])
                self.speak(resp)
                break

            # 4. Tool Dispatch
            self.ui_print(f"执行意图: {intent}", tag='system_message')
            output = ""

            # Persistent Task Tools
            if intent == "task_create":
                output = task_manager.create_business_task(entities.get("subject", "未命名任务"), entities.get("description", ""))
            elif intent == "task_update":
                output = task_manager.update_business_task(int(entities.get("task_id", 0)), entities.get("status"), entities.get("add_blocked_by"), entities.get("remove_blocked_by"))
            elif intent == "task_list":
                output = task_manager.list_business_tasks()
            elif intent == "claim_task":
                output = task_manager.claim_business_task(int(entities.get("task_id", 0)), "lead")

            # Team Tools
            elif intent == "spawn_teammate":
                output = self.team_manager.spawn_teammate(entities.get("name"), entities.get("role"), entities.get("prompt"))
            elif intent == "list_teammates":
                output = self.team_manager.list_teammates()
            elif intent == "send_message":
                output = message_bus.send("lead", entities.get("to"), entities.get("content"), entities.get("msg_type", "message"))
            elif intent == "read_inbox":
                output = message_bus.read_inbox("lead")

            # Context Tools
            elif intent == "compress":
                messages = self.nlu_service.compress_history(messages)
                output = "Context compressed."

            # Legacy & Interpreter Fallbacks
            elif intent == "xlsx_expert" or intent == "pdf_assistant" or self._should_use_interpreter(command):
                # Call interpreter for code-based tasks
                self._execute_with_llm_interpreter(command)
                break
            else:
                # Handle via legacy skill/extension system
                skill_id = self.skill_manager.match_skill(command)
                if skill_id:
                    output = self.skill_manager.execute(skill_id, entities.get("operation"), entities=entities, jarvis_app=self)
                else:
                    output = extension_manager.execute(intent, command=command, args=entities)

            # 5. Feedback Loop
            self.ui_print(f"工具输出: {str(output)[:200]}...", tag='system_message')
            messages.append({"role": "assistant", "content": f"I used tool '{intent}' and got: {json.dumps(output, ensure_ascii=False)}"})

            # If the tool result looks like a final answer or we've reached a conclusion
            if "任务已完成" in str(output) or turn == max_turns - 1:
                final_resp = self.nlu_service.ask_llm("请基于以上工具执行结果，给用户一个最终答复。", history=messages)
                self.speak(final_resp)
                break
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--classic", "--admin", action="store_true", dest="classic")
    args = parser.parse_args()
    usb_screen = USBScreen(40, 8)
    if args.headless:
        jarvis = Jarvis(None, usb_screen); jarvis.main()
        while jarvis.running: time.sleep(1)
        return
    if not args.classic:
        try:
            from frontend.program import modern_app
            modern_app.main(); return
        except Exception: pass
    root = tk.Tk(); root.title("Jarvis 助手 [管理模式]")
    jarvis = Jarvis(root, usb_screen)
    all_tools = {t['name']: t.get('path', t.get('module')) for t in extension_manager.get_all_tools()}
    panel = CommandPanel(root, program_mapping=jarvis.program_mapping, programs=all_tools, command_callback=jarvis.panel_command_handler)
    panel.pack(fill=tk.BOTH, expand=True)
    jarvis.main(); root.mainloop()

if __name__ == "__main__": main()
