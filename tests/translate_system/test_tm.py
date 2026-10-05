"""翻译记忆库（TM）单测：阈值分档、精确/语义/相似命中、降级路径。"""

from __future__ import annotations

import pytest

from package.document.translate_system import tm as tm_mod
from package.document.translate_system.tm import TranslationMemory


@pytest.fixture
def memory(tmp_path):
    return TranslationMemory(str(tmp_path / "tm.db"))


# ---------- 阈值分档 ----------

def test_classify_similarity_bands():
    classify = TranslationMemory.classify_similarity
    assert classify(0.99) == "semantic"
    assert classify(0.92) == "semantic"   # 阈值含端点
    assert classify(0.91) == "similar"
    assert classify(0.80) == "similar"    # 阈值含端点
    assert classify(0.79) == "none"
    assert classify(0.0) == "none"


def test_thresholds_configurable(tmp_path):
    m = TranslationMemory(str(tmp_path / "tm.db"),
                          reuse_threshold=0.5, fewshot_threshold=0.3)
    assert m.reuse_threshold == 0.5
    assert m.fewshot_threshold == 0.3
    assert m.classify_similarity(0.4, 0.5, 0.3) == "similar"


# ---------- 精确命中 ----------

def test_exact_hit(memory):
    memory.record("Hello world", "你好世界", "en", "zh-CN", "mock")
    result = memory.lookup("Hello world", "zh-CN")
    assert result.match_type == "exact"
    assert result.reusable
    assert result.entry.target == "你好世界"


def test_exact_hit_language_scoped(memory):
    memory.record("Hello", "你好", "en", "zh-CN", "mock")
    # 换目标语言不应精确命中
    result = memory.lookup("Hello", "ja")
    assert result.match_type != "exact"


# ---------- 语义命中（直接复用） ----------

def test_semantic_hit_reuses_translation(memory):
    memory.record(
        "The quick brown fox jumps over the lazy dog",
        "敏捷的棕色狐狸跳过懒狗", "en", "zh-CN", "mock")
    # 只差一个标点 → 相似度 ≥ 0.92 → 语义命中，直接复用
    result = memory.lookup("The quick brown fox jumps over the lazy dog!", "zh-CN")
    assert result.match_type == "semantic"
    assert result.reusable
    assert result.entry.target == "敏捷的棕色狐狸跳过懒狗"


def test_similar_hit_produces_fewshot(tmp_path):
    # 注入确定性打分函数，验证 0.80 ≤ sim < 0.92 的 few-shot 分档
    def fake_sim(a, b, ea, eb):
        return 0.85

    m = TranslationMemory(str(tmp_path / "tm.db"), similarity_fn=fake_sim)
    m.record("Some source sentence", "某个译文", "en", "zh-CN", "mock")
    result = m.lookup("A different query", "zh-CN")
    assert result.match_type == "similar"
    assert not result.reusable
    assert result.fewshot == [("Some source sentence", "某个译文")]


def test_no_hit(tmp_path):
    def fake_sim(a, b, ea, eb):
        return 0.1

    m = TranslationMemory(str(tmp_path / "tm.db"), similarity_fn=fake_sim)
    m.record("Some source sentence", "某个译文", "en", "zh-CN", "mock")
    result = m.lookup("Totally unrelated query", "zh-CN")
    assert result.match_type == "none"
    assert result.fewshot == []
    assert result.entry is None


def test_unrelated_text_no_false_reuse(memory):
    memory.record("Hello world, this is a test.", "你好世界，这是测试。", "en", "zh-CN", "mock")
    result = memory.lookup(
        "Completely different topic about quantum physics and thermodynamics", "zh-CN")
    assert result.match_type == "none"


def test_fewshot_capped(tmp_path):
    def fake_sim(a, b, ea, eb):
        return 0.85

    m = TranslationMemory(str(tmp_path / "tm.db"), similarity_fn=fake_sim, fewshot_max=2)
    for i in range(5):
        m.record(f"src {i}", f"tgt {i}", "en", "zh-CN", "mock")
    result = m.lookup("query", "zh-CN")
    assert result.match_type == "similar"
    assert len(result.fewshot) <= 2


# ---------- 降级路径 ----------

def test_sqlite_fallback_always_works(tmp_path):
    """向量库不可用时，降级到 SQLite（FTS5 + 编辑距离），不能崩。"""
    m = TranslationMemory(str(tmp_path / "tm.db"), backend="sqlite")
    assert m.backend_name == "sqlite"
    assert m.vector_backend is None
    m.record("fallback test", "降级测试", "en", "zh-CN", "mock")
    result = m.lookup("fallback test", "zh-CN")
    assert result.match_type == "exact"


def test_auto_backend_degrades_to_sqlite(tmp_path, monkeypatch):
    """auto 模式下 Redis/Zvec 都不可用 → 自动降级 SQLite。"""

    def boom(*args, **kwargs):
        raise ImportError("no vector store")

    monkeypatch.setattr(tm_mod, "RedisTMStore", boom)
    monkeypatch.setattr(tm_mod, "ZvecTMStore", boom)
    m = TranslationMemory(str(tmp_path / "tm.db"), backend="auto")
    assert m.backend_name == "sqlite"
    m.record("auto degrade", "自动降级", "en", "zh-CN", "mock")
    assert m.lookup("auto degrade", "zh-CN").match_type == "exact"


def test_semantic_search_works_on_sqlite_backend(memory):
    """SQLite 后端也能做语义检索（向量 + 编辑距离相似度）。"""
    memory.record("The quick brown fox jumps over the lazy dog",
                  "敏捷的棕色狐狸跳过懒狗", "en", "zh-CN", "mock")
    hits = memory._search("The quick brown fox jumps over the lazy dog?", "zh-CN", k=3)
    assert hits
    entry, sim = hits[0]
    assert entry.target == "敏捷的棕色狐狸跳过懒狗"
    assert sim >= 0.92


def test_record_and_stats(memory):
    memory.record("hello", "你好", "en", "zh-CN", "mock")
    memory.record("world", "世界", "en", "zh-CN", "mock")
    stats = memory.stats()
    assert stats["entries"] == 2
    assert stats["by_lang"].get("zh-CN") == 2
    assert stats["backend"] in ("sqlite", "redis", "zvec")
    assert len(memory.export_entries()) == 2


def test_lookup_empty_text(memory):
    assert memory.lookup("", "zh-CN").match_type == "none"
