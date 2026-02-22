"""
网盘管理工具 - 利用 bypy API 实现百度网盘的上传、下载、列表查看等功能。
支持语音和文字指令触发。
"""
import os
import sys
import io
import contextlib
from bypy import ByPy
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class CloudStorageManager:
    def __init__(self):
        # 禁用 bypy 的自动交互，防止在后台线程阻塞
        self.bp = ByPy(quit_on_error=False)

    def _capture_output(self, func, *args, **kwargs):
        """捕获函数的标准输出并返回字符串"""
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            try:
                func(*args, **kwargs)
            except Exception as e:
                return f"发生错误: {str(e)}\n" + f.getvalue()
        return f.getvalue()

    def list_files(self, remote_path='/'):
        """列出网盘文件"""
        logger.info(f"正在列出网盘目录: {remote_path}")
        output = self._capture_output(self.bp.list, remote_path)
        return output if output.strip() else "目录为空或读取失败。"

    def upload(self, local_path, remote_path='/'):
        """上传文件到网盘"""
        if not os.path.exists(local_path):
            return f"错误：本地文件 {local_path} 不存在。"

        logger.info(f"正在上传 {local_path} 到网盘 {remote_path}")
        # upload 通常不会产生大量 stdout，但也捕获一下以防万一
        output = self._capture_output(self.bp.upload, local_path, remote_path)
        return output if output.strip() else "上传任务已处理。"

    def download(self, remote_path, local_path='.'):
        """从网盘下载文件"""
        logger.info(f"正在从网盘下载 {remote_path} 到 {local_path}")
        output = self._capture_output(self.bp.download, remote_path, local_path)
        return output if output.strip() else "下载任务已处理。"

    def get_quota(self):
        """查看网盘容量信息"""
        logger.info("正在查询网盘容量信息")
        output = self._capture_output(self.bp.info)
        return output if output.strip() else "无法获取空间信息。"

def run(*args, **kwargs):
    """
    Butler ExtensionManager 的入口点。
    """
    # 检查 bypy 是否已经授权
    # bypy 默认存储授权信息在 ~/.bypy 目录下
    auth_file = os.path.expanduser('~/.bypy/bypy.json')
    if not os.path.exists(auth_file):
        return ("检测到网盘尚未授权。请在终端执行 'bypy info' 并按照提示完成授权，"
                "然后再通过语音或文字使用此功能。")

    manager = CloudStorageManager()

    operation = kwargs.get('operation')
    if not operation and args:
        operation = args[0]

    if not operation:
        return "请指定操作：list, upload, download, info"

    operation = operation.lower()

    try:
        if operation == 'list':
            path = kwargs.get('path', kwargs.get('remote_path', '/'))
            if not path and len(args) > 1: path = args[1]
            return manager.list_files(path)

        elif operation == 'upload':
            local_path = kwargs.get('local_path')
            remote_path = kwargs.get('remote_path', '/')
            if not local_path and len(args) > 1: local_path = args[1]
            if len(args) > 2: remote_path = args[2]

            if not local_path:
                return "上传操作需要指定本地文件路径 (local_path)。"
            return manager.upload(local_path, remote_path)

        elif operation == 'download':
            remote_path = kwargs.get('remote_path')
            local_path = kwargs.get('local_path', '.')
            if not remote_path and len(args) > 1: remote_path = args[1]
            if len(args) > 2: local_path = args[2]

            if not remote_path:
                return "下载操作需要指定网盘文件路径 (remote_path)。"
            return manager.download(remote_path, local_path)

        elif operation == 'info':
            return manager.get_quota()

        else:
            return f"不支持的操作: {operation}。支持的操作有: list, upload, download, info。"

    except Exception as e:
        logger.error(f"网盘操作出错: {e}")
        return f"网盘操作时发生错误: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        op = sys.argv[1]
        print(run(operation=op, args=sys.argv[2:]))
    else:
        print("用法: python cloud_storage_manager.py <operation> [args...]")
