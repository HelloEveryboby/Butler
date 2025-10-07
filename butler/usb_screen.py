import os
import textwrap

class USBScreen:
    """
    A mock class to simulate the display on a USB drive.
    In a real-world scenario, this class would interface with the hardware
    of the screen on the USB drive.
    """
    def __init__(self, width=40, height=8):
        self.width = width
        self.height = height
        self.clear()

    def display(self, message: str, clear_screen: bool = False):
        """
        Displays a formatted message on the USB screen.
        For this mock version, it just prints to the console.
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
        Clears the USB screen.
        In this mock, it just prints a clear screen representation.
        """
        # In a real terminal, we could use os.system('cls' or 'clear')
        # For this simulation, we'll just print a "cleared" state.
        print("\n" * 2) # Add some spacing
        print("+" + "-" * (self.width - 2) + "+")
        for _ in range(self.height):
            print(f"| {' ':<{self.width - 4}} |")
        print("+" + "-" * (self.width - 2) + "+")
        print("[USB SCREEN CLEARED]")
