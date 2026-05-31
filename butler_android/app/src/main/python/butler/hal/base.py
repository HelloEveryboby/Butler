from abc import ABC, abstractmethod
from typing import Optional, List

class BaseAudio(ABC):
    @abstractmethod
    def speak(self, text: str):
        """Play TTS audio."""
        pass

    @abstractmethod
    def play_wav(self, file_path: str):
        """Play a local wav file."""
        pass

    @abstractmethod
    def set_volume(self, level: int):
        """Set volume (0-100)."""
        pass

class BaseDisplay(ABC):
    @abstractmethod
    def show_text(self, text: str, clear: bool = False):
        """Show text on display."""
        pass

    @abstractmethod
    def clear(self):
        """Clear display."""
        pass

class BaseHAL(ABC):
    @property
    @abstractmethod
    def audio(self) -> BaseAudio:
        pass

    @property
    @abstractmethod
    def display(self) -> BaseDisplay:
        pass
