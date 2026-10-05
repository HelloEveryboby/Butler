"""translate_system 测试共享 fixture。"""

from __future__ import annotations

import sys
from pathlib import Path

import re

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_+\-]*\b")

# 术语/专名白名单：这些词在“译文”里原样保留（真实译文确实会这样）
_KEEP_TERMS = {"Transformer", "PyTorch", "GPT", "OpenAI"}


def fake_translate(text: str) -> str:
    """测试用假译文：**模拟真实译文的特征**，而不是「前缀 + 原文」。

    为什么不用「译文:」+ 原文：引擎的可信度门禁（engine.is_trustworthy）会拒收
    「原文照搬」这类假产出；若 mock 本身就是这种写法，等于把 bug 固化成测试期望。

    规则：术语白名单里的词原样保留，其余拉丁词换成中文占位词。
    这样产出既含目标语字符、又不整体照搬原文，能正常通过门禁。
    """
    body = _WORD_RE.sub(lambda m: m.group(0) if m.group(0) in _KEEP_TERMS else "词", text)
    return "译文：" + body


def echo_marker(text: str) -> str:
    """结构性测试用的回显标记：「译文:」+ 原文。

    只用于验证导出的段落交错 / 时间轴 / 结构完整性，
    不经过 TranslationSystem，因此不会被可信度门禁拦下。
    """
    return f"译文:{text}"


class MockEngine:
    """测试用翻译引擎：回显标记（供导出结构测试定位每段译文）。"""

    def __init__(self):
        self.calls = []

    def translate(self, text, to=None, **kwargs):
        self.calls.append(text)
        return echo_marker(text)


class MockProvider:
    """测试用翻译源：记录 prompt extras / few-shot 注入。"""

    name = "mock-provider"

    def __init__(self):
        self.calls = []
        self.prompt_extras = None
        self.fewshot = None
        self.fewshot_history = []  # 每次 translate 时快照当时的 few-shot

    def translate(self, text, from_lang, to_lang):
        self.calls.append(text)
        self.fewshot_history.append(list(self.fewshot or []))
        return fake_translate(text)

    def translate_batch(self, texts, from_lang, to_lang):
        return [self.translate(t, from_lang, to_lang) for t in texts]

    def set_prompt_extras(self, extras):
        self.prompt_extras = extras

    def set_fewshot(self, pairs):
        self.fewshot = pairs

    def chat(self, system_prompt, user_prompt):
        raise NotImplementedError


@pytest.fixture
def mock_engine():
    return MockEngine()


@pytest.fixture
def mock_provider():
    return MockProvider()
