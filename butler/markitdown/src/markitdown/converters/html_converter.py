from markdownify import markdownify as md

def convert_html(file_path: str) -> str:
    """
    Converts an HTML file to Markdown.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return md(html_content)
    except Exception as e:
        return f"Error converting HTML file: {e}"
