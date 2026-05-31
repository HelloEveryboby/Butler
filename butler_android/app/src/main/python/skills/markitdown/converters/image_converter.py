import base64
import io
import shutil
from PIL import Image
from PIL.ExifTags import TAGS
import pytesseract

def convert_image(file_path: str) -> str:
    """
    Converts an image file to Markdown.
    Embeds the image and extracts EXIF metadata and OCR text.
    """
    if not shutil.which("tesseract"):
        raise FileNotFoundError(
            "Tesseract OCR is not installed or not in your PATH. "
            "Please install it from https://github.com/tesseract-ocr/tesseract "
            "and ensure it's accessible from your command line."
        )
    try:
        img = Image.open(file_path)
        markdown_parts = []

        # --- Embedded Image ---
        markdown_parts.append("## Embedded Image\n")
        # Create an in-memory buffer
        buffered = io.BytesIO()
        # Save image to buffer, preserving original format if possible
        img_format = img.format or 'PNG'  # Default to PNG if format is not detected
        img.save(buffered, format=img_format)
        # Encode to base64
        b64_string = base64.b64encode(buffered.getvalue()).decode()
        # Create the data URI
        markdown_parts.append(f"![Image](data:image/{img_format.lower()};base64,{b64_string})\n")

        # --- EXIF Metadata ---
        exif_data = img._getexif()
        if exif_data:
            markdown_parts.append("## EXIF Metadata\n")
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                # To keep it clean, decode bytes and limit value length
                if isinstance(value, bytes):
                    value = value.decode(errors="ignore")
                if len(str(value)) > 100:
                    value = str(value)[:100] + "..."
                markdown_parts.append(f"- **{tag}:** {value}")
            markdown_parts.append("\n")

        # --- OCR Text ---
        markdown_parts.append("## OCR Text\n")
        ocr_text = pytesseract.image_to_string(img)
        markdown_parts.append("```text")
        markdown_parts.append(ocr_text)
        markdown_parts.append("```")

        return '\n'.join(markdown_parts)
    except Exception as e:
        return f"Error converting image file: {e}"
