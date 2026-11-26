"""朗读 token 预算说明 — 回答"朗读要消耗多少 token"。"""

from __future__ import annotations

import re
from pathlib import Path

_CJK = re.compile(r"[\u4e00-\u9fff]")


def explain(path: str | Path) -> dict:
    """统计字数并估算各环节的 token 消耗。"""
    file_path = Path(path).expanduser().resolve()
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    return explain_text(text, str(file_path))


def explain_text(text: str, name: str = "文本") -> dict:
    """对任意文本做 token 预算说明。"""
    chars = len(text)
    cjk = len(_CJK.findall(text))
    estimated = int(cjk * 0.7 + (chars - cjk) / 4)
    return {
        "path": name,
        "chars": chars,
        "cjk_chars": cjk,
        "tts_tokens": 0,
        "local_analysis_tokens": 0,
        "ai_analysis_estimated_tokens": estimated,
        "note": (
            "edge-tts 与系统原生语音均不消耗 LLM token；"
            "对白/停顿/语速解析为本地规则，同样为 0 token。"
            "仅当使用 --ai 让大模型推断角色性别时，才按文本长度消耗输入 token。"
        ),
    }


def format_explain(info: dict) -> str:
    return "\n".join(
        [
            f"文件: {info['path']}",
            f"字符数: {info['chars']}（其中中文 {info['cjk_chars']}）",
            f"TTS 合成: {info['tts_tokens']} token（edge-tts 免费额度，不计 LLM token）",
            f"本地解析: {info['local_analysis_tokens']} token",
            f"--ai 角色分析（可选）: 约 {info['ai_analysis_estimated_tokens']} 输入 token",
            info["note"],
        ]
    )
