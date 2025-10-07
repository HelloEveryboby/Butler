import platform
import subprocess
import webbrowser
from .tool_decorator import tool

@tool
def open_application(app_name: str):
    """
    Opens an application using the most direct, OS-specific command.

    Args:
        app_name (str): The name of the application to open.
                        On macOS, this should be the '.app' name (e.g., 'Chess.app').
                        On Windows, this can be an executable name (e.g., 'notepad.exe').
    """
    current_os = platform.system()
    command = []

    if current_os == "Darwin":  # macOS
        command = ["open", "-a", app_name]
    elif current_os == "Windows":
        # The 'start' command is a shell built-in, so we run it through cmd.exe
        command = ["cmd", "/c", "start", app_name]
    elif current_os == "Linux":
        # xdg-open is the standard way to open files/apps on most Linux desktops
        command = ["xdg-open", app_name]
    else:
        return f"Unsupported operating system: {current_os}"

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        return f"Successfully launched {app_name}."
    except FileNotFoundError:
        return f"Error: Command not found for {current_os}. Is the application installed and in your PATH?"
    except subprocess.CalledProcessError as e:
        return f"Error opening {app_name} on {current_os}: {e.stderr}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

@tool
def open_url(url: str):
    """
    Opens a URL in the default web browser.

    Args:
        url (str): The full URL to open (e.g., 'https://www.google.com').
    """
    try:
        webbrowser.open(url)
        return f"Successfully opened URL: {url}"
    except Exception as e:
        return f"An error occurred while opening the URL: {e}"