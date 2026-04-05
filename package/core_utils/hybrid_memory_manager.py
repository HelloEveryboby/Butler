import os
from plugin.memory_engine import hybrid_memory_manager

# This is a bridge for legacy code
# 将此类作为旧代码的桥梁，实际逻辑已迁移至 plugin.memory_engine
# 保持“事实数据库 (SQLite/Redis/Zvec) + 原始日志文件 (Markdown)”的双轨制架构

HybridMemoryManager = type(hybrid_memory_manager)
hybrid_memory_manager = hybrid_memory_manager
