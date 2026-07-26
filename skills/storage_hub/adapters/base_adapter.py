from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseDriveAdapter(ABC):
    def __init__(self, drive_id: str):
        self.drive_id = drive_id

    @abstractmethod
    def login_auth(self) -> bool:
        """处理 OAuth2 认证或 Token 刷新"""
        pass

    @abstractmethod
    def list_files(self, remote_path: str = "/") -> List[Dict[str, Any]]:
        """
        统一返回格式:
        [{'name': '1.mp4', 'size': 1024, 'is_dir': False, 'id': '...', 'path': '...'}]
        """
        pass

    @abstractmethod
    def get_download_link(self, file_id: str) -> str:
        """获取直链或临时下载地址"""
        pass

    @abstractmethod
    def get_quota(self) -> Dict[str, int]:
        """获取空间配额: {'total': 1024, 'used': 512}"""
        pass

    @abstractmethod
    def get_upload_params(self, remote_path: str) -> Dict[str, Any]:
        """获取上传参数: {'url': '...', 'method': 'PUT', 'headers': {...}}"""
        pass

    def delete_file(self, remote_path: str) -> bool:
        """删除文件或目录"""
        raise NotImplementedError

    def rename_file(self, remote_path: str, new_name: str) -> bool:
        """重命名文件或目录"""
        raise NotImplementedError

    def copy_file(self, src_path: str, dst_path: str) -> bool:
        """同盘复制文件/目录"""
        raise NotImplementedError

    def move_file(self, src_path: str, dst_path: str) -> bool:
        """同盘移动文件/目录"""
        raise NotImplementedError

    def create_directory(self, remote_path: str) -> bool:
        """创建目录"""
        raise NotImplementedError
