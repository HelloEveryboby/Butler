# -*- coding: utf-8 -*-
from typing import List, Dict, Any

class ShortTermMemory:
    """
    管理瞬态会话级及任务级临时对话上下文和转存。
    """
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        # 结构: {"session_id": [{"role": "user", "content": "你好"}]}
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}

    def add_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        if session_id not in self._conversations:
            self._conversations[session_id] = []

        msg = {
            "role": role,
            "content": content,
        }
        if metadata:
            msg["metadata"] = metadata

        self._conversations[session_id].append(msg)

        # 保持在指定条数限制内
        if len(self._conversations[session_id]) > self.max_messages:
            self._conversations[session_id] = self._conversations[session_id][-self.max_messages:]

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        return self._conversations.get(session_id, [])

    def clear(self, session_id: str):
        if session_id in self._conversations:
            del self._conversations[session_id]
