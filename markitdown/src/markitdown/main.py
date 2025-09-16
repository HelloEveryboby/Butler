import os
import zipfile
import tempfile
import shutil
from .converters.text import convert_text
from .converters.csv_converter import convert_csv
from .converters.html_converter import convert_html
from .converters.docx_converter import convert_docx
from .converters.pptx_converter import convert_pptx
from .converters.pdf_converter import convert_pdf
from .converters.excel_converter import convert_excel
from .converters.image_converter import convert_image
from .converters.epub_converter import convert_epub

def convert(file_path: str) -> str:
    """
    Converts a file to Markdown.
    """
    _, extension = os.path.splitext(file_path)
    ext = extension.lower()

    if ext in ['.txt', '.json', '.xml']:
        return convert_text(file_path)
    elif ext == '.csv':
        return convert_csv(file_path)
    elif ext in ['.html', '.htm']:
        return convert_html(file_path)
    elif ext == '.docx':
        return convert_docx(file_path)
    elif ext == '.pptx':
        return convert_pptx(file_path)
    elif ext == '.pdf':
        return convert_pdf(file_path)
    elif ext == '.xlsx':
        return convert_excel(file_path)
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        return convert_image(file_path)
    elif ext == '.zip':
        temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            markdown_parts = []
            for root, _, files in os.walk(temp_dir):
                for name in files:
                    extracted_file_path = os.path.join(root, name)
                    markdown_parts.append(f"--- START OF {name} ---\n")
                    markdown_parts.append(convert(extracted_file_path))
                    markdown_parts.append(f"\n--- END OF {name} ---\n")

            return '\n'.join(markdown_parts)
        finally:
            shutil.rmtree(temp_dir)
    elif ext == '.epub':
        return convert_epub(file_path)
    else:
        return f"File type '{ext}' not supported yet."

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert various file formats to Markdown.")
    parser.add_argument("file_path", help="The path to the file to convert.")
    parser.add_argument("-o", "--output", help="The path to save the output Markdown file.")

    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        print(f"Error: File not found at '{args.file_path}'")
    else:
        markdown_content = convert(args.file_path)
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                print(f"Markdown content saved to '{args.output}'")
            except Exception as e:
                print(f"Error writing to output file: {e}")
        else:
            print(markdown_content)
