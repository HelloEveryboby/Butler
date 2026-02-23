from datetime import datetime, timedelta
from package.core_utils.log_manager import LogManager
from abc import ABCMeta, abstractmethod
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

class CountdownPlugin(AbstractPlugin):
    def __init__(self):
        self.name = "倒计时"
        self.chinese_name = "倒计时插件程序"
        self.description = "执行倒计时功能，支持秒级设置"
        self._is_running = False # 添加运行状态标志
        self.parameters = {}

    def valid(self) -> bool:
        return True

    def init(self, logging):
        self.logging = LogManager.get_logger(self.name)

    def get_name(self):
        return self.name

    def get_chinese_name(self):
        return self.chinese_name

    def get_description(self):
        return self.description

    def get_parameters(self):
        return self.parameters

    def on_startup(self):
        logging.info("倒计时插件开始")

    def on_shutdown(self):
        logging.info("倒计时插件停止")

    def on_pause(self):
        logging.info("倒计时插件停止")

    def on_resume(self):
        logging.info("倒计时插件恢复")

    def get_commands(self) -> list[str]:
        return ["倒计时"]

    def run(self, takecommand: str, args: dict) -> PluginResult:
        import time
        from butler.main import Jarvis

        seconds = args.get("seconds")
        if not seconds:
            return PluginResult.new("无效的参数", False, error_message="Missing 'seconds' argument")

        try:
            seconds = int(seconds)
        except ValueError:
            return PluginResult.new("无效的参数", False, error_message="Invalid 'seconds' argument")

        end_time = datetime.now() + timedelta(seconds=seconds)
        while datetime.now() < end_time:
            if not self._is_running:
                return PluginResult.new("倒计时已取消", False)
            remaining_time = (end_time - datetime.now()).seconds
            Jarvis(None).speak(f"剩余时间: {remaining_time} 秒")
            time.sleep(1)
        logging.info("倒计时结束")
        return PluginResult.new("倒计时结束", False)
