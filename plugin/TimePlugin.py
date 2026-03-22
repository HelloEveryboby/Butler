import datetime
from package.core_utils.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

class TimePlugin(AbstractPlugin):
    def __init__(self):
        self.name = "TimePlugin"
        self.chinese_name = "时间查询"
        self.description = "查询当前时间"
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
        self.logger.info("TimePlugin started.")

    def on_shutdown(self):
        self.logger.info("TimePlugin shutdown.")

    def on_pause(self):
        self.logger.info("TimePlugin paused.")

    def on_resume(self):
        self.logger.info("TimePlugin resumed.")

    def get_commands(self) -> list[str]:
        return ["时间", "几点了"]

    def run(self, takecommand: str, args: dict) -> PluginResult:
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        return PluginResult.new(f"现在是北京时间{current_time}", False)
