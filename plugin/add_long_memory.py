import logging
import time
from .abstract_plugin import AbstractPlugin
from .long_memory.long_memory_interface import LongMemoryItem

class AddLongMemoryPlugin(AbstractPlugin):
    def get_name(self) -> str:
        return "add_long_memory"

    def valid(self) -> bool:
        # This feature is not fully implemented or stable.
        return False

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("AddLongMemoryPlugin initialized (but is not valid).")

    def get_commands(self) -> list[str]:
        return ["remember", "add memory", "增加记忆"]

    def run(self, command: str, args: dict) -> str:
        self.logger.warning("Attempted to run AddLongMemoryPlugin, which is not fully implemented.")
        # This plugin requires access to the main application's long_memory object,
        # which is not provided through the current plugin interface.
        # This indicates a design problem that needs to be addressed separately.
        return "Error: The long-term memory feature is currently under development and not available."

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "inactive (feature not implemented)"
