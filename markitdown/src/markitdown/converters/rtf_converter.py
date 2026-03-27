try:
    from rtf_converter import rtf_to_txt
except ImportError:
    rtf_to_txt = None

def convert_rtf(file_path: str) -> str:
    """
    Converts an RTF file to a Markdown code block.
    """
    try:
        if rtf_to_txt is None:
            return "Error: rtf-converter package is not installed."
        with open(file_path, 'r') as f:
            rtf_content = f.read()
        text_content = rtf_to_txt(rtf_content)
        return f"```text\n{text_content}\n```"
    except Exception as e:
        return f"Error converting RTF file: {e}"
