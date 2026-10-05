"""术语表单测 —— 与 frontend/translate/tests/glossary.test.ts 的 9 个用例对齐。"""

from __future__ import annotations

import pytest

from package.document.translate_system.glossary import Glossary, apply_glossary


# ---------- 与前端 glossary.test.ts 逐条对齐 ----------

def test_empty_glossary_or_text():
    """空术语表 / 空文本原样返回。"""
    assert apply_glossary("hello world", []) == "hello world"
    assert apply_glossary("", [("a", "b")]) == ""
    assert apply_glossary("hello", [("", "b")]) == "hello"


def test_basic_replacement():
    """基础替换。"""
    assert apply_glossary("the cat sat", [("cat", "猫")]) == "the 猫 sat"


def test_word_boundary_protection():
    """词边界保护：US 不会吃掉 focus / USB。"""
    g = [("US", "美国")]
    # 焦点 1：focus 中的 "us" 不能被替换
    assert apply_glossary("focus on this", g) == "focus on this"
    # 焦点 2：USB 中的 "US" 不能被替换
    assert apply_glossary("USB drive", g) == "USB drive"
    # 焦点 3：独立的 us / US 要替换，且大小写不敏感
    assert apply_glossary("in the US", g) == "in the 美国"
    assert apply_glossary("in the us", g) == "in the 美国"


def test_longest_word_priority():
    """长词优先：USB 先于 US 匹配。"""
    g = [("US", "美国"), ("USB", "通用串行总线")]
    assert apply_glossary("USB and US", g) == "通用串行总线 and 美国"


def test_cjk_no_boundary():
    """CJK 词不做词边界（中文无空格分词）。"""
    g = [("中国", "China")]
    assert apply_glossary("中国的经济", g) == "China的经济"


def test_regex_metachar_literal():
    """正则元字符按字面匹配，不会抛异常。"""
    g = [("C++", "C加加")]
    assert apply_glossary("learn C++ and C#", g) == "learn C加加 and C#"


def test_case_insensitive():
    """大小写不敏感，替换值保持术语表写死的大小写。"""
    g = [("OpenAI", "开放人工智能")]
    assert apply_glossary(
        "openai and OPENAI and OpenAI", g
    ) == "开放人工智能 and 开放人工智能 and 开放人工智能"


def test_multiple_terms():
    """多条术语同时生效。"""
    g = [("machine learning", "机器学习"), ("neural network", "神经网络")]
    assert apply_glossary(
        "machine learning uses neural network", g
    ) == "机器学习 uses 神经网络"


def test_no_chained_replacement():
    """替换结果不被后续术语二次替换（防连环替换）。"""
    g = [("A", "B"), ("B", "C")]
    assert apply_glossary("A", g) == "B"


# ---------- Glossary 类 ----------

def test_glossary_class_apply_and_persist(tmp_path):
    gl_file = tmp_path / "glossary.json"
    g = Glossary(str(gl_file))
    g.add("Transformer", "变换器")
    g.add("attention", "注意力")
    assert g.size == 2
    assert g.apply("The Transformer uses attention") == "The 变换器 uses 注意力"

    # 持久化后重新加载
    g2 = Glossary(str(gl_file))
    assert g2.get("Transformer") == "变换器"


def test_glossary_render_prompt_rules(tmp_path):
    g = Glossary(str(tmp_path / "glossary.json"))
    assert g.render_prompt_rules() == ""
    g.add("X", "Y")
    rules = g.render_prompt_rules()
    assert '"X" 必须译为 "Y"' in rules
    assert "术语强制约束" in rules


def test_glossary_replace_in_text_compat(tmp_path):
    """replace_in_text 是 apply 的兼容别名。"""
    g = Glossary(str(tmp_path / "glossary.json"))
    g.add("cat", "猫")
    assert g.replace_in_text("a cat") == g.apply("a cat") == "a 猫"


def test_glossary_add_many_and_remove(tmp_path):
    g = Glossary(str(tmp_path / "glossary.json"))
    g.add_many({"foo": "福", "bar": "巴"})
    assert g.all() == {"foo": "福", "bar": "巴"}
    assert g.remove("foo") is True
    assert g.remove("foo") is False
