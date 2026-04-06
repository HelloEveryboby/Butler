import os
import logging
from .markitdown_app import convert

# 获取日志记录器
logger = logging.getLogger("MarkItDownSkill")

def handle_request(action, **kwargs):
    """
    处理 MarkItDown 技能的请求。
    支持的操作:
        - convert: 将文件转换为 Markdown 格式。

    参数:
        action (str): 执行的动作名称。
        **kwargs: 包含参数的字典，通常包含 entities 或直接的 file_path。
    """
    if action == "convert":
        # 从多种可能的参数位置获取文件路径
        entities = kwargs.get("entities", {})
        file_path = entities.get("file_path") or entities.get("path") or kwargs.get("file_path")

        if not file_path:
            return "请提供要转换的文件路径。"

        if not os.path.exists(file_path):
            return f"错误：未找到文件 '{file_path}'"

        try:
            logger.info(f"正在将文件转换为 Markdown: {file_path}")
            # 调用核心转换逻辑
            markdown_content = convert(file_path)
            return markdown_content
        except Exception as e:
            logger.error(f"转换过程中发生错误: {e}")
            return f"转换失败: {str(e)}"

    return f"错误：MarkItDown 技能不支持动作 '{action}'。"
