"""
Butler 开发效率工具集
-------------------
基于 C 语言混合编程模块提供的极速底层接口，封装的高层开发工具。
"""

import os
from typing import List, Dict, Any, Optional
from butler.core.hybrid_link import HybridLinkClient
from butler.core.extension_manager import extension_manager

class DevTools:
    def __init__(self):
        self._client = None
        self._sysutil_path = None

    def _ensure_client(self):
        if self._client:
            return self._client

        info = extension_manager.code_execution_manager.get_program("hybrid_sysutil")
        if not info:
            # 尝试重新扫描
            extension_manager.code_execution_manager.scan_and_register()
            info = extension_manager.code_execution_manager.get_program("hybrid_sysutil")

        if not info:
            raise RuntimeError("混合编程模块 'hybrid_sysutil' 未找到，请确保已编译二进制文件。")

        self._sysutil_path = info['path']
        self._client = HybridLinkClient(self._sysutil_path, cwd=os.path.dirname(self._sysutil_path))
        self._client.open()
        return self._client

    def grep(self, pattern: str, root: str = ".", case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        跨文件搜索关键词
        """
        client = self._ensure_client()
        res = client.call("grep_search", {"root": root, "pattern": pattern, "case_sensitive": 1 if case_sensitive else 0})
        return res.get("matches", [])

    def glob(self, pattern: str) -> List[str]:
        """
        按模式匹配文件路径
        """
        client = self._ensure_client()
        res = client.call("glob_list", {"pattern": pattern})
        return res.get("files", [])

    def safe_edit(self, path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """
        安全地搜索并替换文件中的文本块（原子操作）
        """
        client = self._ensure_client()
        return client.call("patch_edit", {"path": path, "old_text": old_text, "new_text": new_text})

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

# 单例实例
dev_tools = DevTools()

def run(*args, **kwargs):
    """
    独立运行测试函数
    """
    print("正在测试 Butler 开发效率工具集...")
    try:
        matches = dev_tools.grep("Butler", root=".")
        print(f"找到 {len(matches)} 处匹配 'Butler'")

        py_files = dev_tools.glob("**/*.py")
        print(f"找到 {len(py_files)} 个 Python 文件")

        return f"测试完成。匹配数: {len(matches)}, 文件数: {len(py_files)}"
    except Exception as e:
        return f"测试失败: {e}"
    finally:
        dev_tools.close()

if __name__ == "__main__":
    print(run())
