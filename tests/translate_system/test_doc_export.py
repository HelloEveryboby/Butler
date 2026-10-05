"""双语导出单测：SRT / VTT / TXT / Markdown / HTML / EPUB / PDF。"""

from __future__ import annotations

import re

import pytest

from package.document.translate_system.doc_export import (
    export_bilingual,
    export_bilingual_html,
)


# ---------- TXT ----------

def test_txt_paragraph_interleaving(tmp_path, mock_engine):
    src = tmp_path / "in.txt"
    src.write_text("Hello first paragraph.\n\nHello second paragraph.\n", encoding="utf-8")
    out = tmp_path / "out.txt"
    result = export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    assert result == out

    text = out.read_text(encoding="utf-8")
    # 段落交错：原文 → 译文 → 下一段原文 → 译文
    assert text.index("Hello first paragraph.") < text.index("译文:Hello first paragraph.")
    assert text.index("译文:Hello first paragraph.") < text.index("Hello second paragraph.")
    assert text.index("Hello second paragraph.") < text.index("译文:Hello second paragraph.")
    assert mock_engine.calls == ["Hello first paragraph.", "Hello second paragraph."]


# ---------- Markdown ----------

def test_markdown_headings_and_code_blocks(tmp_path, mock_engine):
    md = (
        "# Doc Title\n"
        "\n"
        "Intro paragraph here.\n"
        "\n"
        "```python\n"
        "def foo():\n"
        "    return 1\n"
        "```\n"
        "\n"
        "## Section Two\n"
        "\n"
        "Final paragraph.\n"
    )
    src = tmp_path / "in.md"
    src.write_text(md, encoding="utf-8")
    out = tmp_path / "out.md"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    text = out.read_text(encoding="utf-8")

    # 标题层级保留，译文带同样前缀
    assert "# Doc Title" in text
    assert "# 译文:Doc Title" in text
    assert "## Section Two" in text
    assert "## 译文:Section Two" in text
    # 代码块不翻译、原样保留
    assert "```python\ndef foo():\n    return 1\n```" in text
    assert "def foo():" not in "".join(mock_engine.calls)
    # 段落交错
    assert text.index("Intro paragraph here.") < text.index("译文:Intro paragraph here.")
    assert mock_engine.calls == ["Doc Title", "Intro paragraph here.",
                                 "Section Two", "Final paragraph."]


# ---------- SRT ----------

SRT_SAMPLE = (
    "1\n"
    "00:00:01,000 --> 00:00:04,000\n"
    "Hello world\n"
    "\n"
    "2\n"
    "00:00:05,000 --> 00:00:08,500\n"
    "How are you?\n"
)


def test_srt_timeline_unchanged(tmp_path, mock_engine):
    src = tmp_path / "in.srt"
    src.write_text(SRT_SAMPLE, encoding="utf-8")
    out = tmp_path / "out.srt"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    text = out.read_text(encoding="utf-8")

    # 时间轴完全不动
    assert text.count("00:00:01,000 --> 00:00:04,000") == 1
    assert text.count("00:00:05,000 --> 00:00:08,500") == 1
    # 序号保留
    assert re.search(r"^1$", text, re.MULTILINE)
    assert re.search(r"^2$", text, re.MULTILINE)
    # 原文 + 译文交错（译文紧跟原文之后）
    assert "Hello world\n译文:Hello world" in text
    assert "How are you?\n译文:How are you?" in text
    assert mock_engine.calls == ["Hello world", "How are you?"]


def test_srt_multiline_cue(tmp_path, mock_engine):
    src = tmp_path / "in.srt"
    src.write_text(
        "1\n00:00:01,000 --> 00:00:04,000\nLine one\nLine two\n", encoding="utf-8")
    out = tmp_path / "out.srt"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    text = out.read_text(encoding="utf-8")
    assert "Line one\nLine two\n译文:Line one\nLine two" in text


# ---------- VTT ----------

VTT_SAMPLE = (
    "WEBVTT - Test File\n"
    "\n"
    "NOTE This is a note block\n"
    "\n"
    "intro\n"
    "00:00:01.000 --> 00:00:04.000 line:90%\n"
    "Hello world\n"
)


def test_vtt_header_and_cue_settings_kept(tmp_path, mock_engine):
    src = tmp_path / "in.vtt"
    src.write_text(VTT_SAMPLE, encoding="utf-8")
    out = tmp_path / "out.vtt"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    text = out.read_text(encoding="utf-8")

    # WEBVTT 头保留
    assert text.startswith("WEBVTT - Test File")
    # NOTE 块原样保留
    assert "NOTE This is a note block" in text
    # cue id + 时间轴 + cue 设置（line:90%）原样保留
    assert "intro\n00:00:01.000 --> 00:00:04.000 line:90%\nHello world\n译文:Hello world" in text


# ---------- HTML ----------

def test_html_bilingual_interleave(mock_engine):
    html = (
        "<html><head><title>T</title></head><body>"
        "<p>Hello world</p>"
        "<pre>raw_code()</pre>"
        "<script>evil()</script>"
        "<ul><li>Item one</li></ul>"
        "</body></html>"
    )
    result = export_bilingual_html(html, "zh-CN", engine=mock_engine)

    # 段落交错 + span.bt-translation 包裹译文
    assert "Hello world" in result
    assert '<span class="bt-translation">译文:Hello world</span>' in result
    # 样式写进 head
    assert ".bt-translation" in result
    assert "<style>" in result
    # 脚本被移除
    assert "evil()" not in result
    # 代码块内容不翻译
    assert "raw_code()" in result
    assert "译文:raw_code()" not in result
    assert "raw_code()" not in "".join(mock_engine.calls)
    # 列表项交错（译文在 li 内，不破坏列表结构）
    assert "<li>Item one<br/><span class=\"bt-translation\">译文:Item one</span></li>" in result \
        or ("<li>Item one" in result and "译文:Item one" in result)
    # 原有 title 保留
    assert "<title>T</title>" in result


def test_html_fragment_gets_skeleton(mock_engine):
    result = export_bilingual_html("<p>Only a fragment.</p>", "zh-CN", engine=mock_engine)
    assert result.lstrip().startswith("<!DOCTYPE html>")
    assert "译文:Only a fragment." in result


# ---------- EPUB ----------

def _build_minimal_epub(path):
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("butler-test-1")
    book.set_title("Test Book")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter One", file_name="ch1.xhtml", lang="en")
    c1.content = "<h1>Chapter One</h1><p>First paragraph.</p><ul><li>Point A</li></ul>"
    c2 = epub.EpubHtml(title="Chapter Two", file_name="ch2.xhtml", lang="en")
    c2.content = "<p>Second chapter body.</p>"
    book.add_item(c1)
    book.add_item(c2)
    book.toc = (epub.Link("ch1.xhtml", "Chapter One", "c1"),
                epub.Link("ch2.xhtml", "Chapter Two", "c2"))
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1, c2]
    epub.write_epub(str(path), book)
    return book


def test_epub_bilingual_keeps_structure(tmp_path, mock_engine):
    epub = pytest.importorskip("ebooklib.epub", reason="需要 ebooklib")
    pytest.importorskip("bs4", reason="需要 beautifulsoup4")

    src = tmp_path / "in.epub"
    _build_minimal_epub(src)
    out = tmp_path / "out.epub"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    assert out.exists()

    # spine / 目录 / item 结构与原文件一致（对比读出来的输入文件）
    orig_book = epub.read_epub(str(src))
    orig_idrefs = [s[0] if isinstance(s, tuple) else s for s in orig_book.spine]
    book = epub.read_epub(str(out))
    idrefs = [s[0] if isinstance(s, tuple) else s for s in book.spine]
    assert idrefs == orig_idrefs
    assert "nav" in idrefs

    names = {item.file_name: item for item in book.get_items()}
    # 原有文档还在
    assert "ch1.xhtml" in names
    assert "ch2.xhtml" in names
    # 共享 stylesheet 写进 epub
    assert "style/bt-style.css" in names
    css = names["style/bt-style.css"].get_content().decode("utf-8")
    assert ".bt-translation" in css

    ch1 = names["ch1.xhtml"].get_content().decode("utf-8")
    # 原文保留 + 译文交错
    assert "Chapter One" in ch1
    assert "译文:Chapter One" in ch1
    assert "First paragraph." in ch1
    assert "译文:First paragraph." in ch1
    assert '<span class="bt-translation">' in ch1
    # 双语样式可用（内联 style 或 link 到共享 stylesheet）
    assert ".bt-translation" in ch1
    assert ("<style>" in ch1) or ("style/bt-style.css" in ch1)

    ch2 = names["ch2.xhtml"].get_content().decode("utf-8")
    assert "译文:Second chapter body." in ch2


# ---------- PDF ----------

def test_pdf_bilingual_export(tmp_path, mock_engine):
    fitz = pytest.importorskip("pymupdf", reason="需要 pymupdf")

    src = tmp_path / "in.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Hello world paragraph one.",
                     fontname="helv", fontsize=12)
    page.insert_text((50, 140), "Second line of text here.",
                     fontname="helv", fontsize=12)
    doc.save(str(src))
    doc.close()

    out = tmp_path / "out.pdf"
    result = export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    assert result == out

    out_doc = fitz.open(str(out))
    all_text = "".join(p.get_text() for p in out_doc)
    norm = re.sub(r"\s+", "", all_text)
    # 原文与译文都在（译文可能按宽度折行，这里去空白后比对）
    assert "Helloworldparagraphone." in norm
    assert "译文:Helloworldparagraphone." in norm
    assert "Secondlineoftexthere." in norm
    assert "译文:Secondlineoftexthere." in norm
    out_doc.close()


def test_pdf_overflow_flows_to_next_page(tmp_path, mock_engine):
    fitz = pytest.importorskip("pymupdf", reason="需要 pymupdf")

    src = tmp_path / "in.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for i in range(25):
        page.insert_text((50, 60 + i * 20), f"Filler line number {i:02d} here.",
                         fontname="helv", fontsize=12)
    doc.save(str(src))
    doc.close()

    out = tmp_path / "out.pdf"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)

    src_doc = fitz.open(str(src))
    out_doc = fitz.open(str(out))
    # 译文溢出 → 输出页数变多（自动流到下一页）
    assert out_doc.page_count > src_doc.page_count
    # 最后一页有内容（溢出的译文/原文）
    last_text = out_doc[-1].get_text()
    assert last_text.strip()
    src_doc.close()
    out_doc.close()


def test_pdf_cjk_text(tmp_path, mock_engine):
    fitz = pytest.importorskip("pymupdf", reason="需要 pymupdf")

    src = tmp_path / "in.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "这是中文段落。", fontname="china-s", fontsize=12)
    doc.save(str(src))
    doc.close()

    out = tmp_path / "out.pdf"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    out_doc = fitz.open(str(out))
    norm = re.sub(r"\s+", "", "".join(p.get_text() for p in out_doc))
    assert "这是中文段落。" in norm
    assert "译文:这是中文段落。" in norm
    out_doc.close()


# ---------- 进度回调 / 分派 ----------

def test_progress_callback(tmp_path, mock_engine):
    src = tmp_path / "in.txt"
    src.write_text("One.\n\nTwo.\n", encoding="utf-8")
    calls = []
    export_bilingual(str(src), str(tmp_path / "out.txt"), "zh-CN",
                     engine=mock_engine,
                     progress_cb=lambda done, total: calls.append((done, total)))
    assert calls == [(1, 2), (2, 2)]


def test_unknown_extension_treated_as_txt(tmp_path, mock_engine):
    src = tmp_path / "in.dat"
    src.write_text("Hello data.", encoding="utf-8")
    out = tmp_path / "out.dat"
    export_bilingual(str(src), str(out), "zh-CN", engine=mock_engine)
    assert "译文:Hello data." in out.read_text(encoding="utf-8")


def test_missing_input_raises(tmp_path, mock_engine):
    with pytest.raises(FileNotFoundError):
        export_bilingual(str(tmp_path / "nope.pdf"), str(tmp_path / "out.pdf"),
                         "zh-CN", engine=mock_engine)
