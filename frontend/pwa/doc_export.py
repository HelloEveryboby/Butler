#!/usr/bin/env python3
"""双语导出模块（frontend/pwa 后端配套）。

把上传的文档（TXT / Markdown / SRT / VTT / EPUB / PDF）抽取文本、逐段翻译，
再导出为「原文 + 译文」对照的双语文件：

  - TXT / MD  : 逐段「原文\n译文」对照
  - SRT / VTT : 每条字幕 cue 内「原文行 + 译文行」
  - EPUB      : 生成新的双语 EPUB（zip + XHTML，纯标准库）
  - PDF       : reportlab 生成双语 PDF（项目已有依赖；缺失时给出明确提示）

文本抽取依赖：
  - PDF 入参：pypdf → pdfminer.six → 系统 pdftotext，三者都没有则报错说明
  - EPUB 入参：zipfile + html.parser（标准库）

翻译默认走 package.document.translate_system（与 Butler 翻译系统同一后端），
也可通过 translate_fn 参数注入自定义翻译函数（便于测试与复用）。
"""

from __future__ import annotations

import html
import io
import os
import re
import subprocess
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# 翻译函数签名：translate(text, to, from_lang) -> str
TranslateFn = Callable[[str, Optional[str], str], str]

SUPPORTED_INPUT = ("txt", "md", "srt", "vtt", "epub", "pdf")
SUPPORTED_OUTPUT = ("txt", "md", "srt", "vtt", "epub", "pdf")


class DocExportError(RuntimeError):
    """导出失败，message 面向用户（中文、可执行的建议）。"""


# ============================================================
# 翻译接入
# ============================================================

def _default_translate_fn(text: str, to: Optional[str], from_lang: str) -> str:
    """默认翻译：复用 Butler 统一翻译系统（package.document.translate_system）。"""
    try:
        from package.document.translate_system import get_default_system
    except Exception as exc:  # noqa: BLE001
        raise DocExportError(f"翻译后端（package.document.translate_system）不可用：{exc}") from exc
    system = get_default_system()
    return system.translate(text, to=to, from_lang=from_lang)


def _make_translator(translate_fn: Optional[TranslateFn], to: Optional[str], from_lang: str):
    fn = translate_fn or _default_translate_fn

    def translate(text: str) -> str:
        if not text.strip():
            return text
        return fn(text, to, from_lang)

    return translate


# ============================================================
# 文本抽取
# ============================================================

def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def split_paragraphs(text: str) -> List[str]:
    """按空行切段；无空行的紧凑文本退化为按行切。"""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) == 1 and "\n" in parts[0]:
        parts = [p.strip() for p in parts[0].split("\n") if p.strip()]
    return parts


def extract_text(data: bytes, fmt: str) -> str:
    """从文档字节流抽取纯文本。"""
    fmt = (fmt or "").lower()
    if fmt in ("txt", "md", "text"):
        return _decode_text(data)
    if fmt in ("srt", "vtt"):
        return _decode_text(data)
    if fmt == "epub":
        return _extract_epub_text(data)
    if fmt == "pdf":
        return _extract_pdf_text(data)
    raise DocExportError(f"暂不支持的输入格式：{fmt}（支持 {'/'.join(SUPPORTED_INPUT)}）")


class _HTMLTextExtractor(HTMLParser):
    """极简 HTML 文本抽取（保留段落边界）。"""

    BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: List[str] = []
        self._buf: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self.BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip > 0:
            self._skip -= 1
        if tag in self.BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._skip == 0:
            self._buf.append(data)

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            self.chunks.append(text)
        self._buf = []

    def text(self) -> str:
        self._flush()
        return "\n\n".join(self.chunks)


def _extract_epub_text(data: bytes) -> str:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DocExportError(f"EPUB 文件损坏或不是 zip 格式：{exc}") from exc
    texts: List[str] = []
    for name in sorted(zf.namelist()):
        lower = name.lower()
        if not lower.endswith((".xhtml", ".html", ".htm")):
            continue
        try:
            raw = zf.read(name)
        except Exception:  # noqa: BLE001
            continue
        parser = _HTMLTextExtractor()
        try:
            parser.feed(_decode_text(raw))
        except Exception:  # noqa: BLE001
            continue
        text = parser.text()
        if text.strip():
            texts.append(text)
    if not texts:
        raise DocExportError("EPUB 中未提取到文本（可能是纯图片电子书）")
    return "\n\n".join(texts)


def _extract_pdf_text(data: bytes) -> str:
    # 1) pypdf
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        if text.strip():
            return text
    except Exception:  # noqa: BLE001
        pass
    # 2) pdfminer.six
    try:
        from pdfminer.high_level import extract_text  # type: ignore

        text = extract_text(io.BytesIO(data)) or ""
        if text.strip():
            return text
    except Exception:  # noqa: BLE001
        pass
    # 3) 系统 pdftotext（poppler-utils）
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            out = subprocess.run(
                ["pdftotext", tmp_path, "-"],
                capture_output=True, timeout=60, check=False,
            )
            text = out.stdout.decode("utf-8", errors="replace")
            if text.strip():
                return text
        finally:
            os.unlink(tmp_path)
    except Exception:  # noqa: BLE001
        pass
    raise DocExportError(
        "无法抽取 PDF 文本。请安装其一后重试：pip install pypdf（推荐）或 pdfminer.six，"
        "或安装 poppler-utils（提供 pdftotext 命令）。"
    )


# ============================================================
# 字幕（SRT / VTT）解析与重建
# ============================================================

_CUE_RE = re.compile(
    r"(?P<idx>\d+)\s*\n(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})[^\n]*\n(?P<text>(?:(?!\n\s*\n).)*)",
    re.MULTILINE,
)


def parse_cues(text: str) -> List[Tuple[str, str, str]]:
    """解析 SRT/VTT 字幕，返回 [(start, end, text), ...]。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for m in _CUE_RE.finditer(text):
        cues.append((m.group("start"), m.group("end"), m.group("text").strip()))
    return cues


def build_srt(cues: List[Tuple[str, str, str]]) -> str:
    lines = []
    for i, (start, end, text) in enumerate(cues, 1):
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def build_vtt(cues: List[Tuple[str, str, str]]) -> str:
    lines = ["WEBVTT", ""]
    for start, end, text in cues:
        lines.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(lines)


# ============================================================
# 双语排版
# ============================================================

def bilingual_paragraphs(paras: List[str], translate) -> List[Tuple[str, str]]:
    """逐段翻译，返回 [(原文, 译文), ...]。"""
    out = []
    for p in paras:
        out.append((p, translate(p)))
    return out


def render_txt(pairs: List[Tuple[str, str]]) -> str:
    return "\n\n".join(f"{src}\n{dst}" for src, dst in pairs)


def render_md(pairs: List[Tuple[str, str]]) -> str:
    return "\n\n".join(f"{src}\n\n> {dst}" for src, dst in pairs)


# ============================================================
# EPUB 生成（纯标准库）
# ============================================================

def _xhtml_page(title: str, pairs: List[Tuple[str, str]]) -> str:
    body_parts = []
    for src, dst in pairs:
        body_parts.append(
            f"<p class=\"src\">{html.escape(src)}</p>\n<p class=\"dst\">{html.escape(dst)}</p>"
        )
    body = "\n".join(body_parts)
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<!DOCTYPE html>\n"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"zh\" lang=\"zh\">\n"
        "<head><meta charset=\"utf-8\"/>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:sans-serif;line-height:1.7;margin:1em;}"
        ".src{color:#555;} .dst{color:#111;margin-bottom:1em;}</style>"
        "</head>\n"
        f"<body>\n<h1>{html.escape(title)}</h1>\n{body}\n</body>\n</html>\n"
    )


def render_epub(title: str, pairs: List[Tuple[str, str]]) -> bytes:
    """生成最小合规 EPUB3（双语对照）。"""
    # 控制每章段落数，避免单章过大
    chapter_size = 40
    chapters = [pairs[i:i + chapter_size] for i in range(0, len(pairs), chapter_size)] or [[]]
    chapter_names = [f"chapter{i + 1}.xhtml" for i in range(len(chapters))]

    items = []
    nav_items = []
    for i, (name, chunk) in enumerate(zip(chapter_names, chapters), 1):
        chap_title = f"{title} · 第{i}章"
        items.append(
            f'<item id="ch{i}" href="{name}" media-type="application/xhtml+xml"/>'
        )
        nav_items.append(f'<li><a href="{name}">{html.escape(chap_title)}</a></li>')

    opf = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"bid\">\n"
        "  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">\n"
        f"    <dc:identifier id=\"bid\">urn:uuid:butler-translate-{abs(hash(title))}</dc:identifier>\n"
        f"    <dc:title>{html.escape(title)}（双语对照）</dc:title>\n"
        "    <dc:language>zh</dc:language>\n"
        "    <meta property=\"dcterms:modified\">2026-01-01T00:00:00Z</meta>\n"
        "  </metadata>\n"
        "  <manifest>\n"
        "    <item id=\"nav\" href=\"nav.xhtml\" media-type=\"application/xhtml+xml\" properties=\"nav\"/>\n"
        f"    {''.join(items)}\n"
        "  </manifest>\n"
        "  <spine>\n"
        f"    {''.join(f'<itemref idref=\"ch{i}\"/>' for i in range(1, len(chapters) + 1))}\n"
        "  </spine>\n"
        "</package>\n"
    )
    nav = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<!DOCTYPE html>\n"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" "
        "xml:lang=\"zh\" lang=\"zh\">\n"
        "<head><meta charset=\"utf-8\"/><title>目录</title></head>\n"
        "<body><nav epub:type=\"toc\"><h1>目录</h1><ol>\n"
        f"{''.join(nav_items)}\n"
        "</ol></nav></body>\n</html>\n"
    )
    container = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">\n"
        "  <rootfiles>\n"
        "    <rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/>\n"
        "  </rootfiles>\n"
        "</container>\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/nav.xhtml", nav)
        for i, (name, chunk) in enumerate(zip(chapter_names, chapters), 1):
            zf.writestr(f"OEBPS/{name}", _xhtml_page(f"{title} · 第{i}章", chunk))
    return buf.getvalue()


# ============================================================
# PDF 生成（reportlab，项目已有依赖）
# ============================================================

def render_pdf(title: str, pairs: List[Tuple[str, str]]) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise DocExportError(
            f"PDF 导出需要 reportlab（项目已有依赖）：pip install reportlab（{exc}）"
        ) from exc

    # STSong-Light 是 reportlab 内置 CID 字体，无需字体文件即可显示中文。
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    src_style = ParagraphStyle("src", fontName="STSong-Light", fontSize=10, textColor="#666666",
                               leading=15, spaceAfter=2)
    dst_style = ParagraphStyle("dst", fontName="STSong-Light", fontSize=11, textColor="#111111",
                               leading=17, spaceAfter=12)
    title_style = ParagraphStyle("title", fontName="STSong-Light", fontSize=15, leading=22,
                                 spaceAfter=12)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"{title}（双语对照）")
    flow = [Paragraph(html.escape(f"{title}（双语对照）"), title_style)]
    for src, dst in pairs:
        flow.append(Paragraph(html.escape(src), src_style))
        flow.append(Paragraph(html.escape(dst), dst_style))
        flow.append(Spacer(1, 2))
    doc.build(flow)
    return buf.getvalue()


# ============================================================
# 对外入口
# ============================================================

def export_bilingual_file(
    input_path,
    output_path=None,
    to: Optional[str] = None,
    fmt: Optional[str] = None,
    from_lang: str = "auto",
    translate_fn: Optional[TranslateFn] = None,
):
    """导出双语文件。

    :param input_path: 输入文件路径
    :param output_path: 输出文件路径（默认与输入同名 .bilingual.<ext>）
    :param to: 目标语言（空则使用翻译系统默认目标语言）
    :param fmt: 输出格式 txt/md/srt/vtt/epub/pdf（默认与输入扩展名一致）
    :param from_lang: 源语言（auto=自动检测）
    :param translate_fn: 自定义翻译函数 (text, to, from_lang) -> str
    :return: 实际写出的输出路径（str）
    """
    in_path = Path(input_path)
    if not in_path.is_file():
        raise DocExportError(f"输入文件不存在：{in_path}")

    in_fmt = in_path.suffix.lstrip(".").lower() or "txt"
    out_fmt = (fmt or in_fmt).lower()
    if out_fmt == "text":
        out_fmt = "txt"
    if out_fmt not in SUPPORTED_OUTPUT:
        raise DocExportError(f"暂不支持的导出格式：{out_fmt}（支持 {'/'.join(SUPPORTED_OUTPUT)}）")

    data = in_path.read_bytes()
    raw_text = extract_text(data, in_fmt)
    if not raw_text.strip():
        raise DocExportError("未能从文档中提取到任何文本，无法生成双语对照")

    translate = _make_translator(translate_fn, to, from_lang)

    if out_fmt in ("srt", "vtt"):
        cues = parse_cues(raw_text)
        if not cues:
            # 不是有效字幕：退化为按段翻译并按字幕样式输出
            pairs = bilingual_paragraphs(split_paragraphs(raw_text), translate)
            cues = [("00:00:00,000", "00:00:05,000", f"{src}\n{dst}") for src, dst in pairs]
        else:
            cues = [(s, e, f"{txt}\n{translate(txt)}") for s, e, txt in cues]
        out_text = build_srt(cues) if out_fmt == "srt" else build_vtt(cues)
        out_bytes = out_text.encode("utf-8")
    else:
        pairs = bilingual_paragraphs(split_paragraphs(raw_text), translate)
        if not pairs:
            raise DocExportError("文档没有可翻译的段落")
        title = in_path.stem or "文档"
        if out_fmt == "txt":
            out_bytes = render_txt(pairs).encode("utf-8")
        elif out_fmt == "md":
            out_bytes = render_md(pairs).encode("utf-8")
        elif out_fmt == "epub":
            out_bytes = render_epub(title, pairs)
        else:  # pdf
            out_bytes = render_pdf(title, pairs)

    if output_path is None:
        output_path = in_path.with_name(f"{in_path.stem}.bilingual.{out_fmt}")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(out_bytes)
    return str(out)
