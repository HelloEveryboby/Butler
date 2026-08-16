# -*- coding: utf-8 -*-
"""
AI Memory Skill Package
提供基于 Markdown + SQLite FTS5 + Zvec + MCP 的自建 AI 记忆服务。
"""

import os
import json
from typing import Dict, Any, List, Optional
from skills.ai_memory.memory_service import MemoryService
from skills.ai_memory.data_model import MemoryDocument

class AIMemorySkill:
    """
    AI 记忆技能控制单例
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AIMemorySkill, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_root: Optional[str] = None, api_key: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return
        self.service = MemoryService(project_root=project_root, api_key=api_key)
        self._initialized = True


def handle_request(action: str, **kwargs) -> Any:
    """
    Butler 技能通用调用入口
    :param action: 操作指令 (search, save, create_handoff, get_latest_handoff, index_file, session_start, session_end)
    """
    project_root = kwargs.get("project_root") or os.getcwd()
    api_key = kwargs.get("api_key")
    skill = AIMemorySkill(project_root=project_root, api_key=api_key)
    service = skill.service

    if action == "search" or action == "memory_query":
        query = kwargs.get("query") or kwargs.get("text", "")
        limit = kwargs.get("limit", 5)
        if not query:
            return "错误：搜索查询不能为空。"
        return service.hybrid_search(query, limit=limit)

    elif action == "save" or action == "memory_save":
        title = kwargs.get("title", "Untitled Memory")
        content = kwargs.get("content", "")
        summary = kwargs.get("session_summary", "")
        decisions = kwargs.get("decisions", [])
        questions = kwargs.get("open_questions", [])
        project = kwargs.get("project", "default")
        tags = kwargs.get("tags", ["ai-memory"])

        doc = MemoryDocument(
            title=title,
            content=content,
            session_summary=summary,
            decisions=decisions,
            open_questions=questions,
            project=project,
            tags=tags
        )
        saved_path = service.save_memory(doc)
        return {"status": "success", "file_path": saved_path, "doc_id": doc.doc_id}

    elif action == "create_handoff":
        project_name = kwargs.get("project_name", "default")
        summary = kwargs.get("session_summary", "")
        decisions = kwargs.get("decisions", [])
        questions = kwargs.get("open_questions", [])
        title = kwargs.get("title", "Session Handoff")

        doc = service.create_handoff(project_name, summary, decisions, questions, title=title)
        return {"status": "success", "file_path": doc.file_path, "handoff_id": doc.doc_id}

    elif action == "get_latest_handoff":
        project_name = kwargs.get("project_name")
        res = service.get_latest_handoff(project_name=project_name)
        if not res:
            return {"status": "not_found", "message": "未找到交接记录"}
        return {"status": "success", "handoff": res}

    elif action == "index_file":
        file_path = kwargs.get("file_path", "")
        doc = service.index_file(file_path)
        if not doc:
            return {"status": "error", "message": f"无法对文件建立索引: {file_path}"}
        return {"status": "success", "doc_id": doc.doc_id, "title": doc.title}

    elif action == "session_start":
        # 会话开始生命周期钩子：读取最新交接记录
        project_name = kwargs.get("project_name", "default")
        res = service.get_latest_handoff(project_name=project_name)
        if res:
            return {
                "status": "handoff_restored",
                "summary": res.get("session_summary"),
                "decisions": res.get("decisions"),
                "open_questions": res.get("open_questions"),
                "created_at": res.get("created_at")
            }
        return {"status": "no_previous_handoff"}

    elif action == "session_end":
        # 会话结束生命周期钩子：自动生成交接记录
        project_name = kwargs.get("project_name", "default")
        summary = kwargs.get("session_summary", "Session concluded automatically.")
        decisions = kwargs.get("decisions", [])
        questions = kwargs.get("open_questions", [])

        doc = service.create_handoff(project_name, summary, decisions, questions, title="Auto Session End Handoff")
        return {"status": "handoff_saved", "file_path": doc.file_path}

    return f"未知 AI Memory 操作: {action}"
