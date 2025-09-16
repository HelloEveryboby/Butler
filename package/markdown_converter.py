import sys
import os

# HACK: This is a workaround for the environment's issue with editable installs.
# It ensures that the 'markitdown' package can be found when this module
# is imported by the butler application.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'markitdown', 'src')))

from markitdown.main import convert

def convert_to_markdown(file_path: str) -> str:
    """
    Converts a file to markdown and returns the content as a string.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at '{file_path}'"

    try:
        return convert(file_path)
    except Exception as e:
        return f"An error occurred during conversion: {e}"
