from abc import ABC, abstractmethod
from typing import Dict, Any, List

class AbstractHAL(ABC):
    """
    Abstract Hardware Abstraction Layer (HAL) Base Class.
    Defines the standard interface for managing all hardware drivers, sensors, and actuators.
    """
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the hardware interface."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Safely close/shutdown the hardware interface."""
        pass


class BaseSensor(ABC):
    """
    Base class for all hardware/system sensors in Butler.
    """
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def read(self) -> Dict[str, Any]:
        """
        Read telemetry/data from the sensor.
        Returns a dictionary containing the metrics.
        """
        pass


class BaseActuator(ABC):
    """
    Base class for all actuators/executors in Butler (e.g., LED screens, STM32 relays, vibration motors).
    """
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def write(self, payload: Any) -> bool:
        """
        Execute an action or send a command to the actuator.
        Returns True if successful, False otherwise.
        """
        pass
