"""朗读脚本解析单测。"""

from butler.core.reading.script_parser import parse


def test_dialogue_speaker_and_attribution_stripped():
    segments = parse('小明说：“你好呀。”他抬起头，低声道：“我们走吧。”')
    assert segments[0].speaker == "小明"
    assert segments[0].text == "你好呀。"
    # 引导语不应被朗读
    assert all("小明说" not in seg.text for seg in segments)
    assert all(seg.text != "低声道：" for seg in segments)


def test_rate_hint_propagates_to_dialogue():
    segments = parse('他低声道：“别出声。”')
    dialogue = next(seg for seg in segments if seg.kind == "dialogue")
    assert dialogue.rate < 1.0


def test_pause_after_sentence():
    segments = parse("第一句话。第二句话。")
    assert segments[0].pause_before_ms == 0
    assert segments[1].pause_before_ms >= 400


def test_punctuation_only_not_emitted():
    segments = parse("他说：“好。”。")
    assert all(seg.text.strip("。！？ ") for seg in segments)
