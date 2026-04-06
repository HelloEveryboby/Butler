import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from markdownify import markdownify as md

def convert_epub(file_path: str) -> str:
    """
    Converts an .epub file to Markdown.
    """
    try:
        book = epub.read_epub(file_path)
        full_text = []

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            # Get text and convert to markdown
            html_content = str(soup)
            markdown_content = md(html_content, heading_style="ATX")
            full_text.append(markdown_content)

        return '\n\n'.join(full_text)
    except Exception as e:
        return f"Error converting EPub file: {e}"
