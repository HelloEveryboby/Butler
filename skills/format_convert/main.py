import os
import json
import logging
from butler.core.runner_server import runner_server

logger = logging.getLogger("FormatConvertSkill")

def handle_request(action, **kwargs):
    """
    Handle document format conversion requests.
    Supports action: "run" (and others if needed)
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

    # Normalize some common type aliases
    if from_fmt == "MD": from_fmt = "MARKDOWN"
    if to_fmt == "MD": to_fmt = "MARKDOWN"
    if from_fmt == "MARKDOWN": from_fmt = "MD"
    if to_fmt == "MARKDOWN": to_fmt = "MD"
    if to_fmt == "XLSX": to_fmt = "CSV" # Fallback XLSX to CSV as designed

    # Options structure
    opts = {
        "theme": options.get("theme", "default"),
        "with_water": options.get("with_water", True),
        "config": options.get("config", {})
    }

    # 2. Check if a Go Runner is connected (Distributed Priority)
    runners = runner_server.list_runners()
    if runners:
        runner_id = runners[0] # Pick the first available runner
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

    # 3. Local Fallback Execution (Pure Python)
    logger.info("Executing format conversion locally (Python Fallback)")
    try:
        # Resolve source data
        src_content = ""
        if input_val.startswith("http://") or input_val.startswith("https://"):
            import requests
            resp = requests.get(input_val, timeout=10)
            resp.raise_for_status()
            src_content = resp.text
        elif os.path.exists(input_val):
            with open(input_val, 'r', encoding='utf-8') as f:
                src_content = f.read()
        else:
            src_content = input_val

        # Execute conversion logic based on path
        result = ""
        if from_fmt == "MD" and to_fmt == "HTML":
            result = local_md_to_html(src_content, opts)
        elif from_fmt in ["JSON", "YAML"] and to_fmt == "CSV":
            result = local_data_to_csv(src_content, from_fmt, opts)
        else:
            return f"Error: Unsupported local conversion path: {from_fmt} -> {to_fmt}"

        # Save or return
        if save_to:
            parent_dir = os.path.dirname(save_to)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            with open(save_to, 'w', encoding='utf-8') as f:
                f.write(result)
            return f"Success: Saved to {save_to}"
        else:
            return result

    except Exception as e:
        logger.error(f"Local conversion fallback failed: {e}", exc_info=True)
        return f"Error: Conversion failed locally: {str(e)}"


def local_md_to_html(md_text, opts):
    """Simple pure Python Markdown to HTML parser for zero-dependency local fallback."""
    import re
    theme = opts.get("theme", "default")
    with_water = opts.get("with_water", True)

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
            # Escape HTML characters in code block
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
                # If separator line, ignore
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
            # Simple Inline replacement
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
