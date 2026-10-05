"""AI 专家 / 行业身份预设单测：模板可加载、可组合、可导入导出。"""

from __future__ import annotations

import json

import pytest

from package.document.translate_system.presets import (
    Preset,
    PresetStore,
    builtin_presets,
    compose_system_prompt,
)


def test_builtin_presets_loaded():
    presets = builtin_presets()
    # 通用 / 技术文档 / 法律合同 / 金融研报 / 医学文献 / 文学小说 / 游戏本地化
    assert set(presets) == {"general", "tech", "legal", "finance", "medical",
                            "literary", "game"}
    for p in presets.values():
        assert p.identity
        assert p.tone
        assert p.terminology
        assert p.rules  # 数字/单位/代码处理规则


def test_preset_render_contains_all_parts():
    p = builtin_presets()["tech"]
    text = p.render("中文（简体）")
    assert "资深技术文档工程师" in text          # 身份设定
    assert "严谨" in text                        # 语气
    assert "术语倾向" in text                    # 术语倾向
    assert "处理规则" in text                    # 规则
    assert "代码块、命令行、配置片段一律不翻译" in text
    assert "中文（简体）" in text


def test_preset_roundtrip_dict():
    p = builtin_presets()["legal"]
    data = p.to_dict()
    p2 = Preset.from_dict(data)
    assert p2.id == p.id
    assert p2.rules == p.rules


def test_user_preset_save_and_load(tmp_path):
    store = PresetStore(str(tmp_path / "presets"))
    custom = Preset(
        id="my-style",
        name="我的风格",
        identity="技术布道师",
        tone="轻松幽默",
        terminology="口语化",
        rules=["保留 emoji"],
    )
    path = store.save(custom)
    assert path.exists()

    loaded = store.load()
    assert "my-style" in loaded
    assert loaded["my-style"].identity == "技术布道师"
    # 内置预设仍然可用
    assert "general" in loaded


def test_user_preset_can_override_builtin(tmp_path):
    store = PresetStore(str(tmp_path / "presets"))
    custom = Preset(id="tech", name="自定义技术", identity="自定义身份",
                    tone="t", terminology="x", rules=[])
    store.save(custom)
    loaded = store.load()
    assert loaded["tech"].identity == "自定义身份"
    assert loaded["tech"].builtin is False


def test_builtin_preset_cannot_be_deleted(tmp_path):
    store = PresetStore(str(tmp_path / "presets"))
    assert store.delete("general") is False


def test_export_import_json(tmp_path):
    store = PresetStore(str(tmp_path / "presets"))
    # 导出全部
    all_json = store.export_json()
    data = json.loads(all_json)
    assert isinstance(data, list)
    assert any(d["id"] == "game" for d in data)

    # 导入自定义并回读
    custom_json = json.dumps({
        "id": "imported", "name": "导入的", "identity": "测试员",
        "tone": "平淡", "terminology": "无", "rules": ["规则一"],
    }, ensure_ascii=False)
    imported = store.import_json(custom_json)
    assert imported[0].id == "imported"
    assert store.get("imported").rules == ["规则一"]

    # 单个导出
    one = json.loads(store.export_json("imported"))
    assert one["id"] == "imported"


def test_compose_system_prompt():
    from package.document.translate_system.presets import builtin_presets

    prompt = compose_system_prompt(
        preset=builtin_presets()["finance"],
        glossary_rules='- "GAAP" 必须译为 "公认会计原则"',
        context_block="全文摘要：这是一份财报。",
        target_lang_name="中文（简体）",
    )
    assert "金融行业分析师" in prompt     # 预设
    assert "公认会计原则" in prompt        # 术语约束
    assert "全文摘要" in prompt           # 上下文
    # 组合顺序：预设 → 上下文 → 术语
    assert (prompt.index("金融行业分析师")
            < prompt.index("全文摘要")
            < prompt.index('"GAAP" 必须译为'))


def test_compose_without_preset():
    prompt = compose_system_prompt(preset=None, glossary_rules="rules here")
    assert prompt.strip() == "rules here"
