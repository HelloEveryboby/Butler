"""朗读多格式来源测试 — 使用 tests/fixtures/reading 下的真实 docx/pdf。"""

from __future__ import annotations

from pathlib import Path

import pytest

from butler.core.reading.script_parser import parse
from butler.core.reading.sources import load_source

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "reading"


def test_docx_source_extracts_dialogue():
    pytest.importorskip("docx")
    text, label = load_source(str(FIXTURES / "novel_sample.docx"))
    assert "你还没走" in text
    assert "把这封信带走" in text
    assert label.endswith("novel_sample.docx")


def test_docx_parser_assigns_multiple_speakers():
    pytest.importorskip("docx")
    text, _ = load_source(str(FIXTURES / "novel_sample.docx"))
    segments = parse(text)
    speakers = {segment.speaker for segment in segments if segment.kind == "dialogue"}
    assert {"他", "她"} <= speakers
    # "某某说"引导语不应作为旁白被朗读
    assert not any("说道" in segment.text for segment in segments)


def test_pdf_source_extracts_text_layer():
    pytest.importorskip("pdfplumber")
    text, label = load_source(str(FIXTURES / "novel_sample.pdf"))
    assert "雨下了一整夜" in text
    assert "别回头" in text
    assert label.endswith("novel_sample.pdf")
