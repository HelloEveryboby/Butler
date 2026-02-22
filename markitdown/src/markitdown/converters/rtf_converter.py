from rtf_converter import rtf_to_txt

def convert_rtf(file_path: str) -> str:
    """
    Converts an RTF file to a Markdown code block.
    """
    try:
        with open(file_path, 'r') as f:
            rtf_content = f.read()
        text_content = rtf_to_txt(rtf_content)
        return f"```text\n{text_content}\n```"
    except Exception as e:
        return f"Error converting RTF file: {e}"
