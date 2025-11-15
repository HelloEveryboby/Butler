from datetime import datetime
from package.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

class GreetingPlugin(AbstractPlugin):
    def __init__(self):
        self.name = "GreetingPlugin"
        self.chinese_name = "问候"
        self.description = "根据时间提供不同的问候"
        self.parameters = {}

    def valid(self) -> bool:
        return True

    def init(self, logging):
        self.logger = LogManager.get_logger(self.name)

    def get_name(self):
        return self.name

    def get_chinese_name(self):
        return self.chinese_name

    def get_description(self):
        return self.description

    def get_parameters(self):
        return self.parameters

    def on_startup(self):
        self.logger.info("GreetingPlugin started.")

    def on_shutdown(self):
        self.logger.info("GreetingPlugin shutdown.")

    def on_pause(self):
        self.logger.info("GreetingPlugin paused.")

    def on_resume(self):
        self.logger.info("GreetingPlugin resumed.")

    def get_commands(self) -> list[str]:
        return ["hello", "hi", "greeting", "你好"]

    def run(self, command: str, args: dict) -> PluginResult:
        current_hour = datetime.now().hour
        if 5 <= current_hour < 12:
            greeting = "早上好！"
        elif 12 <= current_hour < 18:
            greeting = "下午好！"
        else:
            greeting = "晚上好！"
        return PluginResult.new(greeting, False)
