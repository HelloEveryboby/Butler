import os
import json
import logging
import base64
import io
from butler.core.runner_server import runner_server

# Relative package imports
from .core.exporter_docx import markdown_to_docx
from .core.exporter_epub import markdown_to_epub
from .core.exporter_img import markdown_to_image
from .core.reverse_converters import html_to_markdown, docx_to_markdown, pdf_to_markdown

logger = logging.getLogger("FormatConvertSkill")


def handle_request(action, **kwargs):
    """
    Handle document format conversion requests.
    Supports action: "run" (and others if needed)
    Supports both direct contents, URL downloads, and file paths.
    """
    entities = kwargs.get("entities", {})

    # 1. Extract params from entities or direct kwargs
    input_val = entities.get("input") or kwargs.get("input")
    from_fmt = entities.get("from") or kwargs.get("from") or entities.get("from_fmt") or kwargs.get("from_fmt")
    to_fmt = entities.get("to") or kwargs.get("to") or entities.get("to_fmt") or kwargs.get("to_fmt")
    save_to = entities.get("save_to") or kwargs.get("save_to")
    options = entities.get("options") or kwargs.get("options") or {}

    if not input_val or not from_fmt or not to_fmt:
        return "Error: Missing required parameters: 'input', 'from', 'to' are mandatory."

    # Normalized formats to upper case
    from_fmt = from_fmt.upper()
    to_fmt = to_fmt.upper()

    # Normalize aliases
    if from_fmt in ["MD", "MARKDOWN"]: from_fmt = "MD"
    if to_fmt in ["MD", "MARKDOWN"]: to_fmt = "MD"
    if from_fmt in ["XLSX", "EXCEL"]: from_fmt = "XLSX"
    if to_fmt in ["XLSX", "EXCEL"]: to_fmt = "XLSX"
    if from_fmt in ["WEBP"]: from_fmt = "WEBP"
    if to_fmt in ["WEBP"]: to_fmt = "WEBP"
    if from_fmt in ["BASE64"]: from_fmt = "BASE64"
    if to_fmt in ["BASE64"]: to_fmt = "BASE64"
    if from_fmt in ["PNG"]: from_fmt = "PNG"
    if to_fmt in ["PNG"]: to_fmt = "PNG"
    if from_fmt in ["JPG", "JPEG"]: from_fmt = "JPG"
    if to_fmt in ["JPG", "JPEG"]: to_fmt = "JPG"
    if from_fmt in ["DOCX", "WORD"]: from_fmt = "DOCX"
    if to_fmt in ["DOCX", "WORD"]: to_fmt = "DOCX"
    if from_fmt in ["EPUB", "EBOOK"]: from_fmt = "EPUB"
    if to_fmt in ["EPUB", "EBOOK"]: to_fmt = "EPUB"

    # Options structure
    opts = {
        "theme": options.get("theme", "apple-light"),
        "with_water": options.get("with_water", False),
        "config": options.get("config", {})
    }

    # 2. Check if a Go Runner is connected (Distributed Priority)
    runners = runner_server.list_runners()
    if runners:
        runner_id = runners[0] # Pick the first available runner
        supported_go_paths = [
            "MD->HTML", "JSON->CSV", "YAML->CSV", "CSV->XLSX", "JSON->XLSX",
            "MD->PDF", "HTML->PDF", "JSON->MD", "CSV->MD", "PNG->WEBP", "JPG->WEBP"
        ]
        test_key = f"{from_fmt}->{to_fmt}"
        if test_key in supported_go_paths:
            logger.info(f"Delegating format conversion task to Go Runner: {runner_id}")

            # Prepare WebSocket payload
            task_payload = {
                "input": input_val,
                "from": from_fmt,
                "to": to_fmt,
                "save_to": save_to or "",
                "options": opts
            }

            # Use send_command_sync to wait blockingly for the result
            res = runner_server.send_command_sync(runner_id, "format_convert", json.dumps(task_payload))
            if res.get("status") == "ok":
                ret_data = res.get("data")
                if save_to:
                    return f"Success: {ret_data}"
                else:
                    return ret_data
            else:
                err_msg = res.get("error", "Unknown WebSocket conversion error")
                logger.warning(f"Go Runner conversion failed: {err_msg}. Falling back to local python execution.")

    # 3. Local Fallback Execution (Pure Python / Zero-Dependency Design)
    logger.info("Executing format conversion locally (Python Fallback)")
    try:
        # Resolve source data as bytes or string
        src_is_file = False
        src_bytes = b""
        src_content = ""

        # Check if the input is a file path on disk
        if isinstance(input_val, str) and os.path.exists(input_val):
            src_is_file = True
            with open(input_val, 'rb') as f:
                src_bytes = f.read()
            try:
                src_content = src_bytes.decode('utf-8')
            except UnicodeDecodeError:
                src_content = "" # Binary file
        elif isinstance(input_val, str) and (input_val.startswith("http://") or input_val.startswith("https://")):
            import requests
            resp = requests.get(input_val, timeout=10)
            resp.raise_for_status()
            src_bytes = resp.content
            try:
                src_content = src_bytes.decode('utf-8')
            except UnicodeDecodeError:
                src_content = ""
        else:
            # Direct text input
            if isinstance(input_val, str):
                src_content = input_val
                src_bytes = input_val.encode('utf-8')
            elif isinstance(input_val, bytes):
                src_bytes = input_val
                try:
                    src_content = input_val.decode('utf-8')
                except UnicodeDecodeError:
                    src_content = ""

        # --- Reverse and Cross Conversion Pipeline ---
        # Normalize non-MD sources by first converting them to MD intermediate representation
        if from_fmt != "MD":
            if from_fmt == "HTML":
                src_content = html_to_markdown(src_content)
            elif from_fmt == "DOCX":
                source_input = input_val if (src_is_file and isinstance(input_val, str)) else src_bytes
                src_content = docx_to_markdown(source_input)
            elif from_fmt == "PDF":
                source_input = input_val if (src_is_file and isinstance(input_val, str)) else src_bytes
                src_content = pdf_to_markdown(source_input)
            elif from_fmt in ["JSON", "YAML"] and to_fmt == "CSV":
                # Supported directly below
                pass
            elif from_fmt in ["JSON", "CSV"] and to_fmt == "MD":
                # Supported directly below
                pass
            else:
                logger.info(f"Format {from_fmt} converted to intermediate Markdown before exporting.")

            # Route to MD if target requires standard export, otherwise maintain for specialized handlers
            if from_fmt in ["PNG", "JPG"] and to_fmt in ["WEBP", "BASE64"]:
                pass
            elif from_fmt in ["JSON", "YAML", "CSV"] and to_fmt in ["CSV", "MD", "XLSX"]:
                pass
            else:
                from_fmt = "MD"

        # Execute target conversion logic
        result = ""
        if from_fmt == "MD" and to_fmt == "HTML":
            result = local_md_to_html(src_content, opts)
        elif from_fmt == "MD" and to_fmt == "DOCX":
            if save_to:
                result = markdown_to_docx(src_content, save_to, opts)
                return f"Success: Saved to {save_to}"
            else:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    markdown_to_docx(src_content, tmp_path, opts)
                    with open(tmp_path, 'rb') as f:
                        result = f.read()
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

        elif from_fmt == "MD" and to_fmt == "EPUB":
            if save_to:
                result = markdown_to_epub(src_content, save_to, opts)
                return f"Success: Saved to {save_to}"
            else:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    markdown_to_epub(src_content, tmp_path, opts)
                    with open(tmp_path, 'rb') as f:
                        result = f.read()
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

        elif from_fmt == "MD" and to_fmt in ["PNG", "JPG"]:
            if save_to:
                result = markdown_to_image(src_content, save_to, opts)
                return f"Success: Saved to {save_to}"
            else:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    markdown_to_image(src_content, tmp_path, opts)
                    with open(tmp_path, 'rb') as f:
                        result = f.read()
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

        elif from_fmt in ["JSON", "YAML"] and to_fmt == "CSV":
            result = local_data_to_csv(src_content, from_fmt, opts)
        elif to_fmt == "XLSX":
            result = _local_fallback_xlsx(src_content, from_fmt, opts)
        elif to_fmt == "MD":
            if from_fmt == "MD":
                result = src_content
            else:
                result = _local_fallback_md(src_content, from_fmt, opts)
        elif to_fmt in ["WEBP", "BASE64"] or from_fmt in ["PNG", "JPG"]:
            result = _local_fallback_image(src_content, from_fmt, to_fmt, opts)
        elif to_fmt == "PDF":
            result = _local_fallback_pdf(src_content, from_fmt, opts)
            if not isinstance(result, bytes) and save_to:
                with open(save_to, 'w', encoding='utf-8') as f:
                    f.write(result)
                return f"Success: Saved to {save_to}"
            elif isinstance(result, bytes) and save_to:
                with open(save_to, 'wb') as f:
                    f.write(result)
                return f"Success: Saved to {save_to}"
        else:
            return f"Error: Unsupported local conversion path: {from_fmt} -> {to_fmt}"

        # Save or return
        if save_to:
            parent_dir = os.path.dirname(save_to)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            if isinstance(result, bytes):
                with open(save_to, 'wb') as f:
                    f.write(result)
            else:
                with open(save_to, 'w', encoding='utf-8') as f:
                    f.write(result)
            return f"Success: Saved to {save_to}"
        else:
            if isinstance(result, bytes):
                return base64.b64encode(result).decode('utf-8')
            return result

    except Exception as e:
        logger.error(f"Local conversion fallback failed: {e}", exc_info=True)
        return f"Error: Conversion failed locally: {str(e)}"


def local_md_to_html(md_text, opts):
    """Simple pure Python Markdown to HTML parser for zero-dependency local fallback."""
    import re
    theme = opts.get("theme", "apple-light")
    with_water = opts.get("with_water", False)

    lines = md_text.split('\n')
    html_lines = []
    in_list = False
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Code block handling
        if stripped.startswith("```"):
            if in_code_block:
                html_lines.append("</pre></code>")
                in_code_block = False
            else:
                html_lines.append("<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_lines.append(escaped)
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if heading_match:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            html_lines.append(f"<h{level}>{content}</h{level}>")
            continue

        # Lists
        list_match = re.match(r'^[\-\*]\s+(.*)$', stripped)
        if list_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{list_match.group(1)}</li>")
            continue
        elif in_list and stripped == "":
            html_lines.append("</ul>")
            in_list = False

        # Table rows (very simple Markdown table parser)
        if stripped.startswith("|") and stripped.endswith("|"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cells) > 0:
                if all(re.match(r'^:?-+:?$', c) for c in cells):
                    continue
                row_str = "".join(f"<td>{c}</td>" for c in cells)
                html_lines.append(f"<tr>{row_str}</tr>")
            continue

        # Paragraph
        if stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            line_html = stripped
            line_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line_html)
            line_html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', line_html)
            line_html = re.sub(r'`(.*?)`', r'<code>\1</code>', line_html)
            line_html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', line_html)
            html_lines.append(f"<p>{line_html}</p>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False

    if in_list:
        html_lines.append("</ul>")

    body_content = "\n".join(html_lines)

    # Wrap in html template
    html_header = f"""<!DOCTYPE html>
<html data-theme="{theme}">
<head>
<meta charset="UTF-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 2rem; background: var(--bg-color, #ffffff); color: var(--text-color, #333333); line-height: 1.6; }}
.butler-content {{ max-width: 800px; margin: 0 auto; }}
.butler-footer {{ text-align: center; margin-top: 3rem; font-size: 0.85rem; color: #888888; border-top: 1px solid #eaeaea; padding-top: 1.5rem; }}
pre {{ background: #f6f8fa; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
code {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 0.85em; }}
table {{ border-collapse: collapse; width: 100%; margin: 1.5rem 0; }}
th, td {{ border: 1px solid #eaeaea; padding: 8px 12px; text-align: left; }}
th {{ background-color: #f6f8fa; }}
</style>
</head>
<body>
<div class="butler-content">
{body_content}
</div>"""

    footer_text = "Generated by Butler Automation Service"
    if with_water:
        footer_text = "Generated by Butler Automation Service | Secure Watermarked Document"

    html_footer = f"""<footer class="butler-footer">{footer_text}</footer>
</body>
</html>"""

    return html_header + "\n" + html_footer


def local_data_to_csv(data_text, from_fmt, opts):
    """Flattens nested JSON or YAML and converts it to CSV."""
    import csv
    import io

    if from_fmt == "JSON":
        raw_data = json.loads(data_text)
    elif from_fmt == "YAML":
        import yaml
        raw_data = yaml.safe_load(data_text)
    else:
        raise ValueError(f"Unsupported format for local conversion: {from_fmt}")

    if isinstance(raw_data, list):
        items = raw_data
    elif isinstance(raw_data, dict):
        items = [raw_data]
    else:
        raise ValueError("Unsupported data structure for conversion to CSV")

    if not items:
        raise ValueError("Empty data set")

    # Flatten helper
    flat_items = []
    all_keys = set()

    for item in items:
        flat = {}
        _flatten_dict(item, "", flat)
        flat_items.append(flat)
        all_keys.update(flat.keys())

    sorted_keys = sorted(list(all_keys))

    # Write CSV using python's csv.writer
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(sorted_keys)

    # Rows
    for flat in flat_items:
        row = [flat.get(k, "") for k in sorted_keys]
        writer.writerow(row)

    return output.getvalue()


def _flatten_dict(val, prefix, current):
    if val is None:
        current[prefix] = ""
    elif isinstance(val, dict):
        for k, v in val.items():
            next_prefix = f"{prefix}.{k}" if prefix else k
            _flatten_dict(v, next_prefix, current)
    elif isinstance(val, list):
        for i, v in enumerate(val):
            next_prefix = f"{prefix}.{i}"
            _flatten_dict(v, next_prefix, current)
    elif isinstance(val, bool):
        current[prefix] = str(val).lower()
    else:
        current[prefix] = str(val)


def _local_fallback_xlsx(src_content, from_fmt, opts):
    """Local fallback for Excel: Prepend UTF-8 BOM to allow double-clicking on Windows."""
    logger.warning("Warning: Local XLSX fallback generated a BOM-marked CSV file instead.")
    csv_data = ""
    if from_fmt in ["JSON", "YAML"]:
        csv_data = local_data_to_csv(src_content, from_fmt, opts)
    else:
        csv_data = src_content
    # Return UTF-8 BOM marked CSV string
    return "\ufeff" + csv_data


def _local_fallback_pdf(src_content, from_fmt, opts):
    """Local fallback for PDF: Try using reportlab flowable layouting; otherwise fall back."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        # Build clean custom styles
        title_style = ParagraphStyle(
            'ApplePDFTitle',
            parent=styles['Heading1'],
            fontSize=22,
            leading=26,
            textColor='#1D1D1F',
            spaceAfter=15
        )
        body_style = ParagraphStyle(
            'ApplePDFBody',
            parent=styles['Normal'],
            fontSize=11,
            leading=15,
            textColor='#333333',
            spaceAfter=8
        )

        story = []
        for line in src_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                story.append(Paragraph(line[2:], title_style))
                story.append(Spacer(1, 10))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], styles['Heading2']))
                story.append(Spacer(1, 8))
            else:
                story.append(Paragraph(line, body_style))
                story.append(Spacer(1, 6))

        doc.build(story)
        return pdf_buffer.getvalue()

    except Exception as e:
        logger.warning(f"ReportLab PDF generation fallback skipped or failed: {e}. Raising standard exception.")
        raise ValueError("Local fallback for PDF is not supported. Please connect a Go Runner.")


def _local_fallback_md(src_content, from_fmt, opts):
    """Generates Markdown table from JSON or CSV in pure Python."""
    import csv
    import io

    rows = []
    if from_fmt == "JSON":
        data = json.loads(src_content)
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError("JSON data must be a list of objects or a single object")

        # Flatten objects
        flat_items = []
        all_keys = set()
        for item in data:
            flat = {}
            _flatten_dict(item, "", flat)
            flat_items.append(flat)
            all_keys.update(flat.keys())

        sorted_keys = sorted(list(all_keys))
        rows.append(sorted_keys)
        for flat in flat_items:
            row = [flat.get(k, "") for k in sorted_keys]
            rows.append(row)
    elif from_fmt == "CSV":
        f = io.StringIO(src_content)
        reader = csv.reader(f)
        rows = list(reader)
    else:
        raise ValueError(f"Unsupported source format for Markdown table: {from_fmt}")

    if not rows:
        return "*No data available.*\n"

    headers = rows[0]
    data_rows = rows[1:]

    def escape_cell(val):
        val_str = str(val)
        val_str = val_str.replace("|", "\\|")
        val_str = val_str.replace("\r\n", "<br />").replace("\n", "<br />")
        return val_str

    # Render Table
    md_lines = []
    md_lines.append("| " + " | ".join(escape_cell(h) for h in headers) + " |")
    md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in data_rows:
        md_lines.append("| " + " | ".join(escape_cell(val) for val in row) + " |")

    return "\n".join(md_lines) + "\n"


def _local_fallback_image(src_content, from_fmt, to_fmt, opts):
    """Converts image to WebP or Base64 in pure Python."""
    import io

    binary_data = b""
    if src_content.startswith("http://") or src_content.startswith("https://"):
        import requests
        resp = requests.get(src_content, timeout=10)
        resp.raise_for_status()
        binary_data = resp.content
    elif os.path.exists(src_content):
        with open(src_content, 'rb') as f:
            binary_data = f.read()
    else:
        # Assume it's a base64 encoded string or raw string
        try:
            binary_data = base64.b64decode(src_content)
        except Exception:
            binary_data = src_content.encode('utf-8')

    if to_fmt == "BASE64":
        encoded = base64.b64encode(binary_data).decode('utf-8')
        if opts.get("config", {}).get("WithDataUri", False):
            fmt = from_fmt.lower()
            if fmt == "jpeg":
                fmt = "jpg"
            encoded = f"data:image/{fmt};base64," + encoded
        return encoded

    elif to_fmt == "WEBP":
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(binary_data))
            out_buf = io.BytesIO()
            quality = opts.get("config", {}).get("quality", 80)
            img.save(out_buf, format="WEBP", quality=quality)
            return out_buf.getvalue()
        except ImportError:
            raise ImportError("Pillow library is required for local WebP image conversion. Please install pillow or connect a Go Runner.")
        except Exception as e:
            raise ValueError(f"Image WebP conversion failed: {e}")
    else:
        raise ValueError(f"Unsupported image target format: {to_fmt}")
