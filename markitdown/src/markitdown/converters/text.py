import os

def convert_text(file_path: str) -> str:
    """
    Converts a plain text file to a Markdown code block.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}"

    # Get file extension to use as a language hint in the code block
    _, extension = os.path.splitext(file_path)
    lang = extension.lstrip('.') if extension else ""

    return f"```{lang}\n{content}\n```"
