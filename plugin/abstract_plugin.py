import abc
import logging
from typing import NamedTuple, Any

class PluginResult(NamedTuple):
    success: bool
    result: Any
    error_message: str = ""

class AbstractPlugin(abc.ABC):
    @abc.abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def valid(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def init(self, logger: logging.Logger):
        raise NotImplementedError

    @abc.abstractmethod
    def run(self, command: str, args: dict) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def cleanup(self):
        raise NotImplementedError

    @abc.abstractmethod
    def status(self) -> Any:
        raise NotImplementedError

    def get_commands(self) -> list[str]:
        """
        Returns a list of commands that this plugin can handle.
        """
        return []

    def get_match_type(self) -> str:
        """
        Returns the match type for the commands.
        Can be 'exact', 'prefix', or 'contains'.
        """
        return 'contains'
