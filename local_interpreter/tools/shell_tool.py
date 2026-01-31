import subprocess
import platform
from .tool_decorator import tool

@tool
def run_shell(command: str) -> str:
    """
    Executes a shell command in the system terminal and returns its STDOUT and STDERR.
    Use this for:
    - Installing packages via pip (e.g., 'pip install requests').
    - Running system commands (e.g., 'ls -la', 'ps aux', 'df -h').
    - Executing compiled programs.
    Always use absolute paths if you are unsure of the current working directory.
    """
    try:
        # For cross-platform compatibility, split the command into a list.
        # This is generally safer than `shell=True`.
        command_parts = command.split()

        # Windows needs a different way to run shell commands sometimes
        if platform.system() == "Windows":
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        else:
            result = subprocess.run(command_parts, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            return f"STDOUT:\n{result.stdout}"
        else:
            return f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"

    except FileNotFoundError:
        return f"Error: Command '{command_parts[0]}' not found."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# This can be used for direct testing of the tool
if __name__ == '__main__':
    # Example usage:
    test_command_unix = "ls -l"
    test_command_windows = "dir"

    if platform.system() == "Windows":
        print(f"Running on Windows. Executing: '{test_command_windows}'")
        output = run_shell(test_command_windows)
        print(output)
    else:
        print(f"Running on Unix-like system. Executing: '{test_command_unix}'")
        output = run_shell(test_command_unix)
        print(output)
