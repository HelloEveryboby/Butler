"""翻译记忆库（TM）—— 复用 Butler 多级降级向量库策略（Redis → Zvec → SQLite FTS5）。

查重链路（每条待译文本）：
1. 精确命中 cache（TranslationCache，由 TranslationSystem 负责，这里做 TM 内精确命中兜底）
2. 语义命中 TM：向量检索 top-1，相似度 ≥ reuse_threshold (0.92) → 直接复用历史译文（零成本）
3. 相似命中：fewshot_threshold (0.80) ≤ sim < 0.92 → 把相似 src/tgt 对作为 few-shot 塞进 prompt
4. 未命中 → 正常走 LLM，结果回写 TM

存储降级：
- 向量检索优先走 Redis（redisvl）→ Zvec，参照 butler/core/memory/memory_engine.py 的实现思路；
- 两者都不可用时降级到 SQLite（FTS5 全文检索 + 编辑距离相似度），绝不直接崩溃。

Embedding 复用 package.core_utils.embedding_utils.get_embedding；该模块不可导入
（如缺 pydantic）时自动降级到同算法的本地字符 n-gram 哈希向量（1024 维，纯 Python）。
"""

from __future__ import annotations

import difflib
import json
import math
import sqlite3
import threading
import time
import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# 可选依赖：向量库
try:
    import redis  # noqa: F401
    from redisvl.index import SearchIndex  # noqa: F401
    from redisvl.query import VectorQuery  # noqa: F401
    _HAS_REDIS = True
except Exception:  # noqa: BLE001
    _HAS_REDIS = False

try:
    import zvec  # noqa: F401
    _HAS_ZVEC = True
except Exception:  # noqa: BLE001
    _HAS_ZVEC = False


EMBED_DIM = 1024

# 默认阈值
DEFAULT_REUSE_THRESHOLD = 0.92   # ≥ 此值直接复用
DEFAULT_FEWSHOT_THRESHOLD = 0.80  # ≥ 此值作为 few-shot 参考


# ---------- Embedding（复用 Butler 的 get_embedding，失败时本地降级） ----------

_local_embedding_cache: Dict[str, List[float]] = {}
_local_embedding_lock = threading.Lock()


def _local_embedding(text: str, dimension: int = EMBED_DIM) -> List[float]:
    """离线向量化：字符 3-gram 哈希投影（与 embedding_utils 的离线方案同算法）。"""
    with _local_embedding_lock:
        cached = _local_embedding_cache.get(text)
        if cached is not None:
            return cached
    vec = [0.0] * dimension
    n = 3
    for i in range(max(0, len(text) - n + 1)):
        ngram = text[i:i + n]
        h = int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16)
        vec[h % dimension] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    with _local_embedding_lock:
        if len(_local_embedding_cache) > 5000:
            _local_embedding_cache.clear()
        _local_embedding_cache[text] = vec
    return vec


def get_text_embedding(text: str, api_key: Optional[str] = None) -> List[float]:
    """获取文本向量：优先 Butler 的 get_embedding，失败时本地哈希降级。"""
    try:
        from package.core_utils.embedding_utils import get_embedding
        emb = get_embedding(text, api_key)
        if emb is not None:
            return [float(x) for x in emb]
    except Exception:  # noqa: BLE001
        pass
    return _local_embedding(text)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _edit_similarity(a: str, b: str) -> float:
    """基于编辑距离的相似度：1 - dist / max_len。"""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    # 滚动数组 DP，O(la*lb)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ca == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    dist = prev[lb]
    return 1.0 - dist / max(la, lb)


def _sequence_similarity(a: str, b: str) -> float:
    """序列相似度（最长公共子序列类），对轻微增删更宽容。"""
    return difflib.SequenceMatcher(None, a, b).ratio()


def default_similarity(a: str, b: str, emb_a: Optional[List[float]] = None,
                       emb_b: Optional[List[float]] = None) -> float:
    """综合相似度 = max(编辑距离, 序列, 向量余弦)。"""
    sim = max(_edit_similarity(a, b), _sequence_similarity(a, b))
    if emb_a is not None and emb_b is not None:
        sim = max(sim, _cosine(emb_a, emb_b))
    return sim


def _pack_embedding(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_embedding(blob: bytes) -> List[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


# ---------- 数据结构 ----------

@dataclass
class TMEntry:
    """一条翻译记忆。"""
    id: str
    source: str
    target: str
    from_lang: str = "auto"
    to_lang: str = "zh-CN"
    provider: str = ""
    ts: float = field(default_factory=time.time)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "from_lang": self.from_lang,
            "to_lang": self.to_lang,
            "provider": self.provider,
            "ts": self.ts,
        }


@dataclass
class TMResult:
    """TM 查询结果。"""
    match_type: str                      # exact | semantic | similar | none
    entry: Optional[TMEntry] = None      # 命中的最佳条目（similar 时也可为 None）
    similarity: float = 0.0
    fewshot: List[Tuple[str, str]] = field(default_factory=list)  # (source, target)

    @property
    def reusable(self) -> bool:
        """是否可以直接复用译文（零成本）。"""
        return self.match_type in ("exact", "semantic")


# ---------- SQLite 后端（永远可用，降级终点） ----------

class SqliteTMStore:
    """SQLite 存储：主表 + FTS5（可用时）全文检索。"""

    def __init__(self, db_path: str, collection: str = "tm_entries"):
        self.db_path = str(db_path)
        self.collection = collection
        self._lock = threading.RLock()
        self._fts_available = False
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self) -> None:
        t = f'"{self.collection}"'
        ft = f'"{self.collection}_fts"'
        with self._conn:
            self._conn.execute(
                f"CREATE TABLE IF NOT EXISTS {t} ("
                "id TEXT PRIMARY KEY, source TEXT, target TEXT, from_lang TEXT, "
                "to_lang TEXT, provider TEXT, ts REAL, embedding BLOB);"
            )
            try:
                self._conn.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS {ft} USING fts5("
                    f"source, target, id UNINDEXED, content={t});"
                )
                self._conn.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {self.collection}_ai AFTER INSERT ON {t} BEGIN "
                    f"INSERT INTO {ft}(rowid, source, target, id) "
                    "VALUES (new.rowid, new.source, new.target, new.id); END;"
                )
                self._conn.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {self.collection}_ad AFTER DELETE ON {t} BEGIN "
                    f"INSERT INTO {ft}({ft}, rowid, source, target, id) "
                    "VALUES('delete', old.rowid, old.source, old.target, old.id); END;"
                )
                self._conn.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {self.collection}_au AFTER UPDATE ON {t} BEGIN "
                    f"INSERT INTO {ft}({ft}, rowid, source, target, id) "
                    "VALUES('delete', old.rowid, old.source, old.target, old.id); "
                    f"INSERT INTO {ft}(rowid, source, target, id) "
                    "VALUES (new.rowid, new.source, new.target, new.id); END;"
                )
                self._fts_available = True
            except sqlite3.OperationalError:
                # FTS5 不可用 → 后续走 LIKE / 全表扫描
                self._fts_available = False

    def upsert(self, entry: TMEntry) -> None:
        t = f'"{self.collection}"'
        blob = _pack_embedding(entry.embedding) if entry.embedding else None
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT OR REPLACE INTO {t} "
                "(id, source, target, from_lang, to_lang, provider, ts, embedding) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (entry.id, entry.source, entry.target, entry.from_lang,
                 entry.to_lang, entry.provider, entry.ts, blob),
            )

    @staticmethod
    def _row_to_entry(row) -> TMEntry:
        emb = _unpack_embedding(row[7]) if row[7] else None
        return TMEntry(
            id=row[0], source=row[1], target=row[2], from_lang=row[3],
            to_lang=row[4], provider=row[5], ts=row[6], embedding=emb,
        )

    def find_exact(self, source: str, to_lang: str, from_lang: str = "auto") -> Optional[TMEntry]:
        t = f'"{self.collection}"'
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM {t} WHERE source = ? AND to_lang = ? LIMIT 1",
                (source, to_lang),
            )
            row = cur.fetchone()
        return self._row_to_entry(row) if row else None

    @staticmethod
    def _sanitize_query(text: str) -> str:
        """清理查询字符串，防止 FTS5 语法错误。"""
        import re
        return re.sub(r"[^\w\s]", " ", text).strip()

    def candidates(self, source: str, to_lang: str, limit: int = 2000) -> List[TMEntry]:
        """召回候选条目：小库全表扫描（确定性），大库用 FTS5 / LIKE 预筛。"""
        t = f'"{self.collection}"'
        with self._lock:
            total = self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if total <= limit:
                rows = self._conn.execute(
                    f"SELECT * FROM {t} WHERE to_lang = ? LIMIT ?", (to_lang, limit)
                ).fetchall()
                return [self._row_to_entry(r) for r in rows]

            items: List[TMEntry] = []
            if self._fts_available:
                clean = self._sanitize_query(source)
                if clean:
                    ft = f'"{self.collection}_fts"'
                    try:
                        rows = self._conn.execute(
                            f"SELECT {t}.* FROM {ft} JOIN {t} ON {t}.rowid = {ft}.rowid "
                            f"WHERE {ft} MATCH ? LIMIT 50",
                            (clean,),
                        ).fetchall()
                        items = [self._row_to_entry(r) for r in rows]
                    except sqlite3.OperationalError:
                        items = []
            if not items:
                rows = self._conn.execute(
                    f"SELECT * FROM {t} WHERE to_lang = ? AND source LIKE ? LIMIT 50",
                    (to_lang, f"%{source[:20]}%"),
                ).fetchall()
                items = [self._row_to_entry(r) for r in rows]
            return items

    def count(self) -> int:
        t = f'"{self.collection}"'
        with self._lock:
            return self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    def all_entries(self, limit: int = 100) -> List[TMEntry]:
        t = f'"{self.collection}"'
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM {t} ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]


# ---------- Redis 向量后端（可选，第一级） ----------

class RedisTMStore:
    """基于 Redis（redisvl）的向量存储，参照 RedisLongMemory 的降级策略。"""

    def __init__(self, api_key: Optional[str] = None, collection: str = "tm_memory"):
        if not _HAS_REDIS:
            raise ImportError("redis/redisvl is not installed")
        from butler.redis_client import redis_client  # 延迟导入
        if redis_client is None:
            raise ConnectionError("Redis client not initialized")
        self.client = redis_client
        self.api_key = api_key
        self.collection = collection
        schema = {
            "index": {"name": collection, "prefix": f"{collection}:"},
            "fields": [
                {"name": "content", "type": "text"},
                {"name": "metadata", "type": "text"},
                {"name": "embedding", "type": "vector", "attrs": {
                    "dims": EMBED_DIM, "distance_metric": "cosine", "algorithm": "flat"}},
            ],
        }
        self.index = SearchIndex.from_dict(schema)
        self.index.set_client(self.client)
        if not self.client.exists(f"idx:{collection}"):
            self.index.create(overwrite=True)

    def upsert(self, entry: TMEntry) -> None:
        emb = entry.embedding or get_text_embedding(entry.source, self.api_key)
        self.index.load([{
            "id": entry.id,
            "content": entry.source,
            "metadata": json.dumps(entry.to_dict(), ensure_ascii=False),
            "embedding": _pack_embedding(emb),
        }])

    def search(self, source: str, k: int = 5) -> List[TMEntry]:
        emb = get_text_embedding(source, self.api_key)
        results = self.index.query(VectorQuery(
            vector=_pack_embedding(emb), vector_field_name="embedding",
            return_fields=["id", "content", "metadata"], num_results=k,
        ))
        out = []
        for d in results:
            meta = json.loads(d.get("metadata", "{}"))
            out.append(TMEntry(
                id=meta.get("id", d.get("id", "")),
                source=meta.get("source", d.get("content", "")),
                target=meta.get("target", ""),
                from_lang=meta.get("from_lang", "auto"),
                to_lang=meta.get("to_lang", "zh-CN"),
                provider=meta.get("provider", ""),
                ts=meta.get("ts", 0.0),
                embedding=emb,
            ))
        return out


# ---------- Zvec 向量后端（可选，第二级） ----------

class ZvecTMStore:
    """基于 zvec 的本地向量存储，参照 ZvecLongMemory。"""

    def __init__(self, api_key: Optional[str] = None, collection: str = "tm_memory_zvec",
                 data_dir: Optional[str] = None):
        if not _HAS_ZVEC:
            raise ImportError("zvec is not installed")
        self.api_key = api_key
        self.collection_name = collection
        base = data_dir or str(Path.home() / ".butler" / "translate")
        self._data_path = str(Path(base) / "zvec_tm" / collection)
        Path(self._data_path).mkdir(parents=True, exist_ok=True)
        schema = zvec.CollectionSchema(
            name=collection,
            vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, EMBED_DIM),
            fields=[
                zvec.FieldSchema("content", zvec.DataType.STRING),
                zvec.FieldSchema("metadata", zvec.DataType.STRING),
                zvec.FieldSchema("timestamp", zvec.DataType.DOUBLE),
            ],
        )
        self.collection = zvec.create_and_open(path=self._data_path, schema=schema)

    def upsert(self, entry: TMEntry) -> None:
        emb = entry.embedding or get_text_embedding(entry.source, self.api_key)
        self.collection.insert([zvec.Doc(
            id=entry.id,
            vectors={"embedding": list(emb)},
            fields={"content": entry.source,
                    "metadata": json.dumps(entry.to_dict(), ensure_ascii=False),
                    "timestamp": entry.ts},
        )])

    def search(self, source: str, k: int = 5) -> List[TMEntry]:
        emb = get_text_embedding(source, self.api_key)
        results = self.collection.query(
            vectors=zvec.VectorQuery(field_name="embedding", vectors=list(emb)), topk=k)
        out = []
        for d in results:
            meta = json.loads(d.field("metadata") or "{}")
            out.append(TMEntry(
                id=meta.get("id", d.id), source=meta.get("source", d.field("content")),
                target=meta.get("target", ""), from_lang=meta.get("from_lang", "auto"),
                to_lang=meta.get("to_lang", "zh-CN"), provider=meta.get("provider", ""),
                ts=meta.get("ts", 0.0), embedding=emb,
            ))
        return out


# ---------- 翻译记忆主入口 ----------

class TranslationMemory:
    """翻译记忆库：记录 + 分档查找（exact / semantic / similar / none）。"""

    def __init__(
        self,
        db_path: str,
        api_key: Optional[str] = None,
        backend: str = "auto",             # auto | redis | zvec | sqlite
        reuse_threshold: float = DEFAULT_REUSE_THRESHOLD,
        fewshot_threshold: float = DEFAULT_FEWSHOT_THRESHOLD,
        fewshot_max: int = 3,
        similarity_fn: Optional[Callable[[str, str, Optional[List[float]], Optional[List[float]]], float]] = None,
    ):
        self.api_key = api_key
        self.reuse_threshold = reuse_threshold
        self.fewshot_threshold = fewshot_threshold
        self.fewshot_max = fewshot_max
        self._similarity_fn = similarity_fn or default_similarity

        # SQLite 是记录的持久化事实源，永远初始化
        self.store = SqliteTMStore(db_path)

        # 向量后端：Redis → Zvec → 无（降级到 SQLite 检索 + 编辑距离）
        self.vector_backend = None
        self.backend_name = "sqlite"
        if backend in ("auto", "redis", "zvec"):
            self._init_vector_backend(backend)

    def _init_vector_backend(self, backend: str) -> None:
        order = ["redis", "zvec"] if backend == "auto" else [backend]
        for name in order:
            try:
                if name == "redis":
                    self.vector_backend = RedisTMStore(self.api_key)
                else:
                    self.vector_backend = ZvecTMStore(self.api_key)
                self.backend_name = name
                return
            except Exception:  # noqa: BLE001
                continue
        self.vector_backend = None
        self.backend_name = "sqlite"

    # ---------- 阈值分档 ----------

    @staticmethod
    def classify_similarity(
        similarity: float,
        reuse_threshold: float = DEFAULT_REUSE_THRESHOLD,
        fewshot_threshold: float = DEFAULT_FEWSHOT_THRESHOLD,
    ) -> str:
        """相似度分档：semantic / similar / none。"""
        if similarity >= reuse_threshold:
            return "semantic"
        if similarity >= fewshot_threshold:
            return "similar"
        return "none"

    # ---------- 写入 ----------

    def record(
        self,
        source: str,
        target: str,
        from_lang: str = "auto",
        to_lang: str = "zh-CN",
        provider: str = "",
    ) -> TMEntry:
        """回写一条翻译记忆（LLM 产出或人工修订）。"""
        source = source.strip()
        target = target.strip()
        entry = TMEntry(
            id=f"tm_{int(time.time() * 1000)}_{hashlib.md5(source.encode('utf-8')).hexdigest()[:8]}",
            source=source, target=target, from_lang=from_lang,
            to_lang=to_lang, provider=provider,
            embedding=get_text_embedding(source, self.api_key),
        )
        self.store.upsert(entry)
        if self.vector_backend is not None:
            try:
                self.vector_backend.upsert(entry)
            except Exception:  # noqa: BLE001
                # 向量库写失败不致命，SQLite 已持久化
                pass
        return entry

    # ---------- 查询 ----------

    def lookup(self, source_text: str, to_lang: str, from_lang: str = "auto") -> TMResult:
        """按四级链路查找翻译记忆。"""
        if not source_text or not source_text.strip():
            return TMResult(match_type="none")

        source = source_text.strip()

        # 1. 精确命中
        exact = self.store.find_exact(source, to_lang, from_lang)
        if exact is not None:
            return TMResult(match_type="exact", entry=exact, similarity=1.0,
                            fewshot=[(exact.source, exact.target)])

        # 2/3. 语义 / 相似命中
        hits = self._search(source, to_lang, k=max(self.fewshot_max, 3) + 2)
        if not hits:
            return TMResult(match_type="none")

        best_entry, best_sim = hits[0]
        match_type = self.classify_similarity(best_sim, self.reuse_threshold, self.fewshot_threshold)

        fewshot: List[Tuple[str, str]] = []
        if match_type == "semantic":
            fewshot = [(best_entry.source, best_entry.target)]
        elif match_type == "similar":
            for entry, sim in hits:
                if sim >= self.fewshot_threshold and len(fewshot) < self.fewshot_max:
                    fewshot.append((entry.source, entry.target))

        return TMResult(
            match_type=match_type,
            entry=best_entry if match_type == "semantic" else (best_entry if match_type == "similar" else None),
            similarity=best_sim,
            fewshot=fewshot,
        )

    def _search(self, source: str, to_lang: str, k: int) -> List[Tuple[TMEntry, float]]:
        """返回 [(entry, similarity)]，按相似度降序。"""
        scored: List[Tuple[TMEntry, float]] = []
        query_emb = get_text_embedding(source, self.api_key)

        candidates: List[TMEntry] = []
        if self.vector_backend is not None:
            try:
                candidates = self.vector_backend.search(source, k=max(k, 10))
            except Exception:  # noqa: BLE001
                candidates = []
        if not candidates:
            # 降级：SQLite FTS5 / 全表召回 + 相似度打分
            candidates = self.store.candidates(source, to_lang)

        for entry in candidates:
            if entry.to_lang != to_lang:
                continue
            sim = self._similarity_fn(source, entry.source, query_emb, entry.embedding)
            scored.append((entry, sim))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:k]

    # ---------- 统计 / 维护 ----------

    def stats(self) -> Dict:
        entries = self.store.all_entries(limit=10000)
        by_lang: Dict[str, int] = {}
        for e in entries:
            by_lang[e.to_lang] = by_lang.get(e.to_lang, 0) + 1
        return {
            "backend": self.backend_name,
            "entries": self.store.count(),
            "by_lang": by_lang,
            "reuse_threshold": self.reuse_threshold,
            "fewshot_threshold": self.fewshot_threshold,
            "recent": [e.to_dict() for e in self.store.all_entries(limit=5)],
        }

    def export_entries(self, limit: int = 10000) -> List[dict]:
        return [e.to_dict() for e in self.store.all_entries(limit=limit)]
