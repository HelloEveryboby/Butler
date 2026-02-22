import os
import shutil
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class FileManager:
    def create_file(self, file_path, content=""):
        """
        Creates a new file at the specified path.
        If content is provided, writes it to the file.
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Successfully created file: {file_path}")
            return True, f"文件 '{file_path}' 已成功创建。"
        except Exception as e:
            logger.error(f"Error creating file {file_path}: {e}")
            return False, f"创建文件 '{file_path}' 时出错: {e}"

    def write_to_file(self, file_path, content):
        """
        Writes or overwrites content to a specified file.
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Successfully wrote to file: {file_path}")
            return True, f"内容已成功写入 '{file_path}'。"
        except Exception as e:
            logger.error(f"Error writing to file {file_path}: {e}")
            return False, f"写入文件 '{file_path}' 时出错: {e}"

    def read_file(self, file_path):
        """
        Reads the content of a specified file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Successfully read file: {file_path}")
            return True, content
        except FileNotFoundError:
            logger.warning(f"File not found: {file_path}")
            return False, f"文件 '{file_path}' 未找到。"
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return False, f"读取文件 '{file_path}' 时出错: {e}"

    def delete_file(self, file_path):
        """
        Deletes a specified file.
        """
        try:
            os.remove(file_path)
            logger.info(f"Successfully deleted file: {file_path}")
            return True, f"文件 '{file_path}' 已成功删除。"
        except FileNotFoundError:
            logger.warning(f"Attempted to delete non-existent file: {file_path}")
            return False, f"文件 '{file_path}' 未找到，无法删除。"
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False, f"删除文件 '{file_path}' 时出错: {e}"

    def list_directory(self, dir_path):
        """
        Lists all files and directories in a given path.
        """
        try:
            items = os.listdir(dir_path)
            logger.info(f"Successfully listed directory: {dir_path}")
            return True, items
        except FileNotFoundError:
            logger.warning(f"Directory not found for listing: {dir_path}")
            return False, f"目录 '{dir_path}' 未找到。"
        except Exception as e:
            logger.error(f"Error listing directory {dir_path}: {e}")
            return False, f"列出目录 '{dir_path}' 内容时出错: {e}"

def run():
    """
    Placeholder run function to make the module executable by the system.
    This could be enhanced to provide a command-line interface for file management.
    """
    print("File Manager module loaded. This module is intended to be used programmatically.")
    logger.info("File Manager module run function executed.")
