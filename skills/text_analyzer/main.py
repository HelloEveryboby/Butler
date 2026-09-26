"""Butler Text Analyzer Skill - Text statistics, readability, keywords."""
import re
from collections import Counter
from typing import Any, Dict, List

# 中文停用词（精简版）
_STOPWORDS_ZH = set(
    "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 "
    "那 他 她 它 们 这个 那个 什么 怎么 为什么 可以 没 把 被 让 从 对 向 跟 比 还 但 而 因为 所以 "
    "如果 虽然 但是 不过 然后 以及 或者 并且 虽然 由于 关于 对于 通过 其中 这些 那些 一些 一样 "
    "这样 那样 怎么 怎样 这么 那么 哪个 哪些 哪里 这儿 那儿 时候 时间 地方 东西 事情 问题 "
    "知道 觉得 认为 看见 听见 现在 以前 以后 已经 正在 将要 曾经 一直 总是 从来 还是 或者 "
    "只是 只有 就是 不是 不能 不会 不要 不用 不是 没有 每 各 该 此 其 之 与 及 或 亦 则 乃 "
    "若 如 因 为 所 以 于 由 自 至 从 向 往 跟 同 和 与 及 等 等等 之类 什么 怎么 怎样 哪".split()
)

# 英文停用词
_STOPWORDS_EN = set(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might can shall i you he she it we they them us our your "
    "his her its their my me him this that these those of in on at to for with "
    "by from as into about against between through during before after above below "
    "up down out off over under again further then once here there when where why "
    "how all any both each few more most other some such no nor not only own same "
    "so than too very just because but and or if while although though since until "
    "also however therefore thus hence already still yet ever never always often "
    "sometimes usually really quite rather almost nearly".split()
)


def _split_sentences(text: str) -> List[str]:
    """中英文分句。"""
    # 按中英文标点分句
    parts = re.split(r"[。！？!?\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _tokenize(text: str) -> List[str]:
    """简单分词：英文按空格和标点，中文按单字。"""
    # 提取英文单词
    en_words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", text.lower())
    # 提取中文字符（按连续中文块切，再按单字）
    zh_blocks = re.findall(r"[\u4e00-\u9fff]+", text)
    zh_chars = []
    for block in zh_blocks:
        # 简单 2-gram 切分
        for i in range(len(block) - 1):
            zh_chars.append(block[i:i + 2])
        if len(block) == 1:
            zh_chars.append(block)
    return en_words + zh_chars


def analyze(text: str) -> str:
    """全面文本统计。"""
    if not text:
        return "错误：文本为空。"

    char_count = len(text)
    char_no_space = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))

    en_words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", text)
    zh_chars = re.findall(r"[\u4e00-\u9fff]", text)
    digits = re.findall(r"\d", text)

    sentences = _split_sentences(text)
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]

    total_words = len(en_words) + len(zh_chars)
    avg_sentence_len = total_words / len(sentences) if sentences else 0
    avg_word_len = sum(len(w) for w in en_words) / len(en_words) if en_words else 0

    # 词频
    tokens = _tokenize(text)
    filtered = [
        t for t in tokens
        if t not in _STOPWORDS_EN and t not in _STOPWORDS_ZH and len(t) > 1
    ]
    word_freq = Counter(filtered).most_common(10)

    lines = [
        "### 📝 文本分析报告",
        "",
        "**基本统计**",
        f"- 字符数：{char_count}",
        f"- 不含空白字符数：{char_no_space}",
        f"- 英文单词数：{len(en_words)}",
        f"- 中文字符数：{len(zh_chars)}",
        f"- 数字字符数：{len(digits)}",
        f"- 句子数：{len(sentences)}",
        f"- 段落数：{len(paragraphs)}",
        "",
        "**平均指标**",
        f"- 平均句长：{avg_sentence_len:.1f} 词/字",
        f"- 平均英文词长：{avg_word_len:.1f} 字符",
        "",
        "**高频词 Top 10**",
    ]
    if word_freq:
        for word, count in word_freq:
            lines.append(f"  - {word}: {count}")
    else:
        lines.append("  （无）")

    return "\n".join(lines)


def readability(text: str) -> str:
    """可读性评估。"""
    if not text:
        return "错误：文本为空。"

    en_words = re.findall(r"[a-zA-Z]+", text)
    sentences = _split_sentences(text)
    syllables = sum(_count_syllables(w) for w in en_words)

    result_lines = ["### 📖 可读性评估\n"]

    if en_words:
        # Flesch Reading Ease
        words = len(en_words)
        sents = len(sentences) if sentences else 1
        syls = max(syllables, 1)
        fre = 206.835 - 1.015 * (words / sents) - 84.6 * (syls / words)
        fre = max(0, min(100, fre))

        if fre >= 90:
            level = "非常容易 (5年级)"
        elif fre >= 80:
            level = "容易 (6年级)"
        elif fre >= 70:
            level = "较容易 (7年级)"
        elif fre >= 60:
            level = "标准 (8-9年级)"
        elif fre >= 50:
            level = "较难 (10-12年级)"
        elif fre >= 30:
            level = "困难 (大学)"
        else:
            level = "非常困难 (专家)"

        result_lines.append(f"**英文 Flesch Reading Ease**: {fre:.1f} / 100")
        result_lines.append(f"**难度等级**: {level}")
        result_lines.append(f"- 单词数: {words}")
        result_lines.append(f"- 句子数: {sents}")
        result_lines.append(f"- 音节数: {syls}")
        result_lines.append(f"- 平均句长: {words/sents:.1f} 词")
        result_lines.append(f"- 平均音节: {syls/words:.1f}/词\n")

    zh_chars = re.findall(r"[\u4e00-\u9fff]", text)
    if zh_chars:
        # 中文简化评估：基于平均句长
        zh_sentences = [s for s in sentences if re.search(r"[\u4e00-\u9fff]", s)]
        if zh_sentences:
            avg_zh_len = len(zh_chars) / len(zh_sentences)
            if avg_zh_len <= 15:
                zh_level = "非常易读"
            elif avg_zh_len <= 25:
                zh_level = "易读"
            elif avg_zh_len <= 40:
                zh_level = "中等"
            elif avg_zh_len <= 60:
                zh_level = "较难"
            else:
                zh_level = "困难"
            result_lines.append(f"**中文可读性**: {zh_level}")
            result_lines.append(f"- 中文字符数: {len(zh_chars)}")
            result_lines.append(f"- 中文句子数: {len(zh_sentences)}")
            result_lines.append(f"- 平均中文句长: {avg_zh_len:.1f} 字")

    if not en_words and not zh_chars:
        result_lines.append("未检测到中英文文本。")

    return "\n".join(result_lines)


def _count_syllables(word: str) -> int:
    """估算英文单词音节数。"""
    word = word.lower()
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0
    count = 0
    vowels = "aeiouy"
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def keywords(text: str, top_n: int = 10) -> str:
    """提取关键词。"""
    if not text:
        return "错误：文本为空。"

    tokens = _tokenize(text)
    filtered = [
        t for t in tokens
        if t not in _STOPWORDS_EN and t not in _STOPWORDS_ZH and len(t) > 1
    ]

    if not filtered:
        return "未提取到有效关键词。"

    # 词频 + 位置权重
    freq = Counter(filtered)
    total = len(filtered)
    scored = []
    for word, count in freq.items():
        tf = count / total
        # 首次出现位置权重（越早出现权重越高）
        first_pos = filtered.index(word) / total if total > 0 else 1
        score = tf * (1 - first_pos * 0.3)
        scored.append((word, count, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    top = scored[:top_n]

    lines = [f"### 🔑 关键词 Top {len(top)}\n"]
    for word, count, score in top:
        lines.append(f"- **{word}** (出现 {count} 次, 权重 {score:.3f})")
    return "\n".join(lines)


def wordfreq(text: str, top_n: int = 15) -> str:
    """词频统计。"""
    if not text:
        return "错误：文本为空。"

    tokens = _tokenize(text)
    filtered = [
        t for t in tokens
        if t not in _STOPWORDS_EN and t not in _STOPWORDS_ZH and len(t) > 1
    ]

    freq = Counter(filtered).most_common(top_n)
    if not freq:
        return "无有效词汇。"

    max_count = freq[0][1]
    lines = [f"### 📊 词频统计 Top {len(freq)}\n"]
    for word, count in freq:
        bar_len = int(count / max_count * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"- {word:<8} {bar} {count}")
    return "\n".join(lines)


def handle_request(action: str, **kwargs) -> Any:
    """Butler 技能入口。"""
    text = kwargs.get("text") or kwargs.get("input") or kwargs.get("content", "")

    if not text and action not in ("help", ""):
        return "错误：请提供 text 参数。"

    if action in ("analyze", "stats", "run"):
        return analyze(text)

    if action in ("readability", "reading", "read"):
        return readability(text)

    if action in ("keywords", "keyword"):
        n = int(kwargs.get("top", kwargs.get("n", 10)))
        return keywords(text, n)

    if action in ("wordfreq", "freq", "frequency"):
        n = int(kwargs.get("top", kwargs.get("n", 15)))
        return wordfreq(text, n)

    if action == "help" or not action:
        return (
            "### 📝 Butler 文本分析器\n\n"
            "**全面统计** (action: `analyze`): text\n"
            "**可读性评估** (action: `readability`): text\n"
            "**关键词提取** (action: `keywords`): text, top (默认 10)\n"
            "**词频统计** (action: `wordfreq`): text, top (默认 15)"
        )

    return f"未知动作: {action}"
