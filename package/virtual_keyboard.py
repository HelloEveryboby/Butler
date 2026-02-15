"""
虚拟键盘工具。提供一个图形界面的屏幕键盘，支持拼音、数字、表情和符号输入。
"""
import tkinter as tk
try:
    from pypinyin import lazy_pinyin, Style
except ImportError:
    lazy_pinyin = None

class VirtualKeyboard(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master

        # 键盘按钮配置（小写）
        self.keys_lower = [
            ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
            ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
            ['z', 'x', 'c', 'v', 'b', 'n', 'm']
        ]
        self.keys_upper = [ [k.upper() for k in row] for row in self.keys_lower ]

        # 数字键盘配置
        self.keys_numbers = [
            ['1', '2', '3'],
            ['4', '5', '6'],
            ['7', '8', '9'],
            ['0']
        ]

        # 表情键盘配置
        self.keys_emojis = [
            ['😊', '😂', '😍', '🥰', '😎'],
            ['😭', '😡', '😱', '👍', '👎'],
            ['🙌', '🙏', '👏', '💪', '🔥']
        ]

        # 符号键盘配置
        self.keys_symbols = [
            ['，', '。', '！', '？', '、'],
            ['：', '；', '（', '）', '【'],
            ['】', '‘', '’', '“', '”']
        ]

        # 特殊按钮
        self.special_keys = {
            'space': ' ',
            'shift': 'Shift',
            'enter': 'Enter',
            'backspace': 'Backspace',
            '123': '123',
            'emoji': '😊',
            'symbols': '符',
            'language': '🌐'
        }

        # 全局变量
        self.language_mode = 'EN'
        self.shift_mode = False
        self.number_mode = False
        self.emoji_mode = False
        self.symbol_mode = False

        self.entry_text = tk.StringVar()
        self.create_widgets()

        # Configure grid weights for resizing
        num_rows = len(self.keys_lower) + 2 # 3 rows of keys + entry + special keys row
        num_cols = len(self.keys_lower[0]) # 10 columns for the main keys

        for i in range(num_rows):
            self.grid_rowconfigure(i, weight=1)
        for i in range(num_cols):
            self.grid_columnconfigure(i, weight=1)


    def create_widgets(self):
        # 创建显示输入内容的文本框
        entry = tk.Entry(self, textvariable=self.entry_text, font=("Helvetica", 14))
        entry.grid(row=0, column=0, columnspan=10, sticky="nsew", padx=2, pady=2)

        # 创建键盘按钮
        self.buttons = []
        for i, row in enumerate(self.keys_lower):
            button_row = []
            for j, key in enumerate(row):
                button = tk.Button(self, text=key, font=("Helvetica", 12),
                                   command=lambda key=key: self.on_key_press(key),
                                   activebackground='lightblue', activeforeground='black')
                button.grid(row=i+1, column=j, sticky="nsew", padx=1, pady=1)
                button_row.append(button)
            self.buttons.append(button_row)

        # 创建特殊功能键
        special_button_row = len(self.keys_lower) + 1
        button_font = ("Helvetica", 10)

        # Left side
        tk.Button(self, text=self.special_keys['123'], font=button_font, command=lambda: self.on_key_press(self.special_keys['123']), activebackground='lightblue', activeforeground='black').grid(row=special_button_row, column=0, sticky="nsew", padx=1, pady=1)
        self.language_button = tk.Button(self, text="EN", font=button_font, command=lambda: self.on_key_press('🌐'), activebackground='lightblue', activeforeground='black')
        self.language_button.grid(row=special_button_row, column=1, sticky="nsew", padx=1, pady=1)

        # Space bar
        tk.Button(self, text=self.special_keys['space'], font=button_font, command=lambda: self.on_key_press(self.special_keys['space']), activebackground='lightblue', activeforeground='black').grid(row=special_button_row, column=2, columnspan=5, sticky="nsew", padx=1, pady=1)

        # Right side
        tk.Button(self, text=self.special_keys['symbols'], font=button_font, command=lambda: self.on_key_press(self.special_keys['symbols']), activebackground='lightblue', activeforeground='black').grid(row=special_button_row, column=7, sticky="nsew", padx=1, pady=1)
        tk.Button(self, text=self.special_keys['backspace'], font=button_font, command=lambda: self.on_key_press(self.special_keys['backspace']), activebackground='lightblue', activeforeground='black').grid(row=special_button_row, column=8, columnspan=2, sticky="nsew", padx=1, pady=1)

        # Side buttons (Shift, Enter, Emoji)
        tk.Button(self, text=self.special_keys['shift'], font=button_font, command=lambda: self.on_key_press(self.special_keys['shift']), activebackground='lightblue', activeforeground='black').grid(row=1, column=9, rowspan=1, sticky="nsew", padx=1, pady=1)
        tk.Button(self, text=self.special_keys['enter'], font=button_font, command=lambda: self.on_key_press(self.special_keys['enter']), activebackground='lightblue', activeforeground='black').grid(row=2, column=9, rowspan=1, sticky="nsew", padx=1, pady=1)
        tk.Button(self, text=self.special_keys['emoji'], font=button_font, command=lambda: self.on_key_press(self.special_keys['emoji']), activebackground='lightblue', activeforeground='black').grid(row=3, column=9, rowspan=1, sticky="nsew", padx=1, pady=1)


    def on_key_press(self, value):
        if value == 'Backspace':
            self.entry_text.set(self.entry_text.get()[:-1])
        elif value == 'Enter':
            self.entry_text.set(self.entry_text.get() + '\n')
        elif value == 'Shift':
            self.shift_mode = not self.shift_mode
            self.update_keyboard()
        elif value == '123':
            self.number_mode = not self.number_mode
            self.emoji_mode = False
            self.symbol_mode = False
            self.update_keyboard()
        elif value == '😊':
            self.emoji_mode = not self.emoji_mode
            self.number_mode = False
            self.symbol_mode = False
            self.update_keyboard()
        elif value == '符':
            self.symbol_mode = not self.symbol_mode
            self.number_mode = False
            self.emoji_mode = False
            self.update_keyboard()
        elif value == 'space':
            self.entry_text.set(self.entry_text.get() + ' ')
        elif value == '🌐':
            if self.language_mode == 'EN':
                self.language_mode = 'CN'
                self.language_button.config(text="CN")
            else:
                self.language_mode = 'EN'
                self.language_button.config(text="EN")
        else:
            self.entry_text.set(self.entry_text.get() + value)

    def update_keyboard(self):
        if self.emoji_mode:
            keys = self.keys_emojis
        elif self.symbol_mode:
            keys = self.keys_symbols
        elif self.number_mode:
            keys = self.keys_numbers
        else:
            keys = self.keys_upper if self.shift_mode else self.keys_lower

        for i, row_buttons in enumerate(self.buttons):
            if i < len(keys):
                for j, button in enumerate(row_buttons):
                    if j < len(keys[i]):
                        button.config(text=keys[i][j])
                        button.grid()
                    else:
                        button.grid_remove()
            else:
                for button in row_buttons:
                    button.grid_remove()


    def get_text(self):
        return self.entry_text.get()


def run(**kwargs):
    """
    启动虚拟键盘。
    """
    root = tk.Tk()
    root.title("Virtual Keyboard")

    # Make the root window resizable
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    keyboard = VirtualKeyboard(root)
    keyboard.grid(row=0, column=0, sticky="nsew")

    root.mainloop()

if __name__ == '__main__':
    run()
