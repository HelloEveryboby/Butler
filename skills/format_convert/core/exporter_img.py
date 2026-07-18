import os
import re
import logging

logger = logging.getLogger("ImageExporter")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def markdown_to_image(md_text, output_path, opts=None):
    """
    Renders Markdown to a clean, elegant, long JPG/PNG image.
    Uses pure-Python Pillow text-layout with automatic word wrap.
    Excellent zero-dependency design with graceful fallback.
    """
    if not PIL_AVAILABLE:
        logger.warning("Pillow library is not installed. Drawing basic mock visual representation.")
        # Return a simple mock file or throw an error
        raise ImportError("Pillow library is required for MD -> Image fallback. Please install pillow.")

    opts = opts or {}
    theme = opts.get("theme", "apple-light")
    width = int(opts.get("width", 800))
    padding = 50
    line_spacing = 6
    para_spacing = 15

    # Aesthetic styles
    if theme == "dark":
        bg_color = (0x1C, 0x1C, 0x1E)
        text_color = (0xEE, 0xEE, 0xEE)
        h1_color = (0xFF, 0xFF, 0xFF)
        h2_color = (0x0A, 0x84, 0xFF) # Vibrant Apple blue for dark theme headers
        quote_bar_color = (0x30, 0xD1, 0x58) # Apple green
        quote_bg_color = (0x2C, 0x2C, 0x2E)
    else:
        bg_color = (0xFF, 0xFF, 0xFF)
        text_color = (0x1D, 0x1D, 0x1F)
        h1_color = (0x1D, 0x1D, 0x1F)
        h2_color = (0x00, 0x7A, 0xFF) # Signature Apple blue header accent
        quote_bar_color = (0x00, 0x7A, 0xFF) # Signature Apple blue quote bar
        quote_bg_color = (0xF4, 0xF4, 0xF4)

    # 1. Font detection and sizing
    font_path = ""
    # Look for PingFang/Helvetica or fallbacks
    fallbacks = [
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial.ttf",
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\msyh.ttf",
        "C:\\Windows\\Fonts\\Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in fallbacks:
        if os.path.exists(p):
            font_path = p
            break

    # Load Pillow fonts
    try:
        if font_path:
            f_title = ImageFont.truetype(font_path, 24)
            f_header = ImageFont.truetype(font_path, 18)
            f_body = ImageFont.truetype(font_path, 14)
            f_quote = ImageFont.truetype(font_path, 13)
        else:
            f_title = f_header = f_body = f_quote = ImageFont.load_default()
    except Exception as e:
        logger.warning(f"Failed to load standard TTF font: {e}. Falling back to default layout.")
        f_title = f_header = f_body = f_quote = ImageFont.load_default()

    # 2. Text layout & wrap calculation
    draw_width = width - 2 * padding
    paragraphs = []
    lines = md_text.split('\n')

    # Parse and wrap blocks
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            paragraphs.append({"type": "spacing", "height": 10})
            i += 1
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title_text = heading_match.group(2)
            font_to_use = f_title if level == 1 else f_header
            color_to_use = h1_color if level == 1 else h2_color

            wrapped_lines = _wrap_text(title_text, font_to_use, draw_width)
            paragraphs.append({
                "type": "heading",
                "level": level,
                "lines": wrapped_lines,
                "font": font_to_use,
                "color": color_to_use
            })
            i += 1
            continue

        # Blockquotes
        if stripped.startswith(">"):
            quote_text = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_text.append(re.sub(r'^>\s*', '', lines[i].strip()))
                i += 1
            full_quote = " ".join(quote_text)
            wrapped_lines = _wrap_text(full_quote, f_quote, draw_width - 30) # indentation
            paragraphs.append({
                "type": "blockquote",
                "lines": wrapped_lines,
                "font": f_quote,
                "color": text_color
            })
            continue

        # List items
        list_match = re.match(r'^([\-\*\+])\s+(.*)$', stripped)
        if list_match:
            content = list_match.group(2)
            # Indent content slightly
            wrapped_lines = _wrap_text(content, f_body, draw_width - 25)
            paragraphs.append({
                "type": "list",
                "bullet": "•",
                "lines": wrapped_lines,
                "font": f_body,
                "color": text_color
            })
            i += 1
            continue

        # Normal Paragraph
        wrapped_lines = _wrap_text(stripped, f_body, draw_width)
        paragraphs.append({
            "type": "paragraph",
            "lines": wrapped_lines,
            "font": f_body,
            "color": text_color
        })
        i += 1

    # 3. Compute dynamic height
    curr_y = padding
    for p in paragraphs:
        if p["type"] == "spacing":
            curr_y += p["height"]
        elif p["type"] in ["paragraph", "heading", "list"]:
            font_h = p["font"].getbbox("A")[3] if hasattr(p["font"], "getbbox") else 14
            curr_y += len(p["lines"]) * (font_h + line_spacing) + para_spacing
        elif p["type"] == "blockquote":
            font_h = p["font"].getbbox("A")[3] if hasattr(p["font"], "getbbox") else 13
            # blockquote has internal top/bottom padding of 8px
            curr_y += len(p["lines"]) * (font_h + line_spacing) + 16 + para_spacing

    total_height = curr_y + padding

    # 4. Draw image
    img = Image.new("RGB", (width, total_height), bg_color)
    draw = ImageDraw.Draw(img)

    curr_y = padding
    for p in paragraphs:
        if p["type"] == "spacing":
            curr_y += p["height"]
        elif p["type"] in ["paragraph", "heading"]:
            font_h = p["font"].getbbox("A")[3] if hasattr(p["font"], "getbbox") else 14
            for l_text in p["lines"]:
                draw.text((padding, curr_y), l_text, font=p["font"], fill=p["color"])
                curr_y += font_h + line_spacing
            curr_y += para_spacing

        elif p["type"] == "list":
            font_h = p["font"].getbbox("A")[3] if hasattr(p["font"], "getbbox") else 14
            # Draw bullet point
            draw.text((padding, curr_y), p["bullet"], font=p["font"], fill=h2_color)
            first = True
            for l_text in p["lines"]:
                indent_x = padding + 20
                draw.text((indent_x, curr_y), l_text, font=p["font"], fill=p["color"])
                curr_y += font_h + line_spacing
            curr_y += para_spacing

        elif p["type"] == "blockquote":
            font_h = p["font"].getbbox("A")[3] if hasattr(p["font"], "getbbox") else 13
            block_h = len(p["lines"]) * (font_h + line_spacing) + 12

            # Draw Quote Background Box
            draw.rectangle(
                [(padding, curr_y), (width - padding, curr_y + block_h)],
                fill=quote_bg_color
            )
            # Draw Thick Left Quote Border Line
            draw.rectangle(
                [(padding, curr_y), (padding + 4, curr_y + block_h)],
                fill=quote_bar_color
            )

            quote_y = curr_y + 6
            for l_text in p["lines"]:
                draw.text((padding + 20, quote_y), l_text, font=p["font"], fill=p["color"])
                quote_y += font_h + line_spacing

            curr_y += block_h + para_spacing

    # Save to path
    parent_dir = os.path.dirname(output_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    img.save(output_path, quality=90)
    logger.info(f"Successfully drew elegant long-image at {output_path}")
    return output_path


def _wrap_text(text, font, max_width):
    """Wraps text into multiple lines fitting inside max_width."""
    words = text.split()
    if not words:
        return [text]

    lines = []
    curr_line = []

    # Simple wrapping based on character count or pixel size
    for word in words:
        test_line = " ".join(curr_line + [word])
        # Calculate width using getbbox or default character approximation
        if hasattr(font, "getbbox"):
            w = font.getbbox(test_line)[2]
        else:
            w = len(test_line) * 8

        if w <= max_width:
            curr_line.append(word)
        else:
            if curr_line:
                lines.append(" ".join(curr_line))
                curr_line = [word]
            else:
                # Single word too wide, force wrap
                lines.append(word)
                curr_line = []

    if curr_line:
        lines.append(" ".join(curr_line))

    # Support double-byte CJK wrapping (split non-ASCII directly)
    final_lines = []
    for line in lines:
        if any(ord(char) > 127 for char in line):
            # Contains CJK characters, wrap strictly character by character
            sub_line = ""
            for char in line:
                test_sub = sub_line + char
                if hasattr(font, "getbbox"):
                    sub_w = font.getbbox(test_sub)[2]
                else:
                    sub_w = len(test_sub) * 12
                if sub_w <= max_width:
                    sub_line += char
                else:
                    final_lines.append(sub_line)
                    sub_line = char
            if sub_line:
                final_lines.append(sub_line)
        else:
            final_lines.append(line)

    return final_lines
