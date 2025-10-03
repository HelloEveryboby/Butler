import os
import mss
import pyautogui
import base64
from io import BytesIO
from .tool_decorator import tool

# --- GUI Automation / OS Control Tools ---

@tool
def capture_screen(monitor_number=1) -> str:
    """
    Captures a screenshot of the specified monitor and returns it as a base64 encoded string.

    Args:
        monitor_number (int): The monitor to capture (1-based index).

    Returns:
        A base64 encoded string of the PNG image.
    """
    with mss.mss() as sct:
        # Get information of monitor 1
        monitor = sct.monitors[monitor_number]

        # Grab the data
        sct_img = sct.grab(monitor)

        # Save to a BytesIO object
        img_buffer = BytesIO()
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=img_buffer)
        img_buffer.seek(0)

        # Encode to base64
        b64_string = base64.b64encode(img_buffer.read()).decode('utf-8')
        return b64_string

@tool
def move_mouse(x: int, y: int, duration: float = 0.5):
    """
    Moves the mouse cursor to the specified X and Y coordinates.

    Args:
        x (int): The x-coordinate on the screen.
        y (int): The y-coordinate on the screen.
        duration (float): The time in seconds to spend moving the mouse.
    """
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse moved to ({x}, {y})."

@tool
def click(x: int = None, y: int = None, button: str = 'left'):
    """
    Simulates a mouse click. Clicks at the current location if x and y are not provided.

    Args:
        x (int, optional): The x-coordinate to move to before clicking.
        y (int, optional): The y-coordinate to move to before clicking.
        button (str): The mouse button to click ('left', 'right', 'middle').
    """
    if x is not None and y is not None:
        pyautogui.click(x, y, button=button)
        return f"Clicked {button} button at ({x}, {y})."
    else:
        pyautogui.click(button=button)
        current_pos = pyautogui.position()
        return f"Clicked {button} button at current position {current_pos}."

@tool
def type_text(text: str, interval: float = 0.1):
    """
    Types the given text at the current cursor location.

    Args:
        text (str): The text to type.
        interval (float): The time in seconds between each keystroke.
    """
    pyautogui.write(text, interval=interval)
    return f"Typed text: '{text[:50]}...'"