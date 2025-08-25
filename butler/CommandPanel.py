import tkinter as tk
from tkinter import scrolledtext
import sys
import os
import json
import re
from package.log_manager import LogManager

# Pygments for syntax highlighting
try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.styles import get_style_by_name
    from pygments.token import Token
    PYGMENTS_INSTALLED = True
except ImportError:
    PYGMENTS_INSTALLED = False

logger = LogManager.get_logger(__name__)

class CommandPanel(tk.Frame):
    def __init__(self, master, program_mapping=None, programs=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.command_callback = None
        self.program_mapping = program_mapping or {}
        self.programs = programs or {}
        self.all_program_names = sorted(list(self.programs.keys()))

        # --- Theme and Styling ---
        self.background_color = '#282c34'
        self.foreground_color = '#abb2bf'
        self.input_bg_color = '#21252b'
        self.button_bg_color = '#3e4451'
        self.button_fg_color = self.foreground_color
        self.code_bg_color = '#21252b'
        self.menu_bg_color = '#21252b'
        self.menu_fg_color = self.foreground_color

        self.config(bg=self.background_color)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Main PanedWindow for collapsible menu ---
        self.main_paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg=self.background_color, sashwidth=4)
        self.main_paned_window.grid(row=0, column=0, sticky="nsew")

        # --- Left Pane: Menu ---
        self.menu_frame = tk.Frame(self.main_paned_window, bg=self.menu_bg_color, width=200)
        self.menu_frame.grid_rowconfigure(2, weight=1)  # Make listbox expandable
        self.menu_frame.grid_columnconfigure(0, weight=1)
        self.main_paned_window.add(self.menu_frame, stretch="never", minsize=200)

        tk.Label(self.menu_frame, text="Programs", font=("Arial", 12, "bold"), bg=self.menu_bg_color, fg=self.menu_fg_color).grid(row=0, column=0, pady=5, padx=5, sticky="ew")

        self.search_entry = tk.Entry(self.menu_frame, bg=self.input_bg_color, fg=self.foreground_color, insertbackground=self.foreground_color, borderwidth=0, highlightthickness=1)
        self.search_entry.grid(row=1, column=0, pady=(0, 5), padx=5, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.filter_programs)

        self.program_listbox = tk.Listbox(
            self.menu_frame,
            bg=self.menu_bg_color,
            fg=self.menu_fg_color,
            selectbackground="#4f5b70",
            selectforeground=self.menu_fg_color,
            highlightthickness=0,
            borderwidth=0,
            font=("Arial", 10)
        )
        self.program_listbox.grid(row=2, column=0, sticky="nsew", padx=(5, 0), pady=(0, 5))
        self.program_listbox.bind("<<ListboxSelect>>", self.on_program_select)

        scrollbar = tk.Scrollbar(self.menu_frame, orient="vertical", command=self.program_listbox.yview)
        scrollbar.grid(row=2, column=1, sticky="ns", pady=(0, 5))
        self.program_listbox.config(yscrollcommand=scrollbar.set)

        for prog_name in self.all_program_names:
            self.program_listbox.insert(tk.END, prog_name)

        # --- Right Pane: Main Content ---
        self.main_content_frame = tk.Frame(self.main_paned_window, bg=self.background_color)
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.main_paned_window.add(self.main_content_frame, stretch="always")


        # --- Main output text area ---
        self.output_text = scrolledtext.ScrolledText(
            self.main_content_frame, # Parent is now main_content_frame
            bg=self.background_color,
            fg=self.foreground_color,
            state='disabled',
            wrap=tk.WORD,
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0,
            selectbackground="#4f5b70"
        )
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # --- Input Frame (at the bottom) ---
        self.input_frame = tk.Frame(self.main_content_frame, bg=self.background_color) # Parent is now main_content_frame
        self.input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = tk.Entry(
            self.input_frame,
            bg=self.input_bg_color,
            fg=self.foreground_color,
            insertbackground=self.foreground_color,
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        self.input_entry.bind("<Return>", self.send_text_command)

        # --- Buttons ---
        button_config = {
            "bg": self.button_bg_color,
            "fg": self.button_fg_color,
            "activebackground": "#4f5b70",
            "activeforeground": self.foreground_color,
            "borderwidth": 0,
            "highlightthickness": 0,
            "font": ("Arial", 9)
        }
        self.send_button = tk.Button(self.input_frame, text="Send", command=self.send_text_command, **button_config)
        self.send_button.grid(row=0, column=1, padx=(5, 0))
        self.listen_button = tk.Button(self.input_frame, text="Listen", command=self.send_listen_command, **button_config)
        self.listen_button.grid(row=0, column=2, padx=(5, 0))
        self.clear_button = tk.Button(self.input_frame, text="Clear", command=self.clear_history, **button_config)
        self.clear_button.grid(row=0, column=3, padx=(5, 0))
        self.restart_button = tk.Button(self.input_frame, text="Restart", command=self.restart_application, **button_config)
        self.restart_button.grid(row=0, column=4, padx=(5, 0))

        self._configure_styles_and_tags()

    def on_program_select(self, event=None):
        """Handle program selection from the listbox."""
        # Get selected indices
        selected_indices = self.program_listbox.curselection()
        if not selected_indices:
            return

        # Get the program name from the index
        selected_index = selected_indices[0]
        program_name = self.program_listbox.get(selected_index)

        if program_name and self.command_callback:
            logger.info(f"Executing program from menu: {program_name}")
            self.append_to_history(f"Executing: {program_name}", "system_message")
            self.command_callback("execute_program", program_name)

    def filter_programs(self, event=None):
        """Filter the program listbox based on the search entry."""
        search_term = self.search_entry.get().lower()

        # Clear the listbox
        self.program_listbox.delete(0, tk.END)

        # Repopulate with matching items
        for name in self.all_program_names:
            if search_term in name.lower():
                self.program_listbox.insert(tk.END, name)

    def _configure_styles_and_tags(self):
        """Configure text tags for styling the output."""
        self.output_text.tag_config('user_prompt', foreground='#61afef', font=("Consolas", 11, "bold"))
        self.output_text.tag_config('ai_response', foreground=self.foreground_color)
        self.output_text.tag_config('system_message', foreground='#e5c07b', font=("Consolas", 11, "italic"))
        self.output_text.tag_config('error', foreground='#e06c75')

        # Configure Pygments syntax highlighting tags
        if PYGMENTS_INSTALLED:
            style = get_style_by_name('monokai')
            for token, t_style in style:
                tag_name = str(token)
                foreground = t_style['color']
                if foreground:
                    self.output_text.tag_config(tag_name, foreground=f"#{foreground}")

    def _highlight_code(self, code, language=''):
        """Apply syntax highlighting to a code block."""
        if not PYGMENTS_INSTALLED:
            self.output_text.insert(tk.END, code)
            return

        try:
            if language:
                lexer = get_lexer_by_name(language, stripall=True)
            else:
                lexer = guess_lexer(code, stripall=True)
        except Exception:
            lexer = get_lexer_by_name('text', stripall=True)

        # Insert the code block with a background
        start_index = self.output_text.index(tk.END)
        self.output_text.insert(tk.END, code)
        end_index = self.output_text.index(tk.END)
        self.output_text.tag_add("code_block", start_index, end_index)
        self.output_text.tag_config("code_block", background=self.code_bg_color, borderwidth=1, relief=tk.SOLID, lmargin1=10, lmargin2=10, rmargin=10)

        # Apply token-based highlighting
        for token, content in lex(code, lexer):
            tag_name = str(token)
            # Find where the content starts relative to the beginning of the whole code block
            # This is a bit tricky with the Text widget, so we search
            start = self.output_text.search(content, start_index, stopindex=end_index)
            if start:
                end = f"{start}+{len(content)}c"
                self.output_text.tag_add(tag_name, start, end)
                start_index = end # Move search start to after the found token


    def append_to_history(self, text, tag='ai_response'):
        self.output_text.config(state='normal')

        code_block_pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

        last_end = 0
        for match in code_block_pattern.finditer(text):
            # Insert text before the code block
            pre_text = text[last_end:match.start()]
            if pre_text.strip():
                self.output_text.insert(tk.END, pre_text, (tag,))

            # Insert the highlighted code block
            language = match.group(1).lower()
            code = match.group(2)
            self._highlight_code(code, language)

            last_end = match.end()

        # Insert any remaining text after the last code block
        remaining_text = text[last_end:]
        if remaining_text.strip():
            self.output_text.insert(tk.END, remaining_text, (tag,))

        self.output_text.insert(tk.END, "\n\n")
        self.output_text.see(tk.END)
        self.output_text.config(state='disabled')


    def set_command_callback(self, callback):
        self.command_callback = callback

    def send_text_command(self, event=None):
        command = self.input_entry.get().strip()
        if command and self.command_callback:
            self.append_to_history(f"You: {command}", "user_prompt")
            logger.info(f"Sending text command: {command}")
            self.command_callback("text", command)
            self.input_entry.delete(0, tk.END)

    def send_listen_command(self):
        if self.command_callback:
            logger.info("Initiating voice command")
            self.command_callback("voice", None)

    def set_input_text(self, text):
        self.input_entry.delete(0, tk.END)
        self.input_entry.insert(0, text)

    def clear_history(self):
        logger.info("Clearing history")
        self.output_text.config(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state='disabled')

    def restart_application(self):
        logger.info("Restarting application")
        python = sys.executable
        os.execl(python, python, *sys.argv)
