# -*- coding: utf-8 -*-
"""别名层测试：中文显示名 / 英文真实名映射 + 命名策略。"""

import sqlite3

import pytest

from butler.core.alias_store import AliasStore
from butler.core.naming_policy import contains_cjk, make_real_name, make_unique_name


@pytest.fixture
def store(tmp_path):
    return AliasStore(db_path=tmp_path / "alias.db")


# ---------- AliasStore ----------

def test_set_get_roundtrip(store):
    store.set_alias("data/docs", "文档")
    record = store.get("data/docs")
    assert record["display_name"] == "文档"


def test_resolve_display_fallback(store):
    assert store.resolve_display("data/docs", "docs") == "docs"   # 无别名回退原名
    store.set_alias("data/docs", "文档")
    assert store.resolve_display("data/docs", "docs") == "文档"


def test_real_name_never_changed(store):
    """别名层只存映射，真实文件名/路径保持英文（核心原则）。"""
    store.set_alias("/home/u/data/report_2026.docx", "周报.docx")
    record = store.get("/home/u/data/report_2026.docx")
    assert record["real_path"] == "/home/u/data/report_2026.docx"
    assert record["display_name"] == "周报.docx"


def test_remove_alias(store):
    store.set_alias("a.txt", "甲")
    assert store.remove("a.txt") is True
    assert store.get("a.txt") is None


def test_persistence_across_instances(tmp_path):
    db = tmp_path / "alias.db"
    s1 = AliasStore(db_path=db)
    s1.set_alias("data/docs", "文档", tags="常用")
    s2 = AliasStore(db_path=db)
    assert s2.get("data/docs")["display_name"] == "文档"


def test_find_by_display_disambiguation(store, tmp_path):
    d1, d2 = tmp_path / "a", tmp_path / "b"
    d1.mkdir(); d2.mkdir()
    store.set_alias(str(d1 / "x"), "同名")
    store.set_alias(str(d2 / "x"), "同名")
    assert len(store.find_by_display("同名")) == 2
    assert len(store.find_by_display("同名", parent_dir=str(d1))) == 1


def test_batch_suggest_and_apply(store, tmp_path):
    (tmp_path / "data_backup.zip").write_bytes(b"x")
    (tmp_path / "meeting_notes.txt").write_text("x")
    (tmp_path / "zzqqxx.unknown").write_text("x")   # 无法翻译 → 不建议

    suggestions = store.batch_suggest(str(tmp_path))
    names = {s["real_name"]: s["suggested"] for s in suggestions}
    assert names.get("data_backup.zip") == "数据备份"
    assert names.get("meeting_notes.txt") == "会议笔记"
    assert "zzqqxx.unknown" not in names

    applied = store.apply_batch({s["real_path"]: s["suggested"] for s in suggestions})
    assert applied == 2
    assert store.resolve_display(str(tmp_path / "data_backup.zip"), "data_backup.zip") == "数据备份"


def test_empty_display_name_rejected(store):
    with pytest.raises(ValueError):
        store.set_alias("a.txt", "  ")


# ---------- naming_policy ----------

def test_make_real_name_chinese_is_ascii():
    name = make_real_name("周报.docx")
    assert name.isascii() and name.endswith(".docx")
    assert not contains_cjk(name)


def test_make_real_name_mixed():
    name = make_real_name("项目 Report v2")
    assert name.isascii()
    assert "report" in name and "v2" in name


def test_make_real_name_fallback():
    name = make_real_name("！！！")
    assert name.isascii() and name.startswith("file_")


def test_make_real_name_date_suffix():
    name = make_real_name("日报", date_suffix=True)
    assert name.isascii() and any(c.isdigit() for c in name)


def test_make_unique_name_collision(tmp_path):
    first = make_unique_name(tmp_path, "笔记")
    (tmp_path / first).write_text("x")
    second = make_unique_name(tmp_path, "笔记")
    assert first != second
    assert not (tmp_path / second).exists()
