"""命令记录器单测。"""

from butler.core.command_recorder import CommandRecorder, CommandSpec


def test_upsert_and_search(tmp_path):
    recorder = CommandRecorder(tmp_path / "cmd.db")
    recorder.upsert(
        CommandSpec(
            name="read",
            category="内容",
            purpose="通用朗读",
            usage="butler read x",
            aliases=["朗读"],
        )
    )
    assert recorder.get("read")["category"] == "内容"
    results = recorder.search("朗读")
    assert results and results[0]["name"] == "read"


def test_track_and_promote(tmp_path):
    recorder = CommandRecorder(tmp_path / "cmd.db")
    for _ in range(3):
        recorder.track("scan", ["a.jpg"], source="cli")
    assert recorder.promote(3) == 1
    assert recorder.get("scan")["source"] == "learned"
    assert recorder.stats()["usage_total"] == 3


def test_categories_and_combos(tmp_path):
    recorder = CommandRecorder(tmp_path / "cmd.db")
    recorder.upsert(CommandSpec(name="a", category="内容"))
    recorder.upsert(CommandSpec(name="b", category="内容"))
    assert recorder.categories()[0]["total"] == 2
    recorder.add_combo("做PDF", "图片转pdf", ["butler scan a.jpg", "butler version snapshot a.pdf"])
    assert recorder.suggest_combo("图片转pdf")
