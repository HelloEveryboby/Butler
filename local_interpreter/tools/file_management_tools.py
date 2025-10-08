import os
from .tool_decorator import tool

@tool
def read_file(path: str) -> str:
    """Reads the content of a file at the specified path."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"Content of '{path}':\n```\n{content}\n```"
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file '{path}': {e}"

@tool
def write_file(path: str, content: str) -> str:
    """Writes the given content to a file at the specified path, overwriting it if it exists."""
    try:
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to '{path}'."
    except Exception as e:
        return f"Error writing to file '{path}': {e}"

@tool
def delete_file(path: str) -> str:
    """Deletes a file at the specified path."""
    try:
        os.remove(path)
        return f"Successfully deleted file at '{path}'."
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error deleting file '{path}': {e}"

@tool
def modify_file(path: str, new_content: str) -> str:
    """
    Modifies an existing file by replacing its content with the provided new content.
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"Successfully modified file at '{path}'."
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error modifying file '{path}': {e}"

@tool
def list_directory(path: str) -> str:
    """Lists all files and subdirectories within a specified directory."""
    try:
        if not os.path.isdir(path):
            return f"Error: '{path}' is not a valid directory."

        items = os.listdir(path)

        if not items:
            return f"Directory '{path}' is empty."

        # Format the output for better readability
        output = f"Contents of '{path}':\n"
        for item in items:
            # Add a trailing slash for directories
            if os.path.isdir(os.path.join(path, item)):
                output += f"- {item}/\n"
            else:
                output += f"- {item}\n"
        return output

    except FileNotFoundError:
        return f"Error: Directory not found at '{path}'."
    except Exception as e:
        return f"Error listing directory '{path}': {e}"
