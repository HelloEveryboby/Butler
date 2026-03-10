import logging
from abc import ABCMeta, abstractmethod


class LongMemoryItem:
    def __init__(self):
        self.content = None
        self.id = None
        self.metadata = None
        self.distance = None

    @staticmethod
    def new(content: str, id: str, metadata: dict, distance: float = None):
        item = LongMemoryItem()
        item.content = content
        item.id = id
        item.metadata = metadata
        item.distance = distance
        return item


class AbstractLongMemory(metaclass=ABCMeta):

    @abstractmethod
    def init(self, logger: logging.Logger):
        pass

    @abstractmethod
    def save(self, items: [LongMemoryItem]):
        pass

    @abstractmethod
    def search(self, text: str, n_results: int, metadata_filter: dict) -> [LongMemoryItem]:
        pass

    @abstractmethod
    def get_recent_history(self, n_results: int) -> [LongMemoryItem]:
        pass

    @abstractmethod
    def export_data(self) -> [dict]:
        """Export all data as a list of dictionaries for migration."""
        pass

    @abstractmethod
    def import_data(self, data: [dict]):
        """Import data from a list of dictionaries."""
        pass
