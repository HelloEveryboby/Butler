import os
import shutil
from typing import List, Tuple
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class FileSystemGuard:
    """
    Protects core system files and directories from accidental deletion.
    """
    PROTECTED_PATHS = [
        "butler",
        "package",
        "config",
        "assets/sounds",
        "requirements.txt",
        ".env"
    ]

    @classmethod
    def is_protected(cls, path: str) -> bool:
        """
        Check if a given path is protected.
        """
        abs_path = os.path.abspath(path)
        root_dir = os.path.abspath(os.getcwd())

        for protected in cls.PROTECTED_PATHS:
            protected_abs = os.path.abspath(os.path.join(root_dir, protected))
            if abs_path == protected_abs or abs_path.startswith(protected_abs + os.sep):
                return True
        return False

    def safe_delete(self, path: str) -> Tuple[bool, str]:
        """
        Attempts to delete a file or directory only if it's not protected.
        """
        if self.is_protected(path):
            logger.warning(f"Deletion blocked for protected path: {path}")
            return False, f"错误: 路径 '{path}' 受系统保护，禁止删除。"

        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            logger.info(f"Successfully deleted: {path}")
            return True, f"已成功删除 '{path}'。"
        except Exception as e:
            logger.error(f"Error deleting {path}: {e}")
            return False, f"删除失败: {e}"


if __name__ == "__main__":
    guard = FileSystemGuard()
    print(f"Is 'butler/app.py' protected? {guard.is_protected('butler/app.py')}")
    print(f"Is 'temp.txt' protected? {guard.is_protected('temp.txt')}")
