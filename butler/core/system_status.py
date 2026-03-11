import threading
from enum import Enum, auto
from butler.core.event_bus import event_bus

class ButlerState(Enum):
    IDLE = auto()
    THINKING = auto()
    RECORDING = auto()
    ERROR = auto()

class SystemStatus:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SystemStatus, cls).__new__(cls)
                cls._instance._state = ButlerState.IDLE
                cls._instance._is_listening = False
                cls._instance._is_speaking = False
        return cls._instance

    @property
    def state(self) -> ButlerState:
        return self._state

    @state.setter
    def state(self, new_state: ButlerState):
        if self._state != new_state:
            self._state = new_state
            event_bus.emit("system_state_change", new_state)

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    @is_listening.setter
    def is_listening(self, value: bool):
        self._is_listening = value
        self._update_derived_state()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @is_speaking.setter
    def is_speaking(self, value: bool):
        self._is_speaking = value
        self._update_derived_state()

    def _update_derived_state(self):
        if self._is_listening:
            self.state = ButlerState.RECORDING
        elif self._is_speaking:
            # We could have a SPEAKING state, but for now let's keep it simple
            # or map it to THINKING if we want the blue light
            pass
        else:
            if self.state == ButlerState.RECORDING:
                self.state = ButlerState.IDLE

    def set_thinking(self, is_thinking: bool):
        if is_thinking:
            self.state = ButlerState.THINKING
        else:
            if self.state == ButlerState.THINKING:
                self.state = ButlerState.IDLE

# Global singleton
system_status = SystemStatus()
