import pdfplumber
import pandas as pd

def convert_pdf(file_path: str) -> str:
    """
    Converts a .pdf file to Markdown.
    Extracts text and tables from all pages.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = []
            for page in pdf.pages:
                # Extract text
                text = page.extract_text()
                if text:
                    full_text.append(text)

                # Extract tables and convert to markdown
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        df = pd.DataFrame(table[1:], columns=table[0])
                        full_text.append(df.to_markdown(index=False))

            return '\n\n'.join(full_text)
    except Exception as e:
        return f"Error converting PDF file: {e}"
