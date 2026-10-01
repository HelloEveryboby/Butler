"""翻译技能脚本 — 对接 Butler 统一翻译系统。

支持中英文互译；若指定 --to 则翻译到目标语言。
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Butler 翻译技能")
    parser.add_argument("--text", type=str, required=True, help="待翻译文本")
    parser.add_argument("--to", type=str, default=None, help="目标语言代码（如 zh-CN / en / ja）")
    args = parser.parse_args()

    # 延迟导入，避免技能加载时的副作用
    try:
        from package.document.translate_system import get_default_system
        from package.document.translate_system.languages import detect_language
    except ImportError:
        # 回退到绝对路径导入（从仓库根运行时）
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from package.document.translate_system import get_default_system
        from package.document.translate_system.languages import detect_language

    system = get_default_system()

    target = args.to
    if target is None:
        # 自动判断：中文 -> 英文，其它 -> 中文
        target = "en" if detect_language(args.text) == "zh-CN" else "zh-CN"

    try:
        result = system.translate(args.text, to=target)
        print(result)
    except Exception as e:
        print(f"翻译失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
