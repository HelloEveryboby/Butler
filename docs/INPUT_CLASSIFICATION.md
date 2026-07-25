# Input Classification

This document classifies the different ways a user can interact with the application.

## GUI-Based Input

- **Text Commands:** Users can type commands into the input field and press Enter or click the "Send" button.
- **Voice Commands:** Users can click the "Listen" button to start and stop voice recognition.
- **Program Execution:** Users can select and execute programs from a list in the GUI.
- **Display Mode Selection:** Users can choose the display mode (Host, USB, or Both) using radio buttons.
- **Settings:** Users can open a settings window to adjust the font size.

## Command-Line and Special Inputs

- **Legacy Mode:** Users can prefix commands with `/legacy` to use the intent-based system.
- **Interpreter Commands:** Any command that is not a special command is sent to the streaming interpreter by default.
- **Safety and Approval:** Users can manage the safety mode with `/safety [on|off]` and approve code execution with `/approve`.
- **OS Mode:** Users can enable or disable OS mode with `/os-mode [on|off]`.
- **Display Command:** Users can set the display mode with `/display [host|usb|both]`.
- **Markdown Conversion:** Users can convert files to markdown with the `markdown <file_path>` command.
- **Headless Mode:** The application can be run in a headless mode using the `--headless` command-line argument. In this mode, the application starts listening for voice commands automatically.

## Other Interactions

- **File System Monitoring:** The application monitors the file system for changes to programs and reloads them automatically. This is an indirect form of interaction.
