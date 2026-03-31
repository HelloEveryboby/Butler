import mss
import base64
from io import BytesIO


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
        b64_string = base64.b64encode(img_buffer.read()).decode("utf-8")
        return b64_string
