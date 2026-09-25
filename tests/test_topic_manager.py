# -*- coding: utf-8 -*-
"""话题管理器测试：换话题自动存档 / 回到之前话题 / 持久化。"""

import pytest

from butler.core.topic_manager import Topic, TopicManager


@pytest.fixture
def manager(tmp_path):
    return TopicManager(store_path=tmp_path / "topics.json")


def test_observe_starts_topic(manager):
    event = manager.observe("帮我把周报排版一下")
    assert event["event"] == "switch"
    assert manager.current is not None
    assert "周报" in manager.current.title


def test_continue_same_topic(manager):
    manager.observe("帮我把周报排版一下")
    event = manager.observe("标题要加粗，正文用宋体")
    assert event["event"] == "continue"
    assert manager.current is not None
    assert len(manager.current.messages) == 2


def test_explicit_switch_archives_previous(manager):
    manager.observe("帮我把周报排版一下")
    manager.add_decision("标题加粗")
    event = manager.observe("对了，我们聊聊打印机设置")
    assert event["event"] == "switch"
    # 旧话题已存档且快照保留了决策
    old = [t for t in manager.list_topics() if t["status"] == "suspended"]
    assert old and "周报" in old[0]["title"]
    assert any("标题加粗" in d for d in old[0]["decisions"])


def test_recall_resumes_previous_topic(manager):
    manager.observe("帮我把周报排版一下")
    manager.add_open_loop("页码还没定")
    manager.observe("换个话题，打印机怎么连 wifi")
    result = manager.resume("周报排版")
    assert result["status"] == "ok"
    assert "周报" in result["topic"]
    assert "页码还没定" in result["snapshot"]
    assert "周报" in manager.current.title


def test_context_snippets_contains_current_and_archived(manager):
    manager.observe("周报排版")
    manager.observe("换个话题，打印机设置")
    block = manager.context_snippets()
    assert "当前话题" in block
    assert "已存档话题" in block


def test_persistence_across_instances(tmp_path):
    store = tmp_path / "topics.json"
    m1 = TopicManager(store_path=store)
    m1.observe("备份手机照片")
    m1.add_artifact("/photos/2026")
    m2 = TopicManager(store_path=store)
    assert m2.current is not None
    assert "备份" in m2.current.title
    assert "/photos/2026" in m2.current.artifacts


def test_snapshot_template_includes_loops(manager):
    t = manager.start_topic("测试话题")
    manager.add_open_loop("待办A")
    text = manager.snapshot_text(t)
    assert "待办A" in text and "未决" in text
