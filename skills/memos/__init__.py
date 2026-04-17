import os
import sys
import json
import shutil
import base64
from typing import List, Optional, Dict, Any
from butler.core.hybrid_link import HybridLinkClient

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MemosSkill:
    """
    备忘录技能类 (Memos Skill) - 单例模式
    连接 Go 后端并处理多媒体附件。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MemosSkill, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Go 后端路径
        self.executable_path = os.path.join(PROJECT_ROOT, "programs/hybrid_memos/memos_service")
        # 数据库路径
        self.db_path = os.path.join(PROJECT_ROOT, "data/memos/memos.db")
        # 附件存储路径
        self.attachments_dir = os.path.join(PROJECT_ROOT, "data/memos/attachments")

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.attachments_dir, exist_ok=True)

        # 初始化混合链接客户端
        # 注意：如果二进制文件不存在，说明尚未构建
        if not os.path.exists(self.executable_path):
            print(f"警告：备忘录后端未找到，请运行 programs/hybrid_memos/build.sh 进行构建。")
            self.client = None
        else:
            self.client = HybridLinkClient(
                executable_path=self.executable_path,
                fallback_enabled=False
            )
            os.environ["BUTLER_MEMO_DB"] = self.db_path
            self.client.start()

        self._initialized = True

    def add_memo(self, content: str, tags: List[str] = None, files: List[str] = None, base64_files: List[Dict[str, str]] = None):
        """
        添加一条备忘录。
        :param content: 文字内容
        :param tags: 标签列表
        :param files: 本地附件路径列表
        :param base64_files: Base64 格式的附件列表 [{"name": "...", "data": "..."}]
        """
        if not self.client:
            return {"error": "后端未就绪"}

        resources = []

        # 处理本地文件
        if files:
            for file_path in files:
                if os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    target_name = self._get_safe_filename(file_name)
                    target_path = os.path.join(self.attachments_dir, target_name)
                    shutil.copy2(file_path, target_path)
                    resources.append(f"data/memos/attachments/{target_name}")

        # 处理 Base64 文件 (通常来自 Web UI)
        if base64_files:
            for f in base64_files:
                name = f.get("name")
                data = f.get("data")
                if name and data:
                    # 移除 Base64 前缀 (例如: data:image/png;base64,)
                    if "," in data:
                        data = data.split(",")[1]

                    target_name = self._get_safe_filename(name)
                    target_path = os.path.join(self.attachments_dir, target_name)
                    with open(target_path, "wb") as fb:
                        fb.write(base64.b64decode(data))
                    resources.append(f"data/memos/attachments/{target_name}")

        return self.client.call("add_memo", {
            "content": content,
            "tags": tags or [],
            "resources": resources
        })

    def _get_safe_filename(self, filename: str) -> str:
        """获取不重复的文件名"""
        if not os.path.exists(os.path.join(self.attachments_dir, filename)):
            return filename
        base, ext = os.path.splitext(filename)
        import time
        return f"{base}_{int(time.time() * 1000)}{ext}"

    def list_memos(self, limit: int = 20, offset: int = 0):
        if not self.client: return []
        return self.client.call("list_memos", {"limit": limit, "offset": offset})

    def search_memos(self, query: str):
        if not self.client: return []
        return self.client.call("search_memos", {"query": query})

    def delete_memo(self, memo_id: int):
        if not self.client: return "错误"
        return self.client.call("delete_memo", {"id": memo_id})

    def stop(self):
        """停止后端进程"""
        if self.client:
            self.client.stop()
            self.client = None
            self._initialized = False
            MemosSkill._instance = None

def handle_request(action: str, **kwargs):
    """
    Skill 入口点 (含中文注释)
    """
    # 获取单例
    memos = MemosSkill()
    jarvis_app = kwargs.get("jarvis_app")

    if action == "add":
        content = kwargs.get("content", "")
        tags = kwargs.get("tags", [])
        files = kwargs.get("files", [])
        base64_files = kwargs.get("base64_files", [])

        if not content and not tags and not files and not base64_files:
             return "错误：备忘录内容不能为空。"

        result = memos.add_memo(content, tags, files, base64_files)

        # 如果是从对话调用的，可能需要渲染卡片到 UI
        if jarvis_app and result and "id" in result:
             # 在对话流中渲染卡片 (针对 bcli 方案 A)
             jarvis_app.ui_print(content, tag="memo_card", response_id=result.get("id"))

        return f"备忘录已保存。ID: {result.get('id')}" if result and "id" in result else "保存失败。"

    elif action == "list":
        return memos.list_memos(kwargs.get("limit", 20), kwargs.get("offset", 0))

    elif action == "search":
        return memos.search_memos(kwargs.get("query", ""))

    elif action == "delete":
        memo_id = kwargs.get("id")
        return memos.delete_memo(int(memo_id)) if memo_id else "错误：未指定 ID。"

    return "未知操作。"
