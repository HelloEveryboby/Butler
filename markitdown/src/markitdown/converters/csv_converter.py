import pandas as pd

def convert_csv(file_path: str) -> str:
    """
    Converts a CSV file to a Markdown table.
    """
    try:
        df = pd.read_csv(file_path)
        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error converting CSV file: {e}"
