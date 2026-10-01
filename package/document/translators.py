"""翻译模块 — 已升级为统一翻译系统的兼容门面。

所有实际逻辑迁移至 package.document.translate_system。
本文件保留原有函数签名，确保 TUI / CLI / 既有调用方无需改动。
"""

from __future__ import annotations

from typing import Optional

from package.document.translate_system import (
    TranslationSystem,
    get_default_system,
    translate_bilingual as _translate_bilingual,
    translate_file as _translate_file,
    translate_text as _translate_text,
    translate_website as _translate_website,
)
from package.document.translate_system.languages import detect_language

__all__ = [
    "TranslationSystem",
    "detect_language",
    "translate_text",
    "translate_bilingual",
    "translate_file",
    "translate_website",
    "translate_website_bilingual",
    "translators",
]


def translate_text(text: str, to: Optional[str] = None) -> str:
    return _translate_text(text, to=to)


def translate_bilingual(text: str, context: Optional[str] = None,
                        to: Optional[str] = None):
    return _translate_bilingual(text, context=context, to=to)


def translate_file(input_file: str, output_file: Optional[str] = None,
                   to: Optional[str] = None) -> str:
    return _translate_file(input_file, output_file, to=to)


def translate_website(url: str, to: Optional[str] = None) -> dict:
    return _translate_website(url, to=to)


# 旧名兼容
def translate_website_bilingual(url: str, to: Optional[str] = None) -> dict:
    return _translate_website(url, to=to)


def translators() -> None:
    """交互式翻译入口（保留旧 CLI）。"""
    print("Butler 翻译系统")
    print("已启用 Provider:")
    system = get_default_system()
    for p in system.config.providers:
        flag = "✓" if p.id in system.config.fallback_chain else " "
        print(f"  [{flag}] {p.name} ({p.type})")
    print(f"目标语言: {system.config.target_lang}")
    print(f"缓存条目: {system.cache.size} | 术语: {system.glossary.size} | 历史: {system.history.size}")
    print()

    choice = input("请选择翻译类型: 1. 文本  2. 文件  3. 网页  4. 查看术语表  5. 查看历史\n")
    if choice == "1":
        text = input("请输入要翻译的文本:\n")
        if text.strip():
            print("翻译结果:", translate_text(text))
    elif choice == "2":
        file_path = input("请输入文件路径:\n")
        output = translate_file(file_path)
        print(f"文件翻译成功，已保存到 {output}")
    elif choice == "3":
        url = input("请输入网页 URL:\n")
        import json
        print(json.dumps(translate_website(url), ensure_ascii=False, indent=2))
    elif choice == "4":
        for src, tgt in system.glossary.all().items():
            print(f"  {src} → {tgt}")
    elif choice == "5":
        for e in system.get_history(limit=20):
            print(f"  [{e.provider}] {e.original[:40]} => {e.translated[:40]}")
    else:
        print("无效选择")


if __name__ == "__main__":
    translators()
