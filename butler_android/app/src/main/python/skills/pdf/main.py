import os
import logging
from pypdf import PdfReader, PdfWriter
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

logger = logging.getLogger("PDFProSkill")

def handle_request(action, **kwargs):
    """
    Handle requests for advanced PDF processing.
    """
    entities = kwargs.get("entities", {})
    file_path = entities.get("file_path") or entities.get("path") or kwargs.get("file_path")

    if action == "extract_text":
        return extract_text(file_path)
    elif action == "extract_tables":
        return extract_tables(file_path)
    elif action == "merge":
        files = entities.get("files") or kwargs.get("files")
        output = entities.get("output") or kwargs.get("output", "merged.pdf")
        return merge_pdfs(files, output)
    elif action == "split":
        output_dir = entities.get("output_dir") or kwargs.get("output_dir", "split_pages")
        return split_pdf(file_path, output_dir)
    elif action == "create":
        text = entities.get("text") or kwargs.get("text", "Hello World")
        output = entities.get("output") or kwargs.get("output", "new.pdf")
        return create_pdf(text, output)
    elif action == "metadata":
        return get_metadata(file_path)
    elif action == "rotate":
        degrees = int(entities.get("degrees") or kwargs.get("degrees", 90))
        output = entities.get("output") or kwargs.get("output", "rotated.pdf")
        return rotate_pages(file_path, degrees, output)

    return f"Error: Action '{action}' not supported."

def extract_text(file_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error: {str(e)}"

def extract_tables(file_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    try:
        results = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if tables:
                    results.append(f"--- Page {i+1} ---")
                    for table in tables:
                        for row in table:
                            results.append(" | ".join([str(cell) if cell else "" for cell in row]))
                        results.append("")
        return "\n".join(results) if results else "No tables found."
    except Exception as e:
        return f"Error: {str(e)}"

def merge_pdfs(files, output_path):
    if not files:
        return "Error: No files provided for merging."
    try:
        writer = PdfWriter()
        for f in files:
            if os.path.exists(f):
                reader = PdfReader(f)
                for page in reader.pages:
                    writer.add_page(page)
        with open(output_path, "wb") as out:
            writer.write(out)
        return f"Successfully merged into {output_path}"
    except Exception as e:
        return f"Error: {str(e)}"

def split_pdf(file_path, output_dir):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    try:
        os.makedirs(output_dir, exist_ok=True)
        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            with open(os.path.join(output_dir, f"page_{i+1}.pdf"), "wb") as out:
                writer.write(out)
        return f"Successfully split {len(reader.pages)} pages into {output_dir}"
    except Exception as e:
        return f"Error: {str(e)}"

def create_pdf(text, output_path):
    try:
        c = canvas.Canvas(output_path, pagesize=letter)
        c.drawString(100, 750, text)
        c.save()
        return f"Successfully created {output_path}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_metadata(file_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    try:
        reader = PdfReader(file_path)
        meta = reader.metadata
        return str(meta)
    except Exception as e:
        return f"Error: {str(e)}"

def rotate_pages(file_path, degrees, output_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    try:
        reader = PdfReader(file_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(degrees)
            writer.add_page(page)
        with open(output_path, "wb") as out:
            writer.write(out)
        return f"Successfully rotated pages and saved to {output_path}"
    except Exception as e:
        return f"Error: {str(e)}"
