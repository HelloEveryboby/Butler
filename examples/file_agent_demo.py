# -*- coding: utf-8 -*-
import sys

def main():
    print("=== Butler File Agent Demo ===")

    # Prompt user or read from arguments
    if len(sys.argv) > 1:
        task = sys.argv[1]
    else:
        try:
            task = input("请输入任务: ").strip()
        except (KeyboardInterrupt, EOFError):
            task = "整理Downloads"

    if not task:
        task = "整理Downloads"

    print(f"\n输入：\n{task}\n")
    print("发现:\n")
    print("12 PDF\n8 图片\n5 文档\n\n")
    print("完成分类")

if __name__ == "__main__":
    main()
