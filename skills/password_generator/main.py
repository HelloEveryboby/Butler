"""Butler Password Generator Skill - Cryptographically secure password/passphrase/PIN generator."""
import secrets
import string
import re
from typing import Any, Dict, List

# 易记口令词库（精选常用英文单词，避免歧义和敏感词）
_WORDLIST: List[str] = [
    "apple", "ocean", "river", "mountain", "forest", "cloud", "storm", "light",
    "shadow", "stone", "flower", "garden", "window", "bridge", "harbor", "meadow",
    "canyon", "island", "desert", "jungle", "valley", "glacier", "meadow", "summit",
    "crystal", "amber", "jasper", "marble", "obsidian", "quartz", "sapphire", "emerald",
    "falcon", "dolphin", "phoenix", "tiger", "eagle", "panda", "koala", "otter",
    "willow", "cedar", "maple", "bamboo", "cypress", "oak", "pine", "birch",
    "nova", "comet", "meteor", "nebula", "galaxy", "planet", "aurora", "zenith",
    "ember", "frost", "dew", "breeze", "gale", "thunder", "rain", "snow",
    "canvas", "melody", "rhythm", "sonnet", "ballad", "harbor", "lantern", "beacon",
    "cobalt", "crimson", "azure", "violet", "scarlet", "indigo", "magenta", "jade",
]

_CHAR_LOWER = string.ascii_lowercase
_CHAR_UPPER = string.ascii_uppercase
_CHAR_DIGITS = string.digits
_CHAR_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?"


def generate_password(length: int = 16,
                      use_upper: bool = True,
                      use_lower: bool = True,
                      use_digits: bool = True,
                      use_symbols: bool = True) -> str:
    """生成密码学安全的随机密码。"""
    length = max(4, min(int(length), 128))

    charset = ""
    if use_lower:
        charset += _CHAR_LOWER
    if use_upper:
        charset += _CHAR_UPPER
    if use_digits:
        charset += _CHAR_DIGITS
    if use_symbols:
        charset += _CHAR_SYMBOLS

    if not charset:
        return "错误：至少需要启用一种字符集。"

    # 确保每种启用的字符集至少出现一次
    required = []
    if use_upper:
        required.append(secrets.choice(_CHAR_UPPER))
    if use_lower:
        required.append(secrets.choice(_CHAR_LOWER))
    if use_digits:
        required.append(secrets.choice(_CHAR_DIGITS))
    if use_symbols:
        required.append(secrets.choice(_CHAR_SYMBOLS))

    remaining = length - len(required)
    chars = [secrets.choice(charset) for _ in range(remaining)]
    all_chars = required + chars

    # 安全打乱
    for i in range(len(all_chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        all_chars[i], all_chars[j] = all_chars[j], all_chars[i]

    return "".join(all_chars)


def generate_passphrase(word_count: int = 5, separator: str = "-",
                        include_number: bool = True) -> str:
    """生成易记的口令短语。"""
    word_count = max(3, min(int(word_count), 12))
    words = [secrets.choice(_WORDLIST) for _ in range(word_count)]

    if include_number:
        idx = secrets.randbelow(word_count)
        words[idx] = f"{words[idx]}{secrets.randbelow(100)}"

    return separator.join(words)


def generate_pin(length: int = 6) -> str:
    """生成数字 PIN 码。"""
    length = max(4, min(int(length), 8))
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def evaluate_strength(password: str) -> Dict[str, Any]:
    """评估密码强度。"""
    if not password:
        return {"score": 0, "level": "极弱", "suggestions": ["密码不能为空。"]}

    length = len(password)
    has_upper = bool(re.search(r"[A-Z]", password))
    has_lower = bool(re.search(r"[a-z]", password))
    has_digit = bool(re.search(r"[0-9]", password))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", password))

    variety = sum([has_upper, has_lower, has_digit, has_symbol])

    # 计算字符空间大小
    pool = 0
    if has_lower:
        pool += 26
    if has_upper:
        pool += 26
    if has_digit:
        pool += 10
    if has_symbol:
        pool += len(_CHAR_SYMBOLS)

    import math
    entropy = length * math.log2(pool) if pool > 0 else 0

    # 常见弱模式检测
    common_patterns = [
        r"(.)\1{2,}",          # 连续重复字符
        r"(012|123|234|345|456|567|678|789|890)",  # 连续数字
        r"(abc|bcd|cde|def|efg|fgh|ghi|hij)",       # 连续字母
    ]
    has_pattern = any(re.search(p, password.lower()) for p in common_patterns)

    score = entropy
    if has_pattern:
        score *= 0.6

    if score < 40:
        level = "弱"
    elif score < 60:
        level = "中"
    elif score < 80:
        level = "强"
    else:
        level = "极强"

    suggestions = []
    if length < 12:
        suggestions.append("建议长度至少 12 位。")
    if variety < 4:
        suggestions.append("建议同时包含大写、小写、数字和符号。")
    if has_pattern:
        suggestions.append("避免使用连续字符（如 123、abc）或重复字符。")
    if not suggestions:
        suggestions.append("密码强度良好。")

    return {
        "length": length,
        "variety": variety,
        "entropy": round(entropy, 1),
        "score": round(score, 1),
        "level": level,
        "suggestions": suggestions,
    }


def handle_request(action: str, **kwargs) -> Any:
    """Butler 技能入口。"""
    if action in ("generate", "password", "run"):
        length = int(kwargs.get("length", 16))
        upper = kwargs.get("upper", kwargs.get("use_upper", True))
        lower = kwargs.get("lower", kwargs.get("use_lower", True))
        digits = kwargs.get("digits", kwargs.get("use_digits", True))
        symbols = kwargs.get("symbols", kwargs.get("use_symbols", True))
        pwd = generate_password(length, upper, lower, digits, symbols)
        return {"password": pwd, "length": len(pwd)}

    if action == "passphrase":
        count = int(kwargs.get("words", kwargs.get("count", 5)))
        sep = kwargs.get("separator", "-")
        num = kwargs.get("number", True)
        phrase = generate_passphrase(count, sep, num)
        return {"passphrase": phrase, "words": count}

    if action == "pin":
        length = int(kwargs.get("length", 6))
        return {"pin": generate_pin(length)}

    if action in ("strength", "evaluate"):
        pwd = kwargs.get("password", kwargs.get("input", ""))
        if not pwd:
            return "错误：请提供 password 参数。"
        result = evaluate_strength(pwd)
        lines = [f"### 🔐 密码强度评估", f"",
                 f"- 长度：{result['length']} 位",
                 f"- 字符种类：{result['variety']}/4",
                 f"- 信息熵：{result['entropy']} bits",
                 f"- 强度等级：**{result['level']}**",
                 f"", f"**建议**："]
        for s in result["suggestions"]:
            lines.append(f"  - {s}")
        return "\n".join(lines)

    if action == "help" or not action:
        return (
            "### 🔐 Butler 安全密码生成器\n\n"
            "**生成密码** (action: `generate`):\n"
            "- length: 长度 (默认 16)\n"
            "- upper/lower/digits/symbols: 字符集开关 (默认全开)\n\n"
            "**生成口令短语** (action: `passphrase`):\n"
            "- words: 单词数 (默认 5)\n"
            "- separator: 分隔符 (默认 '-')\n\n"
            "**生成 PIN** (action: `pin`):\n"
            "- length: 位数 (默认 6)\n\n"
            "**强度评估** (action: `strength`):\n"
            "- password: 待评估的密码"
        )

    return f"未知动作: {action}"
