"""双语文件导出（对标沉浸式翻译的「一键导出双语文件」）。

支持：
- 双语 PDF：pymupdf 重排版，原文段落后插入译文段落（0.8 倍字号、浅灰 #666、
  与原文同 x 位置），译文溢出当前页时自动流到下一页；
- 双语 EPUB：ebooklib + beautifulsoup4，段落/标题/列表项交错输出
  「原文 + 译文」（译文包 <span class="bt-translation">，样式写进 epub stylesheet），
  保留原 EPUB 结构（目录 / 封面 / spine / metadata）；
- 双语 SRT / VTT：每条 cue 输出「原文 + 译文」，时间轴完全不动；
  VTT 保留 WEBVTT 头和 cue 设置；
- 双语 TXT / Markdown：段落交错，Markdown 保留标题层级和代码块（代码块不翻译）；
- 双语 HTML（网页快照）：按 DOM 段落交错输出，自带内联 CSS，可直接双击打开。

翻译调用统一走 TranslationSystem（engine.py），支持传入自定义 engine 便于测试注入 mock。
可选依赖（pymupdf / ebooklib / beautifulsoup4）全部惰性导入：不安装也能 import 本模块，
对应格式的导出会在调用时报出清晰错误。
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# 进度回调：progress_cb(done, total)
ProgressCb = Optional[Callable[[int, int], None]]

# 译文样式常量
TRANS_COLOR = (0.4, 0.4, 0.4)   # 浅灰 #666
TRANS_SCALE = 0.8               # 译文字号 = 原文的 0.8 倍
TRANS_GAP = 2.0                 # 原文与译文的间距（PDF）
PARA_GAP = 6.0                  # 段落之间的间距（PDF）
PAGE_MARGIN = 36.0              # 页边距（PDF 重排版）

# 双语 HTML / EPUB 的 CSS（写进 epub stylesheet / html <style>）
BT_CSS = (
    "/* Butler 双语导出样式 */\n"
    ".bt-translation {\n"
    "  color: #666666;\n"
    "  font-size: 0.9em;\n"
    "  line-height: 1.6;\n"
    "  margin: 0.2em 0 1em 0;\n"
    "  border-left: 2px solid #dddddd;\n"
    "  padding-left: 0.6em;\n"
    "}\n"
    "span.bt-translation { display: block; }\n"
)

# HTML 里参与双语交错的块级标签
BLOCK_TAGS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li",
              "blockquote", "dd", "figcaption", "summary"]
# 这些标签内部不翻译
SKIP_TAGS = {"script", "style", "noscript", "template", "textarea", "pre", "code"}


# ---------- 可选依赖惰性导入 ----------

def _import_pymupdf():
    """惰性导入 pymupdf，未安装时抛出带说明的 RuntimeError。"""
    try:
        import pymupdf as fitz  # 新版包名
        return fitz
    except ImportError:
        pass
    try:
        import fitz  # 旧版包名
        return fitz
    except ImportError as e:
        raise RuntimeError(
            "导出双语 PDF 需要 pymupdf，请先安装：pip install pymupdf"
        ) from e


def _import_ebooklib():
    try:
        from ebooklib import epub
        import ebooklib
        return epub, ebooklib
    except ImportError as e:
        raise RuntimeError(
            "导出双语 EPUB 需要 ebooklib，请先安装：pip install ebooklib"
        ) from e


def _import_bs4():
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup
    except ImportError as e:
        raise RuntimeError(
            "导出双语 HTML/EPUB 需要 beautifulsoup4，请先安装：pip install beautifulsoup4"
        ) from e


# ---------- 翻译适配 ----------

def _call_translate(engine, text: str, to: str, use_context: bool = False) -> str:
    """调用 engine.translate，对不同签名的 mock engine 保持兼容。"""
    try:
        return engine.translate(text, to=to, use_context=use_context)
    except TypeError:
        try:
            return engine.translate(text, to=to)
        except TypeError:
            return engine.translate(text)


class _Translator:
    """统一的段落翻译器：包一层 engine，提供进度回调与空段跳过。"""

    def __init__(self, engine, target_lang: str, source_lang: str = "auto",
                 use_context: bool = False, progress_cb: ProgressCb = None):
        self.engine = engine
        self.target_lang = target_lang
        self.source_lang = source_lang
        self.use_context = use_context
        self.progress_cb = progress_cb
        self._done = 0
        self._total = 0

    def set_total(self, total: int) -> None:
        self._total = total

    def translate(self, text: str) -> str:
        result = ""
        if text and text.strip():
            result = _call_translate(self.engine, text, self.target_lang, self.use_context)
        self._done += 1
        if self.progress_cb:
            try:
                self.progress_cb(self._done, self._total)
            except Exception:  # noqa: BLE001
                pass
        return result


def _get_engine(engine=None):
    if engine is not None:
        return engine
    from . import get_default_system
    return get_default_system()


# ---------- 统一入口 ----------

def export_bilingual(
    input_path: str,
    output_path: str,
    target_lang: str,
    source_lang: str = "auto",
    engine=None,
    progress_cb: ProgressCb = None,
    use_context: bool = False,
) -> Path:
    """双语导出统一入口，按扩展名分派，返回输出路径。"""
    src = Path(input_path)
    dst = Path(output_path)
    if not src.exists():
        raise FileNotFoundError(input_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    engine = _get_engine(engine)
    translator = _Translator(engine, target_lang, source_lang, use_context, progress_cb)
    ext = src.suffix.lower()

    if ext == ".pdf":
        _export_pdf(src, dst, translator)
    elif ext == ".epub":
        _export_epub(src, dst, translator)
    elif ext == ".srt":
        _export_subtitle(src, dst, translator, fmt="srt")
    elif ext == ".vtt":
        _export_subtitle(src, dst, translator, fmt="vtt")
    elif ext in (".html", ".htm"):
        html = src.read_text(encoding="utf-8", errors="replace")
        out_html = export_bilingual_html(
            html, target_lang, source_lang, engine=engine,
            progress_cb=progress_cb, use_context=use_context)
        dst.write_text(out_html, encoding="utf-8")
    elif ext in (".md", ".markdown"):
        _export_markdown(src, dst, translator)
    elif ext in (".txt", ""):
        _export_txt(src, dst, translator)
    else:
        # 未知扩展名按纯文本处理
        _export_txt(src, dst, translator)
    return dst


# ---------- 双语 TXT / Markdown ----------

def _split_paragraphs(text: str) -> List[str]:
    """按空行切段，保留非空段落原文。"""
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _export_txt(src: Path, dst: Path, translator: _Translator) -> None:
    """双语 TXT：段落交错（原文段落 + 译文段落）。"""
    text = src.read_text(encoding="utf-8", errors="replace")
    paragraphs = _split_paragraphs(text)
    translator.set_total(len(paragraphs))
    out: List[str] = []
    for para in paragraphs:
        source = para.strip()
        trans = translator.translate(source)
        out.append(source)
        if trans:
            out.append(trans)
    dst.write_text("\n\n".join(out) + ("\n" if out else ""), encoding="utf-8")


def _export_markdown(src: Path, dst: Path, translator: _Translator) -> None:
    """双语 Markdown：保留标题层级与代码块（代码块不翻译），段落交错。"""
    text = src.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # 先统计需要翻译的段落数（进度用）
    seg_count = 0
    in_fence = False
    para_has = False
    for line in lines:
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,6}\s+\S", line) and para_has:
            seg_count += 1
            para_has = False
        if re.match(r"^#{1,6}\s+\S", line):
            seg_count += 1
        elif not line.strip():
            if para_has:
                seg_count += 1
            para_has = False
        else:
            para_has = True
    if para_has:
        seg_count += 1
    translator.set_total(max(seg_count, 1))

    out: List[str] = []
    para_buf: List[str] = []
    in_fence = False

    def flush_para() -> None:
        if not para_buf:
            return
        source = "\n".join(para_buf).strip()
        para_buf.clear()
        if not source:
            return
        out.append(source)
        trans = translator.translate(source)
        if trans:
            out.append(trans)

    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*(```|~~~)", line):
            flush_para()
            # 代码块整体保留，不翻译
            start = i
            i += 1
            while i < len(lines) and not re.match(r"^\s*(```|~~~)", lines[i]):
                i += 1
            i += 1  # 吃掉闭合围栏（若有）
            out.extend(lines[start:i])
            continue
        heading = re.match(r"^(#{1,6}\s+)(.*)$", line)
        if heading:
            flush_para()
            prefix, title = heading.group(1), heading.group(2).strip()
            out.append(line)
            if title:
                trans = translator.translate(title)
                if trans:
                    out.append(f"{prefix}{trans}")
            i += 1
            continue
        if not line.strip():
            flush_para()
            out.append("")
            i += 1
            continue
        para_buf.append(line)
        i += 1
    flush_para()
    dst.write_text("\n".join(out), encoding="utf-8")


# ---------- 双语 SRT / VTT ----------

def _parse_subtitles(content: str, fmt: str) -> Tuple[Optional[str], List[dict]]:
    """解析字幕，返回 (WEBVTT 头, cue 列表)。

    cue 结构：{"cue_id": str|None, "timing": str, "text_lines": [..]}
    非 cue 块（NOTE / STYLE 等）保留 verbatim。
    """
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", content.strip())
    header: Optional[str] = None
    cues: List[dict] = []
    if fmt == "vtt" and blocks and blocks[0].startswith("WEBVTT"):
        header = blocks[0]
        blocks = blocks[1:]
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split("\n")
        cue_id: Optional[str] = None
        timing: Optional[str] = None
        text_start = 0
        if "-->" in lines[0]:
            timing = lines[0]
            text_start = 1
        elif len(lines) > 1 and "-->" in lines[1]:
            cue_id = lines[0]
            timing = lines[1]
            text_start = 2
        if timing is None:
            # NOTE / STYLE / 注释块：原样保留
            cues.append({"verbatim": block})
            continue
        cues.append({
            "cue_id": cue_id,
            "timing": timing,  # 时间轴行完全不动（含 VTT cue 设置）
            "text_lines": lines[text_start:],
        })
    return header, cues


def _export_subtitle(src: Path, dst: Path, translator: _Translator, fmt: str) -> None:
    """双语字幕：每条 cue 输出「原文 + 译文」，时间轴完全不动。"""
    content = src.read_text(encoding="utf-8", errors="replace")
    header, cues = _parse_subtitles(content, fmt)

    real_cues = [c for c in cues if "verbatim" not in c]
    translator.set_total(len(real_cues))

    out_blocks: List[str] = []
    if header:
        out_blocks.append(header)

    for cue in cues:
        if "verbatim" in cue:
            out_blocks.append(cue["verbatim"])
            continue
        source_text = "\n".join(cue["text_lines"]).strip()
        trans = translator.translate(source_text)
        block_lines: List[str] = []
        if cue["cue_id"] is not None:
            block_lines.append(cue["cue_id"])
        block_lines.append(cue["timing"])
        block_lines.extend(cue["text_lines"])
        if trans:
            block_lines.extend(trans.split("\n"))
        out_blocks.append("\n".join(block_lines))

    dst.write_text("\n\n".join(out_blocks) + "\n", encoding="utf-8")


# ---------- 双语 HTML / EPUB（共享 DOM 交错逻辑） ----------

def _is_skipped(tag) -> bool:
    """判断该标签是否应跳过翻译（代码/脚本内，或已是译文）。"""
    if tag.name in SKIP_TAGS:
        return True
    for parent in tag.parents:
        if parent.name in SKIP_TAGS:
            return True
    classes = tag.get("class") or []
    return "bt-translation" in classes


def _bilingualize_soup(soup, translator: _Translator, li_inline: bool = True):
    """在 soup 中按块级标签交错插入译文。

    - 常规块：在原元素后插入 <p class="bt-translation"><span class="bt-translation">译文</span></p>
    - li：译文 span 直接追加到 li 内部（保持列表编号不乱）
    """
    blocks = [t for t in soup.find_all(BLOCK_TAGS) if not _is_skipped(t)]
    translator.set_total(len(blocks))
    for tag in blocks:
        source_text = tag.get_text(" ", strip=True)
        if not source_text:
            continue
        trans = translator.translate(source_text)
        if not trans:
            continue
        span = soup.new_tag("span", attrs={"class": "bt-translation"})
        span.string = trans
        if tag.name == "li" and li_inline:
            tag.append(soup.new_tag("br"))
            tag.append(span)
        else:
            wrapper = soup.new_tag("p", attrs={"class": "bt-translation"})
            wrapper.append(span)
            tag.insert_after(wrapper)
    return soup


def _ensure_bt_style(soup, href: Optional[str] = None) -> None:
    """确保 <head> 里有双语样式：href 给定时用 <link>（EPUB 共享 stylesheet）。"""
    head = soup.head
    if head is None:
        return
    if href:
        link = soup.new_tag("link", attrs={
            "rel": "stylesheet", "type": "text/css", "href": href})
        head.append(link)
    else:
        style = soup.new_tag("style")
        style.string = BT_CSS
        head.append(style)


_HTML_SKELETON = (
    "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
    "<title>{title}</title>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
)


def export_bilingual_html(
    html_str: str,
    target_lang: str,
    source_lang: str = "auto",
    engine=None,
    progress_cb: ProgressCb = None,
    use_context: bool = False,
) -> str:
    """网页快照双语导出：按 DOM 段落交错输出双语 HTML（自带内联 CSS）。"""
    BeautifulSoup = _import_bs4()
    engine = _get_engine(engine)
    translator = _Translator(engine, target_lang, source_lang, use_context, progress_cb)

    is_full_doc = bool(re.search(r"<html[\s>]", html_str, re.IGNORECASE))
    if is_full_doc:
        soup = BeautifulSoup(html_str, "html.parser")
    else:
        # 片段：补一个最小骨架，保证双击可直接打开
        soup = BeautifulSoup(
            _HTML_SKELETON.format(title="双语对照", body=html_str), "html.parser")

    # 去掉脚本/样式干扰（保留 <style> 以便原有样式生效）
    for tag in soup.find_all(["script", "noscript", "template", "textarea"]):
        tag.decompose()

    _bilingualize_soup(soup, translator)
    _ensure_bt_style(soup)
    return str(soup)


# ---------- 双语 EPUB ----------

def _export_epub(src: Path, dst: Path, translator: _Translator) -> None:
    """双语 EPUB：保留原结构（目录 / 封面 / spine / metadata），内容交错。"""
    epub, ebooklib = _import_ebooklib()
    BeautifulSoup = _import_bs4()

    book = epub.read_epub(str(src), {"ignore_ncx": False}) if _supports_read_options() \
        else epub.read_epub(str(src))

    # 共享 stylesheet（写进 epub 的 css 文件，逐文档 <link> 引用）
    style_item = epub.EpubItem(
        uid="bt-style",
        file_name="style/bt-style.css",
        media_type="text/css",
        content=BT_CSS.encode("utf-8"),
    )
    book.add_item(style_item)

    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        _bilingualize_soup(soup, translator)
        # 用相对路径把共享 stylesheet 挂进 <head>（若 head 能保留）
        doc_dir = posixpath.dirname(item.file_name)
        href = posixpath.relpath("style/bt-style.css", doc_dir or ".")
        _ensure_bt_style(soup, href=href)
        # ebooklib 写回时只保留 body 内容，故再把样式内联到 body 首部兑底
        body = soup.body
        if body is not None and body.find("style") is None:
            style = soup.new_tag("style")
            style.string = BT_CSS
            body.insert(0, style)
        item.set_content(str(soup).encode("utf-8"))

    epub.write_epub(str(dst), book)


def _supports_read_options() -> bool:
    try:
        import inspect
        from ebooklib import epub
        return "options" in inspect.signature(epub.read_epub).parameters
    except Exception:  # noqa: BLE001
        return False


# ---------- 双语 PDF（pymupdf 重排版） ----------

def _pick_font(text: str) -> str:
    """按字符集选择内置字体（原文/译文通用）。"""
    if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", text):
        return "japan"
    if re.search(r"[\uac00-\ud7af]", text):
        return "korea"
    if re.search(r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]", text):
        return "china-s"
    return "helv"


class _FontMetrics:
    """字体宽度测量缓存。"""

    def __init__(self, fitz):
        self._fitz = fitz
        self._cache = {}

    def _font(self, name: str):
        if name not in self._cache:
            self._cache[name] = self._fitz.Font(name)
        return self._cache[name]

    def text_length(self, text: str, fontname: str, fontsize: float) -> float:
        try:
            return self._font(fontname).text_length(text, fontsize=fontsize)
        except Exception:  # noqa: BLE001
            return len(text) * fontsize * 0.5


def _wrap_text(text: str, fontname: str, fontsize: float,
               max_width: float, metrics: _FontMetrics) -> List[str]:
    """按可用宽度折行（拉丁按词、CJK 按字）。"""
    lines: List[str] = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for ch in para:
            candidate = cur + ch
            if cur and metrics.text_length(candidate, fontname, fontsize) > max_width:
                # 尽量在空格处断行
                cut = cur.rfind(" ")
                if cut > 0 and not re.search(r"[\u4e00-\u9fff]", para):
                    lines.append(cur[:cut])
                    cur = cur[cut + 1:] + ch
                else:
                    lines.append(cur)
                    cur = ch
            else:
                cur = candidate
        lines.append(cur)
    return lines


class _PdfLayout:
    """PDF 输出文档的排版游标（支持自动分页）。"""

    def __init__(self, out_doc, page_w: float, page_h: float):
        self.out = out_doc
        self.w = page_w
        self.h = page_h
        self.page = out_doc.new_page(width=page_w, height=page_h)
        self.y = PAGE_MARGIN

    @property
    def bottom(self) -> float:
        return self.h - PAGE_MARGIN

    def new_page(self) -> None:
        self.page = self.out.new_page(width=self.w, height=self.h)
        self.y = PAGE_MARGIN

    def ensure(self, height: float) -> None:
        """若当前页放不下 height，则翻页（当前页已有内容时）。"""
        if self.y + height > self.bottom and self.y > PAGE_MARGIN + 0.5:
            self.new_page()


def _export_pdf(src: Path, dst: Path, translator: _Translator) -> None:
    """双语 PDF：按块重排版，原文块后插入 0.8 倍浅灰译文，溢出自动流到下一页。"""
    fitz = _import_pymupdf()
    metrics = _FontMetrics(fitz)

    src_doc = fitz.open(str(src))
    out_doc = fitz.open()

    # 统计待翻译块数（进度回调）
    page_blocks = []
    total = 0
    for page in src_doc:
        blocks = sorted(
            page.get_text("dict").get("blocks", []),
            key=lambda b: (round(b.get("bbox", (0, 0, 0, 0))[1], 1),
                           b.get("bbox", (0, 0, 0, 0))[0]),
        )
        page_blocks.append(blocks)
        total += sum(1 for b in blocks
                     if b.get("type") == 0 and _block_text(b).strip())
    translator.set_total(total)

    for page, blocks in zip(src_doc, page_blocks):
        page_w, page_h = page.rect.width, page.rect.height
        layout = _PdfLayout(out_doc, page_w, page_h)

        for block in blocks:
            bbox = block.get("bbox", (0, 0, 0, 0))
            x0, y0, x1, y1 = bbox
            block_w = x1 - x0
            max_w = max(page_w - x0 - PAGE_MARGIN, 20.0)

            if block.get("type") == 1 and block.get("image"):
                # 图片块：按原位置 x、原始尺寸放置
                img_h = y1 - y0
                layout.ensure(img_h)
                layout.page.insert_image(
                    fitz.Rect(x0, layout.y, x0 + block_w, layout.y + img_h),
                    stream=block["image"])
                layout.y += img_h + PARA_GAP
                continue

            text = _block_text(block)
            if not text.strip():
                continue

            # ---- 原文行信息 ----
            line_infos = []
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = "".join(s.get("text", "") for s in spans)
                if not line_text.strip():
                    continue
                size = max(s.get("size", 11.0) for s in spans)
                origin_y = spans[0].get("origin", (x0, y0))[1]
                line_infos.append({
                    "text": line_text,
                    "size": size,
                    "x": line.get("bbox", (x0, 0, 0, 0))[0],
                    "origin_y": origin_y,
                    "font": _pick_font(line_text),
                })
            if not line_infos:
                continue

            h_orig = y1 - y0
            base_size = max(li["size"] for li in line_infos)
            trans_size = base_size * TRANS_SCALE
            trans_text = translator.translate(text)
            # 译文字体按译文内容选（zh-CN 等语言代码本身不含 CJK 字符）
            trans_font = _pick_font(trans_text if trans_text.strip() else translator.target_lang)
            trans_lines = _wrap_text(trans_text, trans_font, trans_size, max_w, metrics) \
                if trans_text.strip() else []
            line_h = trans_size * 1.35
            h_trans = len(trans_lines) * line_h

            # 原文块 + 译文至少首行尽量同页
            layout.ensure(h_orig + (line_h if trans_lines else 0.0))

            # ---- 写原文（保持相对行距与 x 位置） ----
            for li in line_infos:
                baseline = layout.y + (li["origin_y"] - y0)
                if baseline > layout.bottom:
                    layout.new_page()
                    baseline = layout.y + (li["origin_y"] - y0)
                layout.page.insert_text(
                    (li["x"], baseline), li["text"],
                    fontname=li["font"], fontsize=li["size"], color=(0, 0, 0))
            layout.y += h_orig + TRANS_GAP

            # ---- 写译文（0.8 倍、浅灰、同 x；溢出流到下一页） ----
            for tl in trans_lines:
                if layout.y + line_h > layout.bottom:
                    layout.new_page()
                baseline = layout.y + trans_size * 0.95
                layout.page.insert_text(
                    (x0, baseline), tl,
                    fontname=trans_font, fontsize=trans_size, color=TRANS_COLOR)
                layout.y += line_h
            layout.y += PARA_GAP

        # 原页面没有内容时保留空白页，页数结构尽量对齐
        if not blocks:
            pass  # _PdfLayout 创建页时已建好空白页

    out_doc.save(str(dst))
    out_doc.close()
    src_doc.close()


def _block_text(block: dict) -> str:
    """抽取文本块的纯文本。"""
    parts = []
    for line in block.get("lines", []):
        parts.append("".join(s.get("text", "") for s in line.get("spans", [])))
    return "\n".join(parts)
