from package.core_utils.log_manager import LogManager

from plugin.plugin_interface import AbstractPlugin, PluginResult

logger = LogManager.get_logger(__name__)

class ClearRecentMemoryPlugin(AbstractPlugin):
    def valid(self) -> bool:
        return True

    #  在 init 方法中初始化类内部的日志记录器
    def init(self, logging):
        self.logging = LogManager.get_logger(self.name)

    def get_name(self):
        return "clear_recent_memory"

    def get_chinese_name(self):
        return "清空记忆"

    def get_description(self):
        return "清空记忆接口，当我要求你清空记忆时，你应该调用本接口。注意：本接口不接收任何参数，当你调用本接口时你不应该传递任何参数进来。"

    def get_parameters(self):
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def run(self, takecommand, args: dict) -> PluginResult:
        jarvis.memory.clear_recent()
        jarvis.mouth.speak("已清空最近的记忆。", lambda: {})
        return PluginResult.new("", False)
