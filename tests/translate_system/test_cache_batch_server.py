"""缓存键 / 批量解析 / BHL 服务端导出 的回归测试。

锁住 Pro 升级中的三处修复：
1. 缓存键改为全文哈希 + 目标语言 + 翻译源 + 术语签名，长文本不再串味；
2. 批量编号解析缺失条目时单独重试，不再把原文静默回填成译文；
3. 服务端补齐 export.pdf（缺 pymupdf 时如实报错，不假装成功）。
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json

import pytest

from package.document.translate_system.cache import TranslationCache
from package.document.translate_system.cli import build_parser
from package.document.translate_system.config import ProviderConfig
from package.document.translate_system.providers import OpenAICompatProvider
from package.document.translate_system.server import TranslationBHPServer

from .conftest import MockEngine


# ---------- 缓存键 ----------

def test_cache_key_uses_full_text(tmp_path):
    """前 120 字符与长度都相同、仅尾部不同 → 旧键会碰撞，新键必须区分。"""
    cache = TranslationCache(str(tmp_path / "cache.json"))
    a = "X" * 120 + "aaaa"
    b = "X" * 120 + "bbbb"
    assert a[:120] == b[:120] and len(a) == len(b)

    cache.set(a, "zh-CN", "译文甲")
    assert cache.get(b, "zh-CN") is None
    assert cache.get(a, "zh-CN") == "译文甲"


def test_cache_key_distinguishes_provider_and_glossary(tmp_path):
    cache = TranslationCache(str(tmp_path / "cache.json"))
    cache.set("Hello", "zh-CN", "你好", provider="p1", glossary_sig="g1")

    assert cache.get("Hello", "zh-CN", provider="p2", glossary_sig="g1") is None
    assert cache.get("Hello", "zh-CN", provider="p1", glossary_sig="g2") is None
    assert cache.get("Hello", "zh-CN", provider="p1", glossary_sig="g1") == "你好"


# ---------- 批量编号解析 ----------

def _silent_provider() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        ProviderConfig(id="test", type="openai-compat", name="test", enabled=True)
    )


def test_batch_missing_index_retried_individually():
    provider = _silent_provider()

    def fake_post(messages, max_tokens=4096, temperature=0.1):
        user = messages[-1]["content"]
        if user.startswith("请逐条翻译"):
            return "[0] 你好"  # 故意漏掉第 1 条
        return f"单独重试：{user}"

    provider._post = fake_post  # type: ignore[assignment]

    out = provider.translate_batch(["Hello", "Second"], "en", "zh-CN")
    assert out == ["你好", "单独重试：Second"]
    # 原文绝不会被当作译文回填
    assert out[1] != "Second"


def test_batch_missing_and_retry_empty_raises():
    provider = _silent_provider()

    def fake_post(messages, max_tokens=4096, temperature=0.1):
        user = messages[-1]["content"]
        if user.startswith("请逐条翻译"):
            return "[0] 你好"
        return ""  # 单条重试也失败

    provider._post = fake_post  # type: ignore[assignment]

    with pytest.raises(RuntimeError):
        provider.translate_batch(["Hello", "Second"], "en", "zh-CN")


# ---------- BHL 服务端 export.pdf ----------

class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, data):
        self.sent.append(json.loads(data))


def _pymupdf_available() -> bool:
    return bool(importlib.util.find_spec("pymupdf") or importlib.util.find_spec("fitz"))


def test_export_pdf_without_pymupdf_reports_error():
    if _pymupdf_available():
        pytest.skip("已安装 pymupdf，此用例针对缺少可选依赖时的 报错路径")

    server = object.__new__(TranslationBHPServer)
    server.system = MockEngine()
    ws = _FakeWS()
    payload = {
        "id": "req-1",
        "pdfBase64": base64.b64encode(b"%PDF-1.4 fake").decode("ascii"),
        "filename": "doc.pdf",
        "to": "zh-CN",
    }

    asyncio.run(server._handle_export_pdf(ws, payload))

    assert ws.sent and ws.sent[0]["action"] == "export.pdf.error"
    assert ws.sent[0]["payload"]["id"] == "req-1"
    assert "pymupdf" in ws.sent[0]["payload"]["message"]


def test_export_pdf_empty_payload_reports_error():
    server = object.__new__(TranslationBHPServer)
    server.system = MockEngine()
    ws = _FakeWS()

    asyncio.run(server._handle_export_pdf(ws, {"id": "req-2", "pdfBase64": ""}))

    assert ws.sent and ws.sent[0]["action"] == "export.pdf.error"


# ---------- CLI serve ----------

def test_cli_serve_subcommand():
    args = build_parser().parse_args(["serve", "--host", "0.0.0.0", "--port", "9999"])
    assert args.command == "serve"
    assert args.host == "0.0.0.0"
    assert args.port == 9999
    assert callable(args.func)
