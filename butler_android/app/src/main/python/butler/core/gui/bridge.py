import tkinter as tk
from typing import Dict, Any, Callable
from butler.core.gui.theme import UIThemeManager

class FontScaler:
    """
    Utility class to calculate auto-scaled fonts based on custom scale factors and window width/height.
    Uses 'medium' as the reference layout.
    """
    @staticmethod
    def get_auto_scaled_fonts(scale: float) -> Dict[str, Any]:
        """
        Dynamically scale fonts based on standard reference widths.
        """
        # Base sizes for 'medium' size configuration
        base_fonts = {
            "menu_label": 12,
            "program_listbox": 10,
            "output_text": 11,
            "input_entry": 11,
            "buttons": 9,
            "user_prompt": 11,
            "system_message": 11
        }

        scaled_fonts = {}
        for key, size in base_fonts.items():
            new_size = max(int(size * scale), 7)
            if key == "menu_label":
                scaled_fonts[key] = ("Arial", new_size, "bold")
            elif key == "user_prompt":
                scaled_fonts[key] = ("Consolas", new_size, "bold")
            elif key == "system_message":
                scaled_fonts[key] = ("Consolas", new_size, "italic")
            elif key in ["output_text", "input_entry"]:
                scaled_fonts[key] = ("Consolas", new_size)
            else:
                scaled_fonts[key] = ("Arial", new_size)

        return scaled_fonts


class UIBridge:
    """
    Unified UI Bridge to route Python UI events to modern or classic GUI renderers.
    Supports registration of listeners for screen updates, inputs, and state changes.
    """
    def __init__(self):
        self._listeners = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Register a handler for specific UI events."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def trigger(self, event_type: str, *args, **kwargs) -> None:
        """Publish a GUI/WebView update to registered renderers."""
        if event_type in self._listeners:
            for cb in self._listeners[event_type]:
                try:
                    cb(*args, **kwargs)
                except Exception as e:
                    # Non-blocking GUI notification failure
                    pass
