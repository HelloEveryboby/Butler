"""翻译系统引擎集成单测：缓存 / TM 复用 / 术语双保险 / 预设注入 / 离线模式。"""

from __future__ import annotations

import pytest

from package.document.translate_system.config import TranslateSystemConfig
from package.document.translate_system.engine import TranslationSystem
from .conftest import fake_translate


def make_system(tmp_path, mock_provider):
    cfg = TranslateSystemConfig(data_dir=str(tmp_path / "data"))
    system = TranslationSystem(cfg)
    system._provider = mock_provider
    return system


def test_translate_pipeline_and_cache(tmp_path, mock_provider):
    system = make_system(tmp_path, mock_provider)
    out = system.translate("Hello there", to="zh-CN")
    assert out == fake_translate("Hello there")
    assert mock_provider.calls == ["Hello there"]
    # 第二次走缓存，不再调用翻译源
    out2 = system.translate("Hello there", to="zh-CN")
    assert out2 == out
    assert mock_provider.calls == ["Hello there"]


def test_glossary_prompt_and_post_fallback(tmp_path, mock_provider):
    system = make_system(tmp_path, mock_provider)
    system.add_term("Transformer", "变换器")

    out = system.translate("The Transformer works", to="zh-CN")
    # 事前：术语约束进 system prompt（经 set_prompt_extras 注入）
    assert mock_provider.prompt_extras is not None
    assert "术语强制约束" in mock_provider.prompt_extras
    assert '"Transformer" 必须译为 "变换器"' in mock_provider.prompt_extras
    # 事后：译文兜底替换
    # 事后：译文兑底替换（术语被强制换成术语表写法）
    assert "变换器" in out
    assert "Transformer" not in out


def test_preset_injected_into_prompt(tmp_path, mock_provider):
    system = make_system(tmp_path, mock_provider)
    system.set_preset("legal")
    system.translate("The parties agree", to="zh-CN")
    assert "法律翻译专家" in mock_provider.prompt_extras


def test_tm_semantic_reuse_skips_provider(tmp_path, mock_provider):
    system = make_system(tmp_path, mock_provider)
    system.tm.record(
        "The quick brown fox jumps over the lazy dog",
        "敏捷的棕色狐狸跳过懒狗", "en", "zh-CN", "mock")
    # 与记忆里的句子只差一个标点 → 语义命中 → 直接复用
    out = system.translate("The quick brown fox jumps over the lazy dog!", to="zh-CN")
    assert out == "敏捷的棕色狐狸跳过懒狗"
    assert mock_provider.calls == []


def test_tm_fewshot_injected(tmp_path, mock_provider):
    system = make_system(tmp_path, mock_provider)
    system.tm.record("Some previous sentence", "某个已有译文", "en", "zh-CN", "mock")
    # 强制把相似度压进 few-shot 档位
    system.tm._similarity_fn = lambda a, b, ea, eb: 0.85
    system.translate("A vaguely similar query", to="zh-CN")
    # few-shot 在翻译时已注入，翻译完成后清理
    assert mock_provider.fewshot_history[-1] == [("Some previous sentence", "某个已有译文")]
    assert mock_provider.fewshot == []
    # 新译文已回写 TM
    assert system.tm.lookup("A vaguely similar query", "zh-CN").match_type in ("exact", "similar")


def test_tm_records_after_llm(tmp_path, mock_provider):
    system = make_system(tmp_path, mock_provider)
    system.translate("Brand new sentence", to="zh-CN")
    result = system.tm.lookup("Brand new sentence", "zh-CN")
    assert result.match_type == "exact"
    assert result.entry.target == fake_translate("Brand new sentence")


def test_use_context_injects_summary_and_terms(tmp_path):
    """translate(use_context=True)：摘要 + 术语表注入 system prompt，术语写进 Glossary。"""
    import json

    class ChatProvider:
        name = "chat-provider"

        def __init__(self):
            self.calls = []
            self.prompt_extras = None
            self.fewshot = None

        def translate(self, text, from_lang, to_lang):
            self.calls.append(text)
            return f"译文:{text}"

        def translate_batch(self, texts, from_lang, to_lang):
            return [self.translate(t, from_lang, to_lang) for t in texts]

        def set_prompt_extras(self, extras):
            self.prompt_extras = extras

        def set_fewshot(self, pairs):
            self.fewshot = pairs

        def chat(self, system_prompt, user_prompt):
            return json.dumps({
                "summary": "全文讲 Transformer。",
                "terms": [{"source": "Transformer", "target": "变换器"}],
            }, ensure_ascii=False)

    provider = ChatProvider()
    system = make_system(tmp_path, provider)
    system.translate("Some text about Transformer", to="zh-CN", use_context=True)
    # 摘要 + 术语约束进 system prompt
    assert "全文讲 Transformer。" in provider.prompt_extras
    assert '"Transformer" 必须译为 "变换器"' in provider.prompt_extras
    # 术语同时写进 Glossary → 事后兜底也生效
    assert system.glossary.get("Transformer") == "变换器"
    assert "译文:Some text about 变换器" == system.translate(
        "Some text about Transformer", to="zh-CN", use_cache=False)


def test_use_context_without_chat_degrades_gracefully(tmp_path, mock_provider):
    """provider 不支持 chat（如免费源）时，use_context 不报错，正常翻译。"""
    system = make_system(tmp_path, mock_provider)
    out = system.translate("Hello", to="zh-CN", use_context=True)
    assert out == fake_translate("Hello")


def test_offline_mode_only_local(tmp_path):
    cfg = TranslateSystemConfig(data_dir=str(tmp_path / "data"))
    cfg.offline_mode = True
    cfg.fallback_chain = ["deepseek-default", "local-llm"]
    system = TranslationSystem(cfg)
    assert system._provider.is_local is True


def test_offline_mode_without_local_raises(tmp_path):
    cfg = TranslateSystemConfig(data_dir=str(tmp_path / "data"))
    cfg.offline_mode = True
    cfg.fallback_chain = ["deepseek-default", "google-free"]
    with pytest.raises(RuntimeError):
        TranslationSystem(cfg)


class _EchoProvider:
    """事故现场重现：把原文加前缀原样回显的“翻译源”。"""

    name = "echo-provider"
    prompt_extras = None
    fewshot = None

    def translate(self, text, from_lang, to_lang):
        return f"[译文]{text}"

    def translate_batch(self, texts, from_lang, to_lang):
        return [self.translate(t, from_lang, to_lang) for t in texts]

    def set_prompt_extras(self, extras):
        self.prompt_extras = extras

    def set_fewshot(self, pairs):
        self.fewshot = pairs


def test_fake_translation_not_cached_nor_recorded(tmp_path):
    """回归锁：假译文（原文照搬）必须被门禁拦下，不写缓存、不写 TM。

    背景：曾有 mock 上游把原文加前缀回显，结果污染缓存与翻译记忆库，
    之后所有导出都在“成功”地输出假译文。
    """
    system = make_system(tmp_path, _EchoProvider())
    out = system.translate("Hello world", to="zh-CN")
    # 输出照常返回（不阻断链路），但……
    assert out == "[译文]Hello world"
    # ……绝不入库
    assert system.cache.get("Hello world", "zh-CN") is None
    assert system.tm.lookup("Hello world", "zh-CN").match_type == "none"
    assert system.last_warnings


def test_batch_fake_translation_not_recorded(tmp_path):
    system = make_system(tmp_path, _EchoProvider())
    system.translate_batch(["Hello world", "Good morning"], to="zh-CN")
    assert system.tm.lookup("Hello world", "zh-CN").match_type == "none"
    assert system.tm.lookup("Good morning", "zh-CN").match_type == "none"
    assert system.last_warnings
