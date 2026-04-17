import platform
from butler.hal.base import BaseHAL
from butler.hal.drivers.pc.driver import PCAudio, PCDisplay

class HAL(BaseHAL):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HAL, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Auto-detect platform and load appropriate drivers
        sys_type = platform.system()
        if sys_type in ["Windows", "Linux", "Darwin"]:
            self._audio = PCAudio()
            self._display = PCDisplay()
        else:
            # Fallback or specific embedded platforms
            self._audio = PCAudio()
            self._display = PCDisplay()

    @property
    def audio(self):
        return self._audio

    @property
    def display(self):
        return self._display

hal = HAL()
