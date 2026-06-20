import time
import os
from butler.hal.base import BaseAudio, BaseDisplay
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("PCAudio")

class PCAudio(BaseAudio):
    def speak(self, text: str):
        # Implementation depends on VoiceService which is already high-level.
        # This driver would handle the OS-specific playback.
        logger.info(f"PC Audio: Speaking '{text}'")
        pass

    def play_wav(self, file_path: str):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            logger.warning(f"PC Audio: Playback failed for {file_path}: {e}")

    def set_volume(self, level: int):
        logger.info(f"PC Audio: Setting volume to {level}")
        # In a real implementation, we would call OS-specific commands here.

class PCDisplay(BaseDisplay):
    def show_text(self, text: str, clear: bool = False):
        if clear:
            print("\n" * 2)
        print(f"[PC Display] {text}")

    def clear(self):
        print("[PC Display] Cleared")
