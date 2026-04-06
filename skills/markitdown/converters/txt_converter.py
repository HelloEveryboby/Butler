def convert_txt(file_path: str) -> str:
    """
    Converts a plain text file to a Markdown code block.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"```text\n{content}\n```"
    except Exception as e:
        return f"Error converting text file: {e}"
