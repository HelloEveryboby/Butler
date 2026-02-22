import sys
import os

# HACK: 这是针对环境可编辑安装问题的临时解决方法。
# 它确保在 butler 应用程序导入此模块时可以找到 'markitdown' 包。
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'markitdown', 'src')))

from markitdown.main import convert

def convert_to_markdown(file_path: str):
    """
    将文件转换为 Markdown 并打印内容。
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return

    try:
        markdown_content = convert(file_path)
        print(markdown_content)
    except Exception as e:
        print(f"转换过程中发生错误: {e}")
