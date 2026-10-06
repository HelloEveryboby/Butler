"""译文可信度门禁的单测。

背景：曾经出现过 mock 翻译上游把原文加前缀原样回显，结果被写进缓存和
翻译记忆库，导致后续所有导出都在"成功"地输出假译文。这些用例锁住修复。
"""

from package.document.translate_system.engine import is_trustworthy


def test_same_language_trustworthy():
    # 同语种不做要求（例如 zh-CN -> zh-TW）
    assert is_trustworthy("hello", "hello", "en", "en")


def test_empty_not_trustworthy():
    assert not is_trustworthy("", "译文", "en", "zh-CN")
    assert not is_trustworthy("原文", "", "en", "zh-CN")
    assert not is_trustworthy("   ", "  ", "en", "zh-CN")


def test_identical_output_not_trustworthy():
    # 跨语种却原样返回 = 根本没翻
    assert not is_trustworthy("Hello world", "Hello world", "en", "zh-CN")
    assert not is_trustworthy("Hello world", "  Hello world  ", "en", "zh-CN")


def test_prefixed_original_rejected():
    # 真实事故特征：译文含原文且完全没有目标语言字符
    assert not is_trustworthy("Hello world", "[译文]Hello world", "en", "zh-CN")
    assert not is_trustworthy("Hello world", "Translation: Hello world", "en", "zh-CN")
    assert not is_trustworthy("Hello world", "Translation: Hello world", "en", "ja")
    assert not is_trustworthy("Привет мир", "[译文]Привет мир", "ru", "zh-CN")


def test_real_translation_accepted():
    assert is_trustworthy("Hello world", "你好，世界", "en", "zh-CN")
    assert is_trustworthy("Hello world", "こんにちは世界", "en", "ja")
    assert is_trustworthy("Hello world", "안녕하세요 세계", "en", "ko")
    assert is_trustworthy("Hello world", "Привет, мир", "en", "ru")
    assert is_trustworthy("Hello world", "مرحبا بالعالم", "en", "ar")


def test_short_source_keeps_quoted_original():
    # 原文太短时不误伤（专名、代号经常原样保留）
    assert is_trustworthy("GPT", "GPT", "en", "zh-CN") is False  # 同文仍是 False
    assert is_trustworthy("GPT", "GPT 模型", "en", "zh-CN")  # 短词 + 有中文，放行


def test_target_without_known_script_skips_rule2():
    # 目标语言没有已知字符集时，只做“完全相同”这条硬规则
    assert is_trustworthy("Hello world", "Xyz abc", "en", "xx")
    assert not is_trustworthy("Hello world", "Hello world", "en", "xx")


def test_translation_may_contain_original_for_long_nouns():
    # 合法译文可以包含原文（术语/代码/产品名），只要含目标语言字符
    assert is_trustworthy(
        "Use Transformer with PyTorch",
        "使用 Transformer 搭配 PyTorch",
        "en", "zh-CN",
    )
