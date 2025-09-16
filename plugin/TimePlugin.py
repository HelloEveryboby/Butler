import datetime
import logging
from .abstract_plugin import AbstractPlugin

class TimePlugin(AbstractPlugin):
    def get_name(self) -> str:
        return "TimePlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("TimePlugin initialized.")

    def get_commands(self) -> list[str]:
        return ["time", "现在几点了", "时间"]

    def run(self, command: str, args: dict) -> str:
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        return f"现在是北京时间 {current_time}"

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "active"
