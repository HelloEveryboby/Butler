import pdfplumber
import pandas as pd
from collections import Counter

def convert_pdf(file_path: str) -> str:
    """
    Converts a .pdf file to Markdown.
    Extracts text and tables from all pages, preserving headings.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = []
            for page in pdf.pages:
                # --- Advanced Text Extraction with Heading Detection ---
                words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False, use_text_flow=True)

                if not words:
                    # Fallback for pages with no words detected
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                else:
                    # Determine the most common font size for body text
                    font_sizes = [round(word['size']) for word in words]
                    if not font_sizes:
                        continue

                    most_common_size = Counter(font_sizes).most_common(1)[0][0]

                    # Group words into lines
                    lines = {}
                    for word in words:
                        top = round(word['top'])
                        if top not in lines:
                            lines[top] = []
                        lines[top].append(word)

                    # Process lines in order
                    sorted_line_keys = sorted(lines.keys())
                    for key in sorted_line_keys:
                        line_words = sorted(lines[key], key=lambda w: w['x0'])
                        line_text = ' '.join(w['text'] for w in line_words)

                        # Simple heading detection heuristic
                        first_word_size = round(line_words[0]['size'])
                        is_bold = "bold" in line_words[0]['fontname'].lower()

                        if first_word_size > most_common_size + 2:
                            full_text.append(f"# {line_text}")
                        elif first_word_size > most_common_size or is_bold:
                            full_text.append(f"## {line_text}")
                        else:
                            full_text.append(line_text)

                # --- Table Extraction (remains the same) ---
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        df = pd.DataFrame(table[1:], columns=table[0])
                        full_text.append(df.to_markdown(index=False))

            return '\n\n'.join(full_text)
    except Exception as e:
        return f"Error converting PDF file: {e}"
