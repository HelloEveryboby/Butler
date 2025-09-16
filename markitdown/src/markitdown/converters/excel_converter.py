import pandas as pd

def convert_excel(file_path: str) -> str:
    """
    Converts an Excel file to Markdown.
    Each sheet is converted to a separate Markdown table.
    """
    try:
        xls = pd.ExcelFile(file_path)
        markdown_parts = []
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            markdown_parts.append(f"## {sheet_name}\n")
            markdown_parts.append(df.to_markdown(index=False))

        return '\n\n'.join(markdown_parts)
    except Exception as e:
        return f"Error converting Excel file: {e}"
