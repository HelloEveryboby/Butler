class USBScreen:
    """
    A mock class to simulate the display on a USB drive.
    In a real-world scenario, this class would interface with the hardware
    of the screen on the USB drive.
    """
    def display(self, message):
        """
        Displays a message on the USB screen.
        For this mock version, it just prints to the console.
        """
        print(f"[USB SCREEN] {message}")
