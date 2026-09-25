# -*- coding: utf-8 -*-
"""话题管理器 —— 解决"AI 聊着聊着换了话题 / 想回到之前的话题就失忆"。

核心思想: 把**话题 (Topic)** 做成一等公民结构，而不是指望线性上下文自己记得：

- 每个话题 = 标题 + 对话片段 + 已定事项 + 未决问题 + 涉及产物
- 换话题时旧话题自动**挂起存档**（快照），随时可"回到 XX 话题"完整恢复
- 检索基于字符余弦相似度（离线可用，无 LLM 依赖）；快照为模板生成，
  接入 LLM 后可升级为语义摘要（预留 summarize 钩子）

持久化: data/topics.json（原子写入）。用法::

    from butler.core.topic_manager import topic_manager
    topic_manager.observe("帮我把报告排版")           # 每条用户消息都过一遍
    topic_manager.recall("报告排版")                  # 回到之前的话题
    topic_manager.context_snippets()                  # 供注入提示的上下文块
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from butler.core.algorithms import char_ngram_cosine

logger = logging.getLogger("TopicManager")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE = PROJECT_ROOT / "data" / "topics.json"

# 显式话语信号
NEW_TOPIC_MARKERS = ["换个话题", "换话题", "新话题", "说点别的", "聊点别的", "换个方向",
                     "对了", "另外", "话说回来", "先不说这个"]
RECALL_MARKERS = ["回到", "说回", "聊回", "接回", "刚才", "之前", "上一个", "上次", "接着说"]

SIMILARITY_SWITCH_BELOW = 0.22   # 与当前话题相似度低于此值且无回忆信号 → 判定为新话题
MAX_MESSAGES_PER_TOPIC = 24      # 每个话题保留的对话片段上限（检索语料）
MAX_TOPICS = 200                 # 话题总数上限（超出淘汰最旧的已挂起话题）


@dataclass
class Topic:
    id: str
    title: str
    status: str = "active"                 # active | suspended | done
    messages: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    open_loops: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    snapshot: str = ""

    def corpus(self) -> str:
        """检索语料。"""
        return " ".join([self.title] + self.messages[-8:] + self.decisions + self.open_loops)


class TopicManager:
    """话题生命周期管理（单例见模块底部 ``topic_manager``）。"""

    def __init__(self, store_path: Optional[Path] = None):
        self._path = Path(store_path or DEFAULT_STORE)
        self._lock = threading.RLock()
        self._topics: Dict[str, Topic] = {}
        self._order: List[str] = []          # 按创建顺序
        self._current_id: Optional[str] = None
        self._counter = 0
        self._load()

    # ---------- 持久化 ----------

    def _load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                for item in raw.get("topics", []):
                    t = Topic(**item)
                    self._topics[t.id] = t
                    self._order.append(t.id)
                self._current_id = raw.get("current_id")
                self._counter = raw.get("counter", len(self._topics))
        except Exception as exc:
            logger.warning(f"话题存档加载失败（将从空开始）: {exc}")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "current_id": self._current_id,
                "counter": self._counter,
                "topics": [asdict(self._topics[i]) for i in self._order if i in self._topics],
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception as exc:
            logger.warning(f"话题存档写入失败: {exc}")

    # ---------- 生命周期 ----------

    @property
    def current(self) -> Optional[Topic]:
        return self._topics.get(self._current_id) if self._current_id else None

    def start_topic(self, title: str) -> Topic:
        with self._lock:
            self._counter += 1
            topic = Topic(id=f"T{self._counter}", title=self._auto_title(title))
            topic.messages.append(title[:120])
            self._topics[topic.id] = topic
            self._order.append(topic.id)
            self._current_id = topic.id
            self._trim()
            self._save()
            return topic

    def suspend_current(self, summary: Optional[str] = None) -> Optional[Topic]:
        """挂起当前话题并生成快照。"""
        with self._lock:
            topic = self.current
            if topic is None:
                return None
            topic.status = "suspended"
            topic.snapshot = summary or self.snapshot_text(topic)
            self._current_id = None
            self._save()
            return topic

    def observe(self, text: str) -> Dict[str, Any]:
        """每条用户消息调用。返回 {'event': 'continue'|'switch'|'recall'|'idle', ...}"""
        text = (text or "").strip()
        if not text:
            return {"event": "idle"}

        has_new = any(m in text for m in NEW_TOPIC_MARKERS)
        has_recall = any(m in text for m in RECALL_MARKERS)

        with self._lock:
            topic = self.current
            if topic is None:
                self.start_topic(text)
                return {"event": "switch", "to": self._topics[self._current_id].title,
                        "message": f"已开启话题「{self._topics[self._current_id].title}」"}

            if has_new and not has_recall:
                prev_title = topic.title
                self.suspend_current()
                self.start_topic(text)
                return {"event": "switch", "from": prev_title,
                        "to": self._topics[self._current_id].title,
                        "message": f"已切换话题：「{prev_title}」已存档（可说「回到{prev_title}」恢复）"}

            similarity = char_ngram_cosine(text, topic.corpus())
            if not has_recall and similarity < SIMILARITY_SWITCH_BELOW and len(topic.messages) >= 2:
                prev_title = topic.title
                self.suspend_current()
                self.start_topic(text)
                return {"event": "switch", "from": prev_title,
                        "to": self._topics[self._current_id].title,
                        "message": f"这像是新话题「{self._topics[self._current_id].title}」，"
                                   f"之前的「{prev_title}」已存档"}

            topic.messages.append(text[:120])
            topic.messages = topic.messages[-MAX_MESSAGES_PER_TOPIC:]
            topic.last_active = time.time()
            self._save()
            return {"event": "continue", "topic": topic.title, "similarity": round(similarity, 3)}

    # ---------- 记录 ----------

    def add_decision(self, text: str) -> None:
        with self._lock:
            if self.current and text not in self.current.decisions:
                self.current.decisions.append(text)
                self._save()

    def add_open_loop(self, text: str) -> None:
        with self._lock:
            if self.current and text not in self.current.open_loops:
                self.current.open_loops.append(text)
                self._save()

    def add_artifact(self, text: str) -> None:
        with self._lock:
            if self.current and text not in self.current.artifacts:
                self.current.artifacts.append(text)
                self._save()

    # ---------- 回溯 / 查询 ----------

    def recall(self, query: str, top: int = 3) -> List[Dict[str, Any]]:
        """按查询找回话题（含已挂起），按相似度降序。"""
        query = (query or "").strip()
        with self._lock:
            scored = []
            for tid in self._order:
                t = self._topics.get(tid)
                if t is None:
                    continue
                score = char_ngram_cosine(query, t.corpus()) if query else 0.0
                scored.append({"topic": asdict(t), "score": round(score, 3)})
            scored.sort(key=lambda x: (x["score"], x["topic"]["last_active"]), reverse=True)
            return scored[:top]

    def resume(self, query: str = "") -> Dict[str, Any]:
        """恢复最匹配的话题为当前话题，返回其快照。"""
        candidates = self.recall(query, top=1)
        with self._lock:
            if not candidates:
                return {"status": "error", "message": "没有找到可恢复的话题。"}
            topic = self._topics.get(candidates[0]["topic"]["id"])
            if topic is None:
                return {"status": "error", "message": "话题不存在。"}
            if self.current and self.current.id != topic.id:
                self.suspend_current()
            topic.status = "active"
            topic.last_active = time.time()
            self._current_id = topic.id
            self._save()
            return {"status": "ok", "topic": topic.title, "snapshot": topic.snapshot or self.snapshot_text(topic)}

    def list_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            items = [asdict(self._topics[tid]) for tid in self._order if tid in self._topics]
        items.sort(key=lambda t: t["last_active"], reverse=True)
        return items[:limit]

    def snapshot_text(self, topic: Topic) -> str:
        """模板快照（LLM 钩子预留: 可替换为语义摘要）。"""
        lines = [f"话题「{topic.title}」"]
        if topic.decisions:
            lines.append("已定: " + "；".join(topic.decisions[-5:]))
        if topic.open_loops:
            lines.append("未决: " + "；".join(topic.open_loops[-5:]))
        if topic.artifacts:
            lines.append("涉及: " + "，".join(topic.artifacts[-5:]))
        if topic.messages:
            lines.append("最近讨论: " + topic.messages[-1][:60])
        return "\n".join(lines)

    def context_snippets(self, n: int = 2) -> str:
        """供注入提示词的话题上下文块：当前话题 + 最近挂起快照。"""
        with self._lock:
            parts = []
            if self.current:
                parts.append("【当前话题】\n" + self.snapshot_text(self.current))
            suspended = [self._topics[tid] for tid in reversed(self._order)
                         if tid in self._topics and self._topics[tid].status == "suspended"]
            for t in suspended[:n]:
                parts.append("【已存档话题，可恢复】\n" + (t.snapshot or self.snapshot_text(t)))
        return "\n\n".join(parts)

    # ---------- 工具 ----------

    @staticmethod
    def _auto_title(text: str) -> str:
        title = text
        for marker in NEW_TOPIC_MARKERS:      # 去掉“换个话题/对了”等引导词
            title = title.replace(marker, "")
        title = re.sub(r"[\s，,。；;！!？?#*`：:]+", "", title)[:14]
        return title or "未命名话题"

    def _trim(self) -> None:
        while len(self._order) > MAX_TOPICS:
            for tid in list(self._order):
                t = self._topics.get(tid)
                if t is not None and t.status != "active":
                    self._order.remove(tid)
                    self._topics.pop(tid, None)
                    break
            else:
                break


# 全局单例
topic_manager = TopicManager()
