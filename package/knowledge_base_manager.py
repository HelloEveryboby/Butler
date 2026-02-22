"""
知识库管理器：利用 zvec 实现本地文档的高效索引与语义检索。
支持联网 (DeepSeek) 和完全离线模式。
"""

import os
import sys
import json
import time
from typing import List, Dict, Any, Optional
from package.log_manager import LogManager
from package.embedding_utils import get_embedding

# 动态添加 markitdown 源码路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'butler', 'markitdown', 'src')))

try:
    import numpy as np
    from markitdown.main import convert as md_convert
except ImportError:
    pass

logger = LogManager.get_logger(__name__)
API_KEY = os.getenv("DEEPSEEK_API_KEY")

class KnowledgeBase:
    """
    表示一个 zvec 驱动的语义知识库。
    """
    def __init__(self, name: str):
        self.name = name
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_path = os.path.join(base_dir, "../data/knowledge_bases", name)
        self.collection = None
        self._offline = (API_KEY is None)
        self._init_zvec()

    def _init_zvec(self):
        try:
            import zvec
        except (ImportError, RuntimeError, Exception) as e:
            logger.error(f"zvec 库加载失败 (可能由于硬件不兼容或未安装): {e}")
            return

        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)

        try:
            schema = zvec.CollectionSchema(
                name=self.name,
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 1024),
                fields=[
                    zvec.FieldSchema("content", zvec.DataType.STRING),
                    zvec.FieldSchema("source", zvec.DataType.STRING),
                    zvec.FieldSchema("timestamp", zvec.DataType.DOUBLE)
                ]
            )
            self.collection = zvec.create_and_open(path=self.base_path, schema=schema)
        except Exception as e:
            logger.error(f"初始化知识库 {self.name} 失败: {e}")

    def add_document(self, content: str, source: str):
        if not self.collection: return
        import zvec

        chunk_size = 1000
        overlap = 200
        chunks = []
        if len(content) <= chunk_size:
            chunks = [content]
        else:
            for i in range(0, len(content), chunk_size - overlap):
                chunks.append(content[i:i + chunk_size])
                if i + chunk_size >= len(content): break

        docs = []
        for i, chunk in enumerate(chunks):
            emb = get_embedding(chunk, API_KEY, offline=self._offline)
            if emb is not None:
                doc = zvec.Doc(
                    id=f"{os.path.basename(source)}_{i}_{int(time.time())}",
                    vectors={"embedding": emb.tolist()},
                    fields={
                        "content": chunk,
                        "source": source,
                        "timestamp": time.time()
                    }
                )
                docs.append(doc)

        if docs:
            try:
                self.collection.insert(docs)
                logger.info(f"成功将 {len(docs)} 个数据块从 {source} 存入知识库。")
            except Exception as e:
                logger.error(f"数据插入失败: {e}")

    def search(self, query_text: str, topk: int = 5) -> List[Dict[str, Any]]:
        if not self.collection: return []
        import zvec

        emb = get_embedding(query_text, API_KEY, offline=self._offline)
        if emb is None: return []

        query = zvec.VectorQuery(field_name="embedding", vector=emb.tolist())
        try:
            results = self.collection.query(vectors=query, topk=topk)
            return [
                {
                    "content": doc.field("content"),
                    "source": doc.field("source"),
                    "score": doc.score
                } for doc in results
            ]
        except Exception as e:
            logger.error(f"知识库查询失败: {e}")
            return []

def run(*args, **kwargs):
    operation = kwargs.get("operation")
    kb_name = kwargs.get("kb_name", "default")

    kb = KnowledgeBase(kb_name)

    if operation == "index_file":
        file_path = kwargs.get("file_path")
        if not file_path or not os.path.exists(file_path):
            return f"错误: 文件不存在 {file_path}"
        try:
            result = md_convert(file_path)
            content = result.text_content
            kb.add_document(content, file_path)
            return f"成功索引文件: {file_path}"
        except Exception as e:
            return f"索引文件失败: {e}"

    elif operation == "index_dir":
        dir_path = kwargs.get("dir_path")
        if not dir_path or not os.path.isdir(dir_path):
            return f"错误: 目录不存在 {dir_path}"

        count = 0
        for root, _, files in os.walk(dir_path):
            for f in files:
                if f.lower().endswith(('.pdf', '.docx', '.md', '.txt', '.pptx', '.xlsx')):
                    path = os.path.join(root, f)
                    try:
                        result = md_convert(path)
                        content = result.text_content
                        kb.add_document(content, path)
                        count += 1
                    except Exception as e:
                        logger.warning(f"无法索引文件 {path}: {e}")
        return f"成功在 {dir_path} 索引了 {count} 个文件。"

    elif operation == "query":
        query_text = kwargs.get("query")
        if not query_text:
            return "错误: 请提供查询内容。"

        results = kb.search(query_text)
        if not results:
            return "未在知识库中找到相关信息。"

        resp = f"在知识库 '{kb_name}' 中找到以下相关内容:\n\n"
        for res in results:
            resp += f"来自: {res['source']} (相似度: {res['score']:.4f})\n"
            resp += f"内容: {res['content'][:500]}...\n"
            resp += "-" * 20 + "\n"
        return resp

    elif operation == "list":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        kb_dir = os.path.join(base_dir, "../data/knowledge_bases")
        if not os.path.exists(kb_dir): return "目前没有任何知识库。"
        kbs = [d for d in os.listdir(kb_dir) if os.path.isdir(os.path.join(kb_dir, d))]
        return "现有知识库: " + ", ".join(kbs) if kbs else "目前没有任何知识库。"

    return f"不支持的操作: {operation}。支持的操作: index_file, index_dir, query, list。"
