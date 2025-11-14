from butler import algorithms
from package.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

class FibonacciPlugin(AbstractPlugin):
    def __init__(self):
        self.name = "FibonacciPlugin"
        self.chinese_name = "斐波那契数列"
        self.description = "计算斐波那契数列的第n项"
        self.parameters = {
            "number": "integer"
        }

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
        self.logger.info("FibonacciPlugin started.")

    def on_shutdown(self):
        self.logger.info("FibonacciPlugin shutdown.")

    def on_pause(self):
        self.logger.info("FibonacciPlugin paused.")

    def on_resume(self):
        self.logger.info("FibonacciPlugin resumed.")

    def get_commands(self) -> list[str]:
        return ["fibonacci", "斐波那契"]

    def run(self, command: str, args: dict) -> PluginResult:
        try:
            n = args.get("number")
            if n is None or not isinstance(n, int):
                return PluginResult.new("计算失败，请输入一个有效的整数。", False)
            fib = algorithms.fibonacci(n)
            return PluginResult.new(f"斐波那契数列第{n}项是: {fib}", False)
        except Exception as e:
            return PluginResult.new(f"计算斐波那契数时出错: {e}", False)
