"""脚本解析 — 把小说正文拆成带说话人、停顿与语速提示的朗读片段。

解析完全在本地完成（零 token）：
  - 识别 “…” / 「…」 / 『…』 与英文双引号对白
  - 把"某某说/道/问"这类引导语用于判定说话人，但不进入朗读文本
  - 依据标点计算停顿，依据"低声/缓缓/大声"等描述调节语速
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_QUOTE_PATTERN = re.compile(r'[“「『](.+?)[”」』]|"([^"\n]{1,300})"')

_ATTR_WORDS = (
    "低声道|沉声道|喃喃道|怒吼道|笑道|说道|问道|答道|喊道|喝道|说|道|问|答|喊"
)
_PRE_SPEAKER = re.compile(rf"([\u4e00-\u9fa5]{{1,4}}?)(?:{_ATTR_WORDS})[：:，,]?\s*$")
_POST_SPEAKER = re.compile(
    rf"^\s*[，,。！？!?…]*\s*([\u4e00-\u9fa5]{{1,4}}?)(?:{_ATTR_WORDS})"
)
_ONLY_ATTRIBUTION = re.compile(
    rf"^[\u4e00-\u9fa5]{{1,4}}(?:{_ATTR_WORDS})[：:，,。！？!?…]*$"
)
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])")
_WORD_CHAR = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9]")
_MODIFIERS = {"低声", "沉声", "轻声", "高声", "喃喃", "冷笑", "怒", "大喊"}
_TRAILING_ATTRIBUTION = re.compile(
    rf"[，,]\s*(?:[\u4e00-\u9fa5]{{1,4}}?)?(?:{_ATTR_WORDS})[：:，,。！？!?…]*\s*$"
)
# 引导语里出现这些字时多半是正常叙述（如"他不知道。"），不应当作"某某说"删除
_ATTRIB_SKIP_CHARS = set("不没知会能要想是有在让把被")

RATE_HINTS: tuple[tuple[str, float], ...] = (
    ("飞快", 1.25),
    ("急促", 1.2),
    ("大声", 1.15),
    ("喊道", 1.15),
    ("怒吼", 1.2),
    ("缓缓", 0.8),
    ("慢慢", 0.85),
    ("轻声", 0.85),
    ("低声", 0.85),
    ("悄悄", 0.85),
    ("喃喃", 0.8),
)

EMOTION_HINTS: tuple[tuple[str, str], ...] = (
    ("笑", "cheerful"),
    ("怒", "angry"),
    ("吼", "angry"),
    ("喝", "angry"),
    ("哭", "sad"),
    ("泪", "sad"),
    ("哽咽", "sad"),
    ("低声", "gentle"),
    ("轻声", "gentle"),
    ("喃喃", "gentle"),
)


@dataclass
class Segment:
    """一个朗读片段。"""

    index: int
    speaker: str
    text: str
    kind: str                 # narration | dialogue
    pause_before_ms: int
    rate: float
    emotion_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "speaker": self.speaker,
            "text": self.text,
            "kind": self.kind,
            "pause_before_ms": self.pause_before_ms,
            "rate": self.rate,
            "emotion_hint": self.emotion_hint,
        }


def _paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r\n", "\n"))]
    parts = [p for p in parts if p]
    return parts or ([text.strip()] if text.strip() else [])


def _pause_ms(text: str) -> int:
    tail = text.strip()
    if not tail:
        return 0
    if tail.endswith(("……", "...")):
        return 800
    if tail.endswith(("。", "！", "？", "!", "?", ".")):
        return 500
    if tail.endswith(("；", ";")):
        return 350
    if tail.endswith(("，", ",", "、", "：")):
        return 200
    return 150


def _rate_for(text: str, default_rate: float) -> float:
    rate = default_rate
    for word, factor in RATE_HINTS:
        if word in text:
            rate = default_rate * factor
            break
    return round(max(0.5, min(2.0, rate)), 2)


def _emotion_for(text: str) -> str:
    for word, hint in EMOTION_HINTS:
        if word in text:
            return hint
    return ""


_PRONOUNS = ("他们", "她们", "我们", "你们", "他", "她", "我", "你")
_PRONOUN_PATTERN = re.compile("|".join(_PRONOUNS))
# 含这些字的候选多半是修饰语/动词而非人名（如"笑道""才缓缓说道"）
_NAME_BAD_CHARS = set("说道问答喊笑骂吼叫嚷缓慢轻低沉喃才")


def _valid_name(name: str) -> bool:
    """过滤把"说/道/笑"等引导语误当成人名的抽取结果。"""
    return bool(name) and name not in _MODIFIERS and not any(
        char in _NAME_BAD_CHARS for char in name
    )


def _detect_speaker(paragraph: str, match: re.Match) -> str:
    before = paragraph[max(0, match.start() - 18): match.start()]
    for found in _PRE_SPEAKER.finditer(before):
        name = found.group(1)
        if _valid_name(name):
            return name
    after = paragraph[match.end(): match.end() + 20]
    found = _POST_SPEAKER.match(after)
    if found and _valid_name(found.group(1)):
        return found.group(1)
    # 兜底：对白所在小句里唯一的人称代词即说话人（避免跨句带入其他角色）
    clause = re.split(r"[。！？!?\n；;]", paragraph[:match.start()])[-1][-24:]
    for window in (clause, after):
        pronouns = set(_PRONOUN_PATTERN.findall(window))
        if len(pronouns) == 1:
            return pronouns.pop()
    return ""


def _is_attribution_only(text: str) -> bool:
    """判断整段是否只是"某某说/道"这类引导语（需要整段丢弃，避免重复朗读）。"""
    text = text.strip()
    if not text or len(text) > 8 or not _ONLY_ATTRIBUTION.match(text):
        return False
    prefix = re.sub(rf"(?:{_ATTR_WORDS})[：:，,。！？!?…]*$", "", text)
    return not any(char in _ATTRIB_SKIP_CHARS for char in prefix)


class _Builder:
    def __init__(self, default_rate: float):
        self.default_rate = default_rate
        self.segments: list[Segment] = []

    @property
    def last_text(self) -> str:
        return self.segments[-1].text if self.segments else ""

    def add(self, speaker: str, text: str, kind: str, extra_pause: int = 0,
            hint: str = "") -> None:
        text = text.strip()
        if not text:
            return
        pause = _pause_ms(self.last_text) + extra_pause
        mood_text = f"{hint}{text}"
        self.segments.append(
            Segment(
                index=len(self.segments),
                speaker=speaker,
                text=text,
                kind=kind,
                pause_before_ms=pause,
                rate=_rate_for(mood_text, self.default_rate),
                emotion_hint=_emotion_for(mood_text),
            )
        )

    def add_narration(self, text: str) -> None:
        text = text.strip()
        if not text or _is_attribution_only(text):
            return
        # 去掉句尾的"某某说/低声道："等引导语，让旁白读起来像自然叙述
        text = _TRAILING_ATTRIBUTION.sub("", text).strip()
        if not text:
            return
        for sentence in _SENTENCE_SPLIT.split(text):
            if _WORD_CHAR.search(sentence):
                self.add("旁白", sentence, "narration")

    def add_dialogue(self, speaker: str, text: str, hint: str = "") -> None:
        self.add(speaker or "旁白", text, "dialogue", extra_pause=150, hint=hint)


def parse(text: str, default_rate: float = 1.0) -> list[Segment]:
    """把正文解析为有序片段；纯对白与纯旁白都能处理。"""
    builder = _Builder(default_rate)
    for paragraph in _paragraphs(text):
        cursor = 0
        for match in _QUOTE_PATTERN.finditer(paragraph):
            builder.add_narration(paragraph[cursor: match.start()])
            speaker = _detect_speaker(paragraph, match)
            quote = (match.group(1) or match.group(2) or "").strip()
            hint = paragraph[max(0, match.start() - 12): match.start()]
            builder.add_dialogue(speaker, quote, hint=hint)
            cursor = match.end()
        builder.add_narration(paragraph[cursor:])

    for new_index, segment in enumerate(builder.segments):
        segment.index = new_index
    return builder.segments
