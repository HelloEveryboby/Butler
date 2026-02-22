import docx
from tabulate import tabulate
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

def convert_docx(file_path: str) -> str:
    """
    Converts a .docx file to Markdown, preserving paragraphs and tables.
    """
    try:
        doc = docx.Document(file_path)
        markdown_parts = []

        for block in doc.element.body:
            if isinstance(block, CT_P):
                markdown_parts.append(Paragraph(block, doc).text)
            elif isinstance(block, CT_Tbl):
                table = Table(block, doc)
                table_data = []
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    table_data.append(row_data)

                if not table_data:
                    continue

                headers = table_data[0]
                data = table_data[1:]

                markdown_table = tabulate(data, headers=headers, tablefmt="pipe")
                markdown_parts.append(markdown_table)

        return '\n\n'.join(markdown_parts)
    except Exception as e:
        return f"Error converting DOCX file: {e}"
