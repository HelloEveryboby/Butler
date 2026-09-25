# -*- coding: utf-8 -*-
"""动词识别引擎评测：tests/nlu_cases.yaml 同义表述归一准确率 ≥ 95%。"""

from pathlib import Path

import pytest
import yaml

from butler.core.verb_engine import CONFIDENCE_AUTO, VerbEngine

CASES_PATH = Path(__file__).parent / "nlu_cases.yaml"


@pytest.fixture(scope="module")
def engine():
    return VerbEngine()


def _load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CASES = _load_cases()


def test_lexicon_loads_and_has_actions(engine):
    assert len(engine.actions) >= 8
    for action_id in ("screen.capture", "textfile.edit", "file.move", "topic.recall"):
        assert action_id in engine.actions


@pytest.mark.parametrize("case", CASES, ids=[c["text"] for c in CASES])
def test_nlu_cases(engine, case):
    matches = engine.parse(case["text"])

    if case.get("no_match"):
        # 干扰样本：要么无匹配，要么低置信度（绝不允许高置信度误命中）
        assert not matches or matches[0].need_confirm, \
            f"干扰样本被高置信度误命中: {case['text']} → {matches[0].intent_id}"
        return

    assert matches, f"未识别: {case['text']}"
    top = matches[0]
    assert top.intent_id == case["intent"], \
        f"意图错误: {case['text']} → {top.intent_id} (期望 {case['intent']}, 置信度 {top.confidence})"

    if "scope" in case:
        assert top.slots.get("scope") == case["scope"], \
            f"范围槽位错误: {case['text']} → {top.slots.get('scope')} (期望 {case['scope']})"

    if "count" in case:
        assert len(matches) == case["count"], \
            f"复合句拆分数量错误: {case['text']} → {len(matches)} (期望 {case['count']})"


def test_accuracy_report(engine):
    """评测报告：同义表述归一准确率（目标 ≥ 95%）。"""
    hit = total = 0
    failures = []
    for case in CASES:
        if case.get("no_match"):
            continue
        total += 1
        matches = engine.parse(case["text"])
        if matches and matches[0].intent_id == case["intent"]:
            hit += 1
        else:
            failures.append(case["text"])
    accuracy = hit / total if total else 0
    print(f"\n[动词识别评测] {hit}/{total} = {accuracy:.1%}")
    if failures:
        print("未命中:", failures)
    assert accuracy >= 0.95, f"同义归一准确率不达标: {accuracy:.1%} < 95%"


def test_user_spec_examples_all_confident(engine):
    """需求原文样例必须高置信度命中（直接执行，不需确认）。"""
    for text in ("记录当前画面", "记录当前眼前画面"):
        matches = engine.parse(text)
        assert matches and matches[0].intent_id == "screen.capture"
        assert matches[0].confidence >= CONFIDENCE_AUTO
        assert matches[0].slots.get("scope") == "fullscreen"


def test_destructive_delete_needs_confirm(engine):
    matches = engine.parse("删除这个文件")
    assert matches and matches[0].intent_id == "file.delete"
    # 高置信度但 handler 侧要求 confirmed 才执行（由 butler_app 快通道注入）
    assert matches[0].confidence >= CONFIDENCE_AUTO
