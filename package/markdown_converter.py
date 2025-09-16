import sys
import os

# HACK: This is a workaround for the environment's issue with editable installs.
# It ensures that the 'markitdown' package can be found when this module
# is imported by the butler application.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'markitdown', 'src')))

from markitdown.main import convert

def convert_to_markdown(file_path: str):
    """
    Converts a file to markdown and prints the content.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return

    try:
        markdown_content = convert(file_path)
        print(markdown_content)
    except Exception as e:
        print(f"An error occurred during conversion: {e}")
