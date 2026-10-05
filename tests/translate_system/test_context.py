"""AI 上下文翻译单测：JSON 解析、缓存、术语注入。"""

from __future__ import annotations

import json

import pytest

from package.document.translate_system.context import (
    ContextBuildError,
    ContextCache,
    build_context,
    parse_context_json,
    render_context_block,
)


def test_parse_context_json_strict():
    raw = json.dumps({
        "summary": "这是一篇关于 Transformer 的文章。",
        "terms": [
            {"source": "Transformer", "target": "变换器"},
            {"source": "attention", "target": "注意力"},
        ],
    }, ensure_ascii=False)
    ctx = parse_context_json(raw)
    assert ctx["summary"].startswith("这是")
    assert len(ctx["terms"]) == 2
    assert ctx["terms"][0] == {"source": "Transformer", "target": "变换器"}


def test_parse_context_json_fenced_and_noise():
    raw = '```json\n{"summary": "s", "terms": []}\n```'
    assert parse_context_json(raw)["summary"] == "s"
    raw2 = '好的，以下是 JSON：\n{"summary": "s2", "terms": [{"source": "a", "target": "b"}]}'
    assert parse_context_json(raw2)["summary"] == "s2"


def test_parse_context_json_invalid_raises():
    with pytest.raises(ContextBuildError):
        parse_context_json("完全不是 JSON")
    with pytest.raises(ContextBuildError):
        parse_context_json('{"terms": []}')  # 缺 summary
    with pytest.raises(ContextBuildError):
        parse_context_json("")


def test_render_context_block():
    ctx = {
        "summary": "全文讲了 X。",
        "terms": [{"source": "X", "target": "叉"}],
    }
    block = render_context_block(ctx)
    assert "全文讲了 X。" in block
    assert '"X" 必须译为 "叉"' in block


def test_build_context_calls_llm_once_and_caches(tmp_path):
    calls = []

    def fake_llm(system_prompt, user_prompt):
        calls.append(user_prompt)
        return json.dumps({
            "summary": "摘要内容",
            "terms": [{"source": "foo", "target": "福"}],
        }, ensure_ascii=False)

    cache = ContextCache(str(tmp_path / "ctx.json"))
    doc = "Some long document text. " * 10

    ctx1 = build_context(doc, "zh-CN", llm_fn=fake_llm, cache=cache)
    ctx2 = build_context(doc, "zh-CN", llm_fn=fake_llm, cache=cache)

    # 每篇文档只多一次 LLM 调用（缓存命中时零次）
    assert len(calls) == 1
    assert ctx1 == ctx2
    assert ctx1["terms"][0]["target"] == "福"


def test_build_context_no_llm_and_no_cache_raises(tmp_path):
    with pytest.raises(ContextBuildError):
        build_context("some text", "zh-CN", llm_fn=None,
                      cache=ContextCache(str(tmp_path / "ctx.json")))


def test_build_context_max_chars_truncates(tmp_path):
    captured = {}

    def fake_llm(system_prompt, user_prompt):
        captured["user"] = user_prompt
        return '{"summary": "s", "terms": []}'

    doc = "x" * 10000
    build_context(doc, "zh-CN", llm_fn=fake_llm, cache=None, max_chars=4000)
    # 文档被截断到 max_chars（prompt 里的原文部分）
    assert "x" * 4000 in captured["user"]
    assert "x" * 4001 not in captured["user"]


def test_context_cache_ttl_expiry(tmp_path):
    import time

    # TTL 要留足磁盘 I/O 的余量：set() 会同步写盘，若 TTL 只给 10ms，
    # 写盘耗时就可能让条目在首次 get 之前过期，造成误报。
    cache = ContextCache(str(tmp_path / "ctx.json"), ttl=0.3)
    cache.set("h1", "zh-CN", {"summary": "s", "terms": []})
    assert cache.get("h1", "zh-CN") is not None  # 未过期
    time.sleep(0.5)
    assert cache.get("h1", "zh-CN") is None  # 过期


def test_context_cache_persists_to_disk(tmp_path):
    path = str(tmp_path / "ctx.json")
    c1 = ContextCache(path, ttl=60)
    c1.set("h2", "en", {"summary": "s2", "terms": [{"source": "a", "target": "b"}]})

    # 新实例从磁盘重新加载，应能读到
    c2 = ContextCache(path, ttl=60)
    got = c2.get("h2", "en")
    assert got is not None
    assert got["summary"] == "s2"


def test_context_cache_key_isolated_by_lang(tmp_path):
    cache = ContextCache(str(tmp_path / "ctx.json"), ttl=60)
    cache.set("h3", "zh-CN", {"summary": "cn", "terms": []})
    cache.set("h3", "ja", {"summary": "jp", "terms": []})
    assert cache.get("h3", "zh-CN")["summary"] == "cn"
    assert cache.get("h3", "ja")["summary"] == "jp"
    assert cache.get("h3", "ko") is None
