# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from butler.memory.sqlite_memory import SQLiteMemory

class MemoryManager:
    """
    Unified Memory Manager using SQLiteMemory.
    """
    def __init__(self, db_path: str = None):
        self.sqlite_mem = SQLiteMemory(db_path=db_path)

    def store(self, key: str, value: str):
        self.sqlite_mem.save(key, value)

    def get(self, key: str) -> Optional[str]:
        return self.sqlite_mem.get(key)

    def search(self, query: str) -> List[Dict[str, Any]]:
        return self.sqlite_mem.search(query)
