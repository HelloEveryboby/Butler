import os
import textwrap
from butler.hal import hal

class USBScreen:
    """
    一个模拟 USB 驱动器上显示的模拟类。
    在实际场景中，此类将与 USB 驱动器上屏幕的硬件进行接口。
    """
    def __init__(self, width=40, height=8):
        self.width = width
        self.height = height
        self.clear()

    def display(self, message: str, clear_screen: bool = False):
        """
        在 USB 屏幕上显示格式化的消息。
        通过 HAL 层进行硬件解耦。
        """
        hal.display.show_text(message, clear=clear_screen)

    def clear(self):
        """
        清除 USB 屏幕。
        通过 HAL 层进行硬件解耦。
        """
        hal.display.clear()
