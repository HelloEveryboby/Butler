# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from butler.memory.short_term import ShortTermMemory
from butler.memory.long_term import LongTermMemory

class MemoryManager:
    """
    统一记忆管理门户：整合短期会话上下文与长期 SQLite 数据持久化。
    """
    def __init__(self, db_path: str = None):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(db_path=db_path)

    def store(self, type_str: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        在长期 SQLite 数据库中保存一个记忆。
        """
        return self.long_term.store(type_str, content, metadata)

    def search(self, query: str, type_str: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        检索长期历史事实或习惯记录。
        """
        return self.long_term.search(query, type_str, limit)

    def add_conversation_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        """
        在短期缓存中添加一条对话记录。
        """
        self.short_term.add_message(session_id, role, content, metadata)

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取指定会话当前的活跃对话历史。
        """
        return self.short_term.get_messages(session_id)

    def clear_conversation(self, session_id: str):
        """
        清空指定会话的短期对话上下文缓存。
        """
        self.short_term.clear(session_id)
