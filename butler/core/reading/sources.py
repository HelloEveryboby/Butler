"""朗读文本来源 — 文件、网页 URL、标准输入、剪贴板与原始文本。

"只要能显示文字的内容都可以读"：网页会先抽正文，HTML 文件同样处理。
原生加速：若 BHL 注册了 ``reading_extract_text``，优先走原生实现。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("ReadingSources")

SUPPORTED_FORMATS = (
    "txt, md, html/htm, docx, pdf, epub, xlsx/xlsm, pptx, csv, json, "
    "yaml, rst, 代码文本, 网页 URL, 剪贴板, 标准输入"
)

_PLAIN_SUFFIXES = {
    ".txt", ".text", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
    ".json", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".toml", ".py",
    ".js", ".ts", ".java", ".c", ".h", ".cpp", ".go", ".rs", ".sql",
    ".sh", ".bat", ".ps1", ".srt", ".vtt", ".tex", ".xml",
}


def load_source(source: str) -> tuple[str, str]:
    """返回 (正文, 展示名)。source 可为本地路径、http(s) URL 或 '-'（标准输入）。"""
    text = str(source or "").strip()
    if text in ("-", "stdin"):
        return sys.stdin.read(), "标准输入"
    if text.startswith(("http://", "https://")):
        return load_url(text), text
    path = Path(text).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        return html_to_text(_read_text_file(path)), str(path)
    if suffix == ".docx":
        return _docx_text(path), str(path)
    if suffix == ".pdf":
        return _pdf_text(path), str(path)
    if suffix == ".epub":
        return _epub_text(path), str(path)
    if suffix in (".xlsx", ".xlsm"):
        return _xlsx_text(path), str(path)
    if suffix == ".pptx":
        return _pptx_text(path), str(path)
    if suffix in _PLAIN_SUFFIXES:
        return _read_text_file(path), str(path)
    return _read_text_file(path), str(path)


def _read_text_file(path: Path) -> str:
    """按 UTF-8/GBK/自动探测依次解码，遇到二进制文件给出明确提示。"""
    raw = path.read_bytes()
    if raw.count(b"\x00") > max(8, len(raw) // 100):
        raise ValueError(
            f"无法直接读取二进制文件: {path.suffix or path.name}；"
            f"支持格式: {SUPPORTED_FORMATS}"
        )
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    try:
        import chardet

        detected = chardet.detect(raw).get("encoding")
        if detected:
            return raw.decode(detected, errors="ignore")
    except Exception:
        pass
    return raw.decode("utf-8", errors="ignore")


def _docx_text(path: Path) -> str:
    """Word：段落 + 表格文本。"""
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("读取 .docx 需要 python-docx：pip install python-docx") from exc

    document = Document(str(path))
    lines = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
    return "\n\n".join(lines)


def _pdf_text(path: Path) -> str:
    """PDF：先用 pdfplumber，再退回 pypdf；无文字层时提示改用扫描 OCR。"""
    chunks: list[str] = []
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            chunks = [(page.extract_text() or "").strip() for page in pdf.pages]
    except Exception as exc:
        logger.debug("pdfplumber 提取失败: %s", exc)

    text = "\n\n".join(chunk for chunk in chunks if chunk)
    if text.strip():
        return text

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n\n".join(
            (page.extract_text() or "").strip() for page in reader.pages
        )
    except Exception as exc:
        logger.debug("pypdf 提取失败: %s", exc)
        text = ""

    if not text.strip():
        raise ValueError(
            f"该 PDF 没有可提取的文字层（可能是扫描件）：{path.name}；"
            "可先运行 `butler scan 图片 -o out.pdf -O` 生成带文字层的 PDF"
        )
    return text


def _epub_text(path: Path) -> str:
    """EPUB：逐章抽取正文。"""
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError as exc:
        raise RuntimeError("读取 .epub 需要 ebooklib：pip install ebooklib") from exc

    book = epub.read_epub(str(path))
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="ignore")
        text = html_to_text(html).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _xlsx_text(path: Path) -> str:
    """Excel：逐表逐行转成可朗读文本。"""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("读取 .xlsx 需要 openpyxl：pip install openpyxl") from exc

    workbook = load_workbook(str(path), read_only=True, data_only=True)
    parts: list[str] = []
    for sheet in workbook.worksheets:
        lines = [f"工作表：{sheet.title}"]
        for row in sheet.iter_rows(values_only=True):
            cells = [str(value).strip() for value in row if value is not None and str(value).strip()]
            if cells:
                lines.append(" | ".join(cells))
        if len(lines) > 1:
            parts.append("\n\n".join(lines))
    workbook.close()
    return "\n\n".join(parts)


def _pptx_text(path: Path) -> str:
    """PowerPoint：逐页抽取文本框与表格文字。"""
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise RuntimeError("读取 .pptx 需要 python-pptx：pip install python-pptx") from exc

    presentation = Presentation(str(path))
    parts: list[str] = []
    for index, slide in enumerate(presentation.slides, start=1):
        lines = [f"第 {index} 页"]
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                content = shape.text_frame.text.strip()
                if content:
                    lines.append(content)
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        lines.append(" | ".join(cells))
        if len(lines) > 1:
            parts.append("\n\n".join(lines))
    return "\n\n".join(parts)


def load_url(url: str, timeout: int = 20) -> str:
    """抓取网页并抽取正文；优先使用 BHL 原生实现。"""
    from butler.core.hybrid_accel import try_native

    native = try_native("reading_extract_text", {"url": url, "timeout": timeout})
    if isinstance(native, dict) and native.get("text"):
        return str(native["text"])
    if isinstance(native, str) and native:
        return native

    import requests

    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (Butler Reader)"},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return html_to_text(response.text)


def html_to_text(html: str) -> str:
    """去脚本/导航后抽取可读正文，保留段落换行。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "aside"]):
        tag.decompose()

    root = soup.find("article") or soup.find("main") or soup.body or soup
    title = soup.title.get_text(strip=True) if soup.title else ""
    lines: list[str] = []
    for block in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "pre"]):
        content = block.get_text(" ", strip=True)
        if content:
            lines.append(content)

    if not lines:
        lines = [line.strip() for line in root.get_text("\n").splitlines() if line.strip()]

    body = "\n\n".join(lines)
    return f"{title}\n\n{body}" if title and title not in body else body


def read_clipboard() -> str:
    """读取系统剪贴板文本（依赖 tkinter，不需要额外安装）。"""
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception as exc:
        raise RuntimeError(
            "无法读取剪贴板（无图形环境或权限不足），请改用文件/URL/--text"
        ) from exc
