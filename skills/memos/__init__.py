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

    def update_memo(self, memo_id: int, content: Optional[str] = None, tags: Optional[List[str]] = None, files: Optional[List[str]] = None, base64_files: Optional[List[Dict[str, str]]] = None, is_pinned: Optional[int] = None, is_archived: Optional[int] = None):
        """
        更新一条备忘录。
        """
        if not self.client:
            return {"error": "后端未就绪"}

        params = {"id": memo_id}
        if content is not None:
            params["content"] = content
        if tags is not None:
            params["tags"] = tags
        if is_pinned is not None:
            params["is_pinned"] = is_pinned
        if is_archived is not None:
            params["is_archived"] = is_archived

        # If files or base64_files are provided, process and append to resources
        resources = []
        has_new_resources = False
        if files:
            has_new_resources = True
            for file_path in files:
                if os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    target_name = self._get_safe_filename(file_name)
                    target_path = os.path.join(self.attachments_dir, target_name)
                    shutil.copy2(file_path, target_path)
                    resources.append(f"data/memos/attachments/{target_name}")

        if base64_files:
            has_new_resources = True
            for f in base64_files:
                name = f.get("name")
                data = f.get("data")
                if name and data:
                    if "," in data:
                        data = data.split(",")[1]
                    target_name = self._get_safe_filename(name)
                    target_path = os.path.join(self.attachments_dir, target_name)
                    with open(target_path, "wb") as fb:
                        fb.write(base64.b64decode(data))
                    resources.append(f"data/memos/attachments/{target_name}")

        if has_new_resources:
            params["resources"] = resources

        return self.client.call("update_memo", params)

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

    elif action == "update":
        memo_id = kwargs.get("id")
        if not memo_id:
            return "错误：未指定 ID。"
        content = kwargs.get("content")
        tags = kwargs.get("tags")
        files = kwargs.get("files")
        base64_files = kwargs.get("base64_files")
        is_pinned = kwargs.get("is_pinned")
        is_archived = kwargs.get("is_archived")

        result = memos.update_memo(
            int(memo_id),
            content=content,
            tags=tags,
            files=files,
            base64_files=base64_files,
            is_pinned=is_pinned,
            is_archived=is_archived
        )
        return "备忘录已更新。" if result == "success" else "更新失败。"

    elif action == "list":
        return memos.list_memos(kwargs.get("limit", 20), kwargs.get("offset", 0))

    elif action == "search":
        return memos.search_memos(kwargs.get("query", ""))

    elif action == "delete":
        memo_id = kwargs.get("id")
        return memos.delete_memo(int(memo_id)) if memo_id else "错误：未指定 ID。"

    elif action == "ai_tag_predict":
        # 异步 AI 标签预测接口，通过 NLUService 调用本地 LLM
        content = kwargs.get("content", "")
        if not content:
            return []
        if jarvis_app and hasattr(jarvis_app, "nlu_service"):
            prompt = f"分析以下备忘录内容，提取1至3个最相关的中文社交标签（例如：#生活, #学习, #技术, #会议, #随笔）。仅返回标签名称，以空格分隔。例如: '#技术 #学习'。内容如下：\n{content}"
            try:
                res = jarvis_app.nlu_service.ask_llm(prompt, use_habit=False)
                tags = [t.strip() for t in res.split() if t.strip().startswith('#')]
                return tags[:3]
            except Exception as e:
                print(f"AI Tag prediction failed: {e}")
        return []

    elif action == "ai_magic_wand":
        # AI 润色、摘要、待办转化
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "summary") # summary, polish, todo
        if not content:
            return "错误：内容不能为空。"
        if jarvis_app and hasattr(jarvis_app, "nlu_service"):
            if mode == "summary":
                prompt = f"请为以下内容生成一段极简的摘要或总结（TL;DR），适合作为备忘卡片快速阅读，限制在50字内。内容：\n{content}"
            elif mode == "polish":
                prompt = f"请美化并润色以下备忘录内容，进行优雅的排版（可以使用 Markdown 分点整理或修辞微调），保持原意但看起来更加专业清爽。内容：\n{content}"
            elif mode == "todo":
                prompt = f"请提取或转化以下内容，将其转变为一个清晰的待办事项 Markdown 列表（使用 - [ ] 格式），方便打钩。内容：\n{content}"
            else:
                return "错误：未知模式。"

            try:
                res = jarvis_app.nlu_service.ask_llm(prompt, use_habit=False)
                return res.strip()
            except Exception as e:
                return f"AI 处理失败: {str(e)}"
        return "AI 服务未就绪。"

    return "未知操作。"
