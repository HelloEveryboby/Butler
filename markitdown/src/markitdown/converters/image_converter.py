from PIL import Image
from PIL.ExifTags import TAGS
import pytesseract

def convert_image(file_path: str) -> str:
    """
    Converts an image file to Markdown.
    Extracts EXIF metadata and performs OCR.
    """
    try:
        img = Image.open(file_path)
        markdown_parts = []

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
