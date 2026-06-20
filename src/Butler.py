import os
import sys
import time
import json
import re
import threading
import logging
from typing import Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from utils.environment import run_preflight_check
run_preflight_check()

from utils.logger import LogManager
from config.config import config_loader
from utils.core_utils.quota_manager import quota_manager
from utils.event_bus import event_bus
from api.gui.CommandPanel import CommandPanel
from models.data_storage import data_storage_manager
from services.extension_manager import extension_manager
from services.voice_service import VoiceService
from core.llm_client import NLUService
from services.habit_manager import habit_manager
from services.plugin_service import SkillManager
from services.task_manager import task_manager
from services.chat_service import message_bus
from services.team_manager import TeamManager
from services.battery_manager import battery_manager
from services.cron_scheduler import cron_scheduler
from services.dream_engine import DreamEngine
from core.local_nlu import LocalNLU
from services.proactive_agent import ProactiveAgent
from services.focus_mode import FocusMode
from api.sensing_api import init_sensing_api
from services.workflow_engine import WorkflowEngine
from core.self_healing import SelfHealing
from api.display_protocol import display_server
from api.usb_screen import USBScreen
from api.gui.config_wizard import show_config_wizard_if_needed
from utils.asset_downloader import download_essential_assets
from core.resource_manager import ResourceManager, PerformanceMode
from core.memory.memory_engine import (
    RedisLongMemory, ZvecLongMemory, SQLiteLongMemory,
    LongMemoryItem, UnifiedMemoryEngine, hybrid_memory_manager
)
from core.agent import intent_registry
from core import legacy_commands
from services.interpreter import interpreter
from core.hybrid_link import HybridLinkClient
from api.runner_server import RunnerServer
from api.hal.device.standalone_manager import StandaloneManager

class Butler:
    def __init__(self, root=None, usb_screen=None, headless=False):
        self.root = root
        self.usb_screen = usb_screen
        self.resource_manager = ResourceManager()
        self.display_mode = 'host'
        self.running = True
        self.pending_dev_code = None
        self._check_environment()
        load_dotenv()
        self.logger = LogManager.get_logger(__name__)
        self.config = config_loader._config
        self.prompts = self._load_json_resource("prompts.json")
        self.program_mapping = self._load_json_resource("program_mapping.json")
        self._initialize_long_memory()
        self.nlu_service = NLUService(config_loader.get("api.deepseek.key"), self.prompts)
        self.voice_service = VoiceService(self.handle_user_command, self.ui_print, self._on_voice_status_change)
        self.skill_manager = SkillManager()
        self.skill_manager.load_skills()
        self.skill_manager.start_monitoring()
        self.local_nlu = LocalNLU(self.skill_manager)
        self.team_manager = TeamManager.get_instance(self)
        battery_manager.res_mgr = self.resource_manager
        self.dream_engine = DreamEngine(self)
        self.proactive_agent = ProactiveAgent(self)
        self.focus_mode = FocusMode(self)
        self.sensing_api = init_sensing_api(self)
        self.workflow_engine = WorkflowEngine(self)
        self.self_healing = SelfHealing(self)
        display_server.start()
        self._setup_kairos_tasks()
        voice_mode = self.config.get("voice", {}).get("mode", "offline")
        self.voice_service.set_voice_mode(voice_mode)
        self.sysutil = HybridLinkClient(
            executable_path=str(project_root / "programs/hybrid_sysutil/sysutil"),
            fallback_enabled=True
        )
        self.sysutil.start()
        self.standalone_manager = StandaloneManager(self)
        self.standalone_manager.start()
        runner_config = self.config.get("runner_server", {})
        self.runner_server = RunnerServer(
            host=runner_config.get("host", "0.0.0.0"),
            port=runner_config.get("port", 8000),
            token=runner_config.get("token", "BUTLER_TOKEN_PLACEHOLDER")
        )
        self.runner_server.register_event_callback(self._on_runner_event)
        self.runner_server.start()
        from utils.security.encrypt import DualLayerEncryptor
        self.dual_encryptor = DualLayerEncryptor()
        self.ui_suggested = False
        self.waiting_for_ui_confirm = False
        self._interaction_count = 0

    def _load_json_resource(self, filename):
        path = Path(__file__).parent / "core" / filename
        try:
            with path.open('r', encoding='utf-8') as f: return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load {filename}: {e}")
            return {}

    def _initialize_long_memory(self):
        api_key = config_loader.get("api.deepseek.key")
        backend = None
        try:
            if api_key:
                backend = RedisLongMemory(api_key=api_key)
                backend.init(self.logger)
        except Exception: pass
        if not backend:
            try:
                import zvec
                if api_key:
                    backend = ZvecLongMemory(api_key=api_key)
                    backend.init(self.logger)
            except Exception: pass
        if not backend:
            backend = SQLiteLongMemory()
            backend.init(self.logger)
        self.long_memory = UnifiedMemoryEngine(backend, hybrid_memory_manager)
        self.long_memory.init(self.logger)

    def _on_voice_status_change(self, is_listening):
        event_bus.emit("voice_status", is_listening)

    def _setup_kairos_tasks(self):
        cron_scheduler.add_task("dream", interval_seconds=3600*4, permanent=True)
        event_bus.on("cron:dream", self.dream_engine.dream)
        cron_scheduler.add_task("proactive-tick", interval_seconds=3600, permanent=True)
        event_bus.on("cron:proactive-tick", self.proactive_agent.tick)
        event_bus.on("workflow_next", self.workflow_engine.execute_step)
        cron_scheduler.start()

    def _on_runner_event(self, runner_id: str, data: Dict[str, Any]):
        msg_type = data.get("status")
        if msg_type == "screenshot":
            event_bus.emit("screenshot_update", data.get("data"))
        elif msg_type == "sys":
            self.ui_print(f"运行节点 '{runner_id}' 系统信息: {data.get('data')}", tag='system_message')
        elif msg_type == "ok":
            self.ui_print(f"运行节点 '{runner_id}' 反馈: {data.get('data')}", tag='system_message')
        elif msg_type == "fail":
            self.ui_print(f"运行节点 '{runner_id}' 错误: {data.get('error')}", tag='error')

    def ui_print(self, message, tag='ai_response', response_id=None):
        lvl = logging.ERROR if tag == 'error' else logging.INFO
        self.logger.log(lvl, f"[UI:{tag}] {message}")
        if tag == 'ai_response_start': tag = 'ai_response'
        def do_emit():
            if self.display_mode in ('host', 'both'): event_bus.emit("ui_output", message, tag, response_id)
            if self.display_mode in ('usb', 'both'):
                if self.usb_screen: self.usb_screen.display(message, clear_screen=True)
                display_server.push_update({"type": "text", "content": message, "tag": tag})
        if self.root: self.root.after(0, do_emit)
        else: do_emit()

    def speak(self, text):
        self.ui_print(text, tag='ai_response')
        self.long_memory.save_fact(text, metadata={"role": "assistant"})
        self.voice_service.speak(text)

    def handle_user_command(self, command, programs=None):
        if not command: return
        cmd = command.strip()
        self.proactive_agent.update_activity()
        if quota_manager.halt_system and not quota_manager.check_quota():
            self.ui_print("⚠️ 系统已锁定: API 额度已耗尽。", tag='error')
            return
        self.long_memory.logs.add_daily_log(f"User: {cmd}")
        if "一中" in cmd and "早读" in cmd:
            self._trigger_no1_middle_school_easter_egg()
            return
        if self.waiting_for_ui_confirm:
            if any(word in cmd.lower() for word in ['是', '好', '打开', 'yes']):
                self.waiting_for_ui_confirm = False
                self._activate_full_ui()
                return
        if cmd.startswith("/voice-mode "):
            mode = cmd.split()[1].lower()
            self.voice_service.set_voice_mode(mode)
        elif cmd == "/cleanup":
            from utils.file_system import data_recycler
            self.ui_print(data_recycler.run())
        elif cmd.startswith("/theme "):
            parts = cmd.split()
            if len(parts) > 1:
                theme = parts[1].lower()
                config_loader.set("display.theme", theme)
                event_bus.emit("theme_change", theme)
        elif cmd.startswith("/py "):
            self._execute_with_interpreter("python", cmd[4:])
        elif cmd == "/tasks":
            self.ui_print(str(task_manager.list_business_tasks()), tag='system_message')
        elif cmd == "/approve" and self.pending_dev_code:
            code = self.pending_dev_code
            self.pending_dev_code = None
            success, output = interpreter.run("python", code)
            self.ui_print(output, tag='code_block')
        else:
            threading.Thread(target=self._autonomous_agent_loop, args=(cmd,), daemon=True).start()

    def _execute_with_interpreter(self, lang, code):
        success, output = interpreter.run(lang, code)
        self.ui_print(output, tag='code_block')

    def _trigger_no1_middle_school_easter_egg(self):
        response = "那年的风很大... 虽然 Butler 没法带你回到过去，但会陪你走向更好的未来。🌅"
        self.ui_print(response, tag='system_message')
        event_bus.emit("nostalgia_mode_activated")
        self.speak(response)

    def main(self):
        download_essential_assets()
        self.voice_service.start_listening()
        self.speak("Butler 已启动并就绪")
        while self.running: time.sleep(1)

    def _check_environment(self):
        pass

    def _autonomous_agent_loop(self, command: str):
        history = self.long_memory.get_recent_history(10)
        self.ui_print(f"Butler 正在思考...", tag='system_message')
        nlu_result = self.nlu_service.extract_intent(command, history=history)
        intent = nlu_result.get("intent", "unknown")
        if intent == "unknown":
            resp = self.nlu_service.ask_llm(command, history=history)
            self.speak(resp)
        else:
            self.ui_print(f"执行意图: {intent}", tag='system_message')
            output = self.skill_manager.execute(intent, "run", butler_app=self)
            self.speak(str(output))

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    usb_screen = USBScreen(40, 8)
    if args.headless:
        butler = Butler(None, usb_screen, headless=True)
        butler.main()
        return
    import tkinter as tk
    root = tk.Tk()
    root.title("Butler 助手")
    butler = Butler(root, usb_screen, headless=False)
    butler.main()
    root.mainloop()

if __name__ == "__main__": main()
