import docx

def convert_docx(file_path: str) -> str:
    """
    Converts a .docx file to Markdown.
    """
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        return f"Error converting DOCX file: {e}"
