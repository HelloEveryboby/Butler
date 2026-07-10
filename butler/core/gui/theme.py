from typing import Dict, Any, Tuple

class UIThemeManager:
    """
    Centralized theme manager for Butler's graphical interfaces.
    Adheres to Apple minimalism and glassmorphism design tokens:
    - Standard 12px rounded corners on panels.
    - Glassmorphism parameters: translucent background, fine-line borders, high blur (30px).
    - Clear light/dark color mappings.
    """
    # Apple Minimalism & Glassmorphism Design Tokens
    ROUNDNESS_RADIUS = 12       # 12px rounded corners
    BACKDROP_BLUR_PX = 30       # 30px backdrop blur
    BORDER_WIDTH_PX = 1         # Fine borders
    TRANSITION_EASING = "--apple-easing"

    # Color Palettes
    DARK_THEME = {
        "background": "#1c1c1c",        # Deep rich black (with transparency in modern views)
        "foreground": "#00ff00",        # Classic terminal/radar green
        "input_bg": "#000000",          # Pure black background for input
        "button_bg": "#333333",         # Muted charcoal buttons
        "button_fg": "#ffffff",         # Clean white button text
        "code_bg": "#000000",           # High contrast black code block bg
        "menu_bg": "#121212",           # Slightly lighter black for menus
        "menu_fg": "#00ff00",           # Green text on menu
        "accent": "#2da44e",            # Positive green accent
        "glass_border": "rgba(255, 255, 255, 0.08)",
        "glass_bg": "rgba(28, 28, 28, 0.7)"
    }

    LIGHT_THEME = {
        "background": "#f6f8fa",        # Light clean background (GitHub style)
        "foreground": "#24292f",        # Dark text
        "input_bg": "#ffffff",          # Clean white input
        "button_bg": "#eaeef2",         # Soft light gray buttons
        "button_fg": "#24292f",         # Dark text for buttons
        "code_bg": "#fcfdfd",           # Off-white for code
        "menu_bg": "#ffffff",           # Pure white menu
        "menu_fg": "#24292f",
        "accent": "#2da44e",
        "glass_border": "rgba(0, 0, 0, 0.06)",
        "glass_bg": "rgba(246, 248, 252, 0.75)"
    }

    # Core typography definition
    FONT_CONFIGS = {
        "small": {
            "menu_label": ("Arial", 10, "bold"),
            "program_listbox": ("Arial", 8),
            "output_text": ("Consolas", 9),
            "input_entry": ("Consolas", 9),
            "buttons": ("Arial", 7),
            "user_prompt": ("Consolas", 9, "bold"),
            "system_message": ("Consolas", 9, "italic"),
        },
        "medium": {
            "menu_label": ("Arial", 12, "bold"),
            "program_listbox": ("Arial", 10),
            "output_text": ("Consolas", 11),
            "input_entry": ("Consolas", 11),
            "buttons": ("Arial", 9),
            "user_prompt": ("Consolas", 11, "bold"),
            "system_message": ("Consolas", 11, "italic"),
        },
        "large": {
            "menu_label": ("Arial", 14, "bold"),
            "program_listbox": ("Arial", 12),
            "output_text": ("Consolas", 13),
            "input_entry": ("Consolas", 13),
            "buttons": ("Arial", 11),
            "user_prompt": ("Consolas", 13, "bold"),
            "system_message": ("Consolas", 13, "italic"),
        }
    }

    def __init__(self, mode: str = "dark"):
        self.set_mode(mode)

    def set_mode(self, mode: str):
        self.mode = mode.lower()
        if self.mode == "light":
            self.colors = self.LIGHT_THEME
        else:
            self.colors = self.DARK_THEME

    def get_colors(self) -> Dict[str, str]:
        return self.colors

    def get_font_style(self, size_mode: str, component_key: str) -> Tuple[str, int, str]:
        size_mode = size_mode.lower() if size_mode.lower() in self.FONT_CONFIGS else "medium"
        return self.FONT_CONFIGS[size_mode].get(component_key, ("Arial", 10))
