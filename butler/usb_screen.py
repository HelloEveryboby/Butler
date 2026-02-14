import os
import textwrap

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
        对于这个模拟版本，它只是打印到控制台。
        """
        if clear_screen:
            self.clear()

        # Wrap text to fit the screen width
        wrapped_lines = textwrap.wrap(message, self.width - 4) # -4 for padding

        # Simulate screen output
        print("+" + "-" * (self.width - 2) + "+")
        for i in range(self.height):
            if i < len(wrapped_lines):
                line_content = wrapped_lines[i]
            else:
                line_content = ""
            print(f"| {line_content:<{self.width - 4}} |")
        print("+" + "-" * (self.width - 2) + "+")

    def clear(self):
        """
        清除 USB 屏幕。
        在这个模拟中，它只是打印清除屏幕的表示。
        """
        # In a real terminal, we could use os.system('cls' or 'clear')
        # For this simulation, we'll just print a "cleared" state.
        print("\n" * 2) # Add some spacing
        print("+" + "-" * (self.width - 2) + "+")
        for _ in range(self.height):
            print(f"| {' ':<{self.width - 4}} |")
        print("+" + "-" * (self.width - 2) + "+")
        print("[USB 屏幕已清除]")
