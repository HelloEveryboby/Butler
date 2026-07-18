import os
import zipfile
import re
import uuid
import logging

logger = logging.getLogger("EpubExporter")


def markdown_to_epub(md_text, output_path, opts=None):
    """
    Converts Markdown content into a standards-compliant .epub e-book.
    Uses pure-Python zipfile compression and standard templates (OEBPS/content.opf/toc.ncx).
    No heavy C or CLI dependencies (like pandoc) required!
    """
    opts = opts or {}
    title = opts.get("title", "Butler Document Book")
    author = opts.get("author", "Butler Automation")
    theme = opts.get("theme", "apple-light")

    # Clean up standard html lines from Markdown
    # We will build a basic HTML representation of Markdown for chapter text
    import html
    body_html = _simple_md_to_html(md_text)

    # Unique IDs for compilation
    book_id = f"urn:uuid:{uuid.uuid4()}"

    # Standard EPUB elements:
    # 1. mimetype (MUST be uncompressed and must be the first file in ZIP)
    # 2. META-INF/container.xml
    # 3. OEBPS/content.opf
    # 4. OEBPS/toc.ncx
    # 5. OEBPS/stylesheet.css
    # 6. OEBPS/chapter1.xhtml

    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""

    stylesheet_css = """body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    margin: 10%;
    color: #1d1d1f;
    background-color: #ffffff;
    line-height: 1.6;
}
h1 {
    font-size: 1.8em;
    text-align: center;
    color: #007aff;
    margin-bottom: 1.5em;
}
h2 {
    font-size: 1.4em;
    color: #1d1d1f;
    border-bottom: 1px solid #e5e5ea;
    padding-bottom: 0.3em;
}
p {
    margin-bottom: 1em;
    text-indent: 0;
}
ul, ol {
    margin-bottom: 1em;
    padding-left: 1.5em;
}
li {
    margin-bottom: 0.5em;
}
blockquote {
    border-left: 3px solid #007aff;
    background-color: #f4f4f4;
    padding: 0.5em 1em;
    margin: 1em 0;
    color: #555555;
    font-style: italic;
}
pre {
    background-color: #f5f5f7;
    border: 1px solid #e5e5ea;
    border-radius: 4px;
    padding: 1em;
    overflow-x: auto;
    font-family: monospace;
}
code {
    font-family: monospace;
    background-color: #f5f5f7;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.5em 0;
}
th, td {
    border: 1px solid #e5e5ea;
    padding: 8px;
    text-align: left;
}
th {
    background-color: #f5f5f7;
}
"""

    chapter_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{html.escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
    <div class="chapter">
        {body_html}
    </div>
</body>
</html>"""

    content_opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:title>{html.escape(title)}</dc:title>
        <dc:creator opf:role="aut">{html.escape(author)}</dc:creator>
        <dc:language>zh-CN</dc:language>
        <dc:identifier id="BookId">{book_id}</dc:identifier>
    </metadata>
    <manifest>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
        <item id="style" href="stylesheet.css" media-type="text/css"/>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine toc="ncx">
        <itemref idref="chapter1"/>
    </spine>
</package>"""

    toc_ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD NCX 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle>
        <text>{html.escape(title)}</text>
    </docTitle>
    <navMap>
        <navPoint id="navpoint-1" playOrder="1">
            <navLabel>
                <text>开始阅读</text>
            </navLabel>
            <content src="chapter1.xhtml"/>
        </navPoint>
    </navMap>
</ncx>"""

    # Ensure parent folder exists
    parent_dir = os.path.dirname(output_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    # Write out the epub zip package
    # The 'mimetype' file must be written first and uncompressed (zipfile.ZIP_STORED)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as epub:
        # 1. mimetype (first and uncompressed)
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        # 2. META-INF/container.xml
        epub.writestr("META-INF/container.xml", container_xml)

        # 3. OEBPS contents
        epub.writestr("OEBPS/content.opf", content_opf)
        epub.writestr("OEBPS/toc.ncx", toc_ncx)
        epub.writestr("OEBPS/stylesheet.css", stylesheet_css)
        epub.writestr("OEBPS/chapter1.xhtml", chapter_xhtml)

    logger.info(f"EPUB book successfully compiled & packed at {output_path}")
    return output_path


def _simple_md_to_html(md_text):
    """Extremely lightweight and clean MD parser that produces strict XHTML compliant tags."""
    import html
    lines = md_text.split('\n')
    xhtml_lines = []
    in_list = False
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            if in_code_block:
                xhtml_lines.append("</pre></code>")
                in_code_block = False
            else:
                xhtml_lines.append("<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            xhtml_lines.append(html.escape(line))
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if heading_match:
            if in_list:
                xhtml_lines.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            xhtml_lines.append(f"<h{level}>{html.escape(content)}</h{level}>")
            continue

        # Lists
        list_match = re.match(r'^[\-\*]\s+(.*)$', stripped)
        if list_match:
            if not in_list:
                xhtml_lines.append("<ul>")
                in_list = True
            xhtml_lines.append(f"<li>{html.escape(list_match.group(1))}</li>")
            continue
        elif in_list and stripped == "":
            xhtml_lines.append("</ul>")
            in_list = False

        # Tables
        if stripped.startswith("|") and stripped.endswith("|"):
            if in_list:
                xhtml_lines.append("</ul>")
                in_list = False
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cells) > 0:
                if all(re.match(r'^:?-+:?$', c) for c in cells):
                    continue
                row_str = "".join(f"<td>{html.escape(c)}</td>" for c in cells)
                xhtml_lines.append(f"<tr>{row_str}</tr>")
            continue

        # Normal Paragraphs
        if stripped:
            if in_list:
                xhtml_lines.append("</ul>")
                in_list = False
            # Basic inline rendering (bold, italic)
            line_html = html.escape(stripped)
            line_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line_html)
            line_html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', line_html)
            line_html = re.sub(r'`(.*?)`', r'<code>\1</code>', line_html)
            xhtml_lines.append(f"<p>{line_html}</p>")
        else:
            if in_list:
                xhtml_lines.append("</ul>")
                in_list = False

    if in_list:
        xhtml_lines.append("</ul>")

    return "\n".join(xhtml_lines)
