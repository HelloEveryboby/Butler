import sys
import os

# Use consistent project root resolution
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
markitdown_src = os.path.join(project_root, 'markitdown', 'src')
if markitdown_src not in sys.path:
    sys.path.insert(0, markitdown_src)

from markitdown.markitdown_app import convert

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
