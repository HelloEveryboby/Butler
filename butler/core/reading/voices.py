"""音色分配 — 把出场角色稳定映射到不同的男/女音色。

不需要每行都读"某某说"：同一角色始终使用同一音色，
不同角色默认拿到不同音色，靠声音区分说话人。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("ReadingVoices")

DEFAULT_FEMALE = ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-XiaohanNeural"]
DEFAULT_MALE = ["zh-CN-YunxiNeural", "zh-CN-YunyangNeural", "zh-CN-YunjianNeural"]
DEFAULT_NARRATOR = "zh-CN-XiaoxiaoNeural"

_FEMALE_HINTS = (
    "妈妈", "母亲", "姐姐", "妹妹", "阿姨", "姑娘", "女孩", "女人",
    "夫人", "太太", "小姐", "祖母", "奶奶", "外婆", "少女",
)
_MALE_HINTS = (
    "爸爸", "父亲", "哥哥", "弟弟", "叔叔", "男孩", "男人",
    "先生", "少年", "老头", "老爷子", "祖父", "爷爷", "外公",
)


def guess_gender(name: str) -> str | None:
    """依据称谓推断角色性别；无法判断返回 None。"""
    for word in _FEMALE_HINTS:
        if word in name:
            return "female"
    for word in _MALE_HINTS:
        if word in name:
            return "male"
    if name.endswith("女"):
        return "female"
    if name.endswith("男"):
        return "male"
    return None


def assign_voices(
    characters: list[str],
    female_voices: list[str] | None = None,
    male_voices: list[str] | None = None,
    narrator: str = "旁白",
    role_map: dict[str, str] | None = None,
    gender_map: dict[str, str] | None = None,
) -> dict[str, str]:
    """给每个角色分配音色。role_map（人工指定音色）优先级最高。"""
    female = list(female_voices or DEFAULT_FEMALE)
    male = list(male_voices or DEFAULT_MALE)
    mapping: dict[str, str] = {narrator: female[0] if female else DEFAULT_NARRATOR}

    fi = 1 if len(female) > 1 else 0
    mi = 0
    for name in characters:
        if not name or name in mapping:
            continue
        gender = (gender_map or {}).get(name) or guess_gender(name)
        if gender == "female" and female:
            mapping[name] = female[fi % len(female)]
            fi += 1
        elif gender == "male" and male:
            mapping[name] = male[mi % len(male)]
            mi += 1
        elif len(mapping) % 2 == 0 and female:
            mapping[name] = female[fi % len(female)]
            fi += 1
        elif male:
            mapping[name] = male[mi % len(male)]
            mi += 1

    if role_map:
        mapping.update({k: v for k, v in role_map.items() if v})
    return mapping


def load_role_map(path: str | Path | None) -> dict[str, str]:
    """读取人工音色映射文件：{"角色名": "zh-CN-YunxiNeural"}。"""
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取音色映射失败: %s", exc)
    return {}
