import base64
import io
import shutil
import logging
from PIL import Image
from PIL.ExifTags import TAGS
import pytesseract
try:
    import easyocr
    import numpy as np
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

logger = logging.getLogger(__name__)

def convert_image(file_path: str, engine: str = "auto", model_path: str = None) -> str:
    """
    Converts an image file to Markdown.
    Embeds the image and extracts EXIF metadata and OCR text.

    Args:
        file_path: Path to the image file.
        engine: OCR engine to use ('tesseract', 'easyocr', or 'auto').
        model_path: Path to the directory containing OCR models (for offline use).
    """
    # Fallback logic for 'auto'
    if engine == "auto":
        if HAS_EASYOCR:
            engine = "easyocr"
        elif shutil.which("tesseract"):
            engine = "tesseract"
        else:
            raise RuntimeError(
                "No OCR engine found. Please install Tesseract or EasyOCR."
            )

    if engine == "tesseract" and not shutil.which("tesseract"):
        raise FileNotFoundError(
            "Tesseract OCR is not installed or not in your PATH."
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

        if engine == "easyocr":
            # EasyOCR expects a path, a numpy array, or bytes
            # If model_path is provided, use it for offline model loading
            reader = easyocr.Reader(
                ['ch_sim', 'en'],
                model_storage_directory=model_path,
                download_enabled=True if not model_path else False
            ) # Supports Simplified Chinese and English
            # Use numpy array for PIL image
            ocr_results = reader.readtext(np.array(img))
            ocr_text = "\n".join([result[1] for result in ocr_results])
        else:
            ocr_text = pytesseract.image_to_string(img)

        markdown_parts.append("```text")
        markdown_parts.append(ocr_text)
        markdown_parts.append("```")

        return '\n'.join(markdown_parts)
    except Exception as e:
        return f"Error converting image file: {e}"
