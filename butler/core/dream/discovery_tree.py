"""
Dream 发现树 (Discovery Tree) — 论文 §3 "Discovery trees and actions"。

- 根节点 r 代表初始工作区状态；每个非根节点 v 恰好有一个父节点，
  记录一次 CONTINUE 尝试的完整结果：工作区快照、生成物、评估诊断、得分 s_v。
- 原子操作 CONTINUE(v)：恢复 v 的工作区 → 生成一个新候选 → 评估 → 产生子节点。
- 可继续节点集合 A(T) = {根} ∪ {叶子}；一次决策轮选取批次 C ⊆ A(T;W)，
  |C| ≤ W（W 为并行 worker 数）；C = ∅ 终止 rollout。
- 根节点开出新分支（并行探索）；非根叶子继续则推进该分支（细化/修复）。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Node:
    """一次尝试（attempt）的完整记录。"""

    id: str
    parent_id: Optional[str]
    workspace: Dict[str, Any] = field(default_factory=dict)
    artifact: Any = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None          # 根节点为 None；越大越好
    depth: int = 0
    created_at: float = field(default_factory=time.time)
    children: List[str] = field(default_factory=list)

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "workspace": self.workspace,
            "artifact": self.artifact,
            "diagnostics": self.diagnostics,
            "score": self.score,
            "depth": self.depth,
            "created_at": self.created_at,
            "children": list(self.children),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Node":
        return cls(
            id=data["id"],
            parent_id=data.get("parent_id"),
            workspace=data.get("workspace", {}) or {},
            artifact=data.get("artifact"),
            diagnostics=data.get("diagnostics", {}) or {},
            score=data.get("score"),
            depth=int(data.get("depth", 0)),
            created_at=float(data.get("created_at", time.time())),
            children=list(data.get("children", [])),
        )


class DiscoveryTree:
    """一棵发现树：根 + 若干条从根出发的探索/细化路径。"""

    def __init__(self, tree_id: Optional[str] = None,
                 root_workspace: Optional[Dict[str, Any]] = None):
        self.tree_id = tree_id or uuid.uuid4().hex[:12]
        root = Node(id="root", parent_id=None,
                    workspace=root_workspace or {}, depth=0)
        self.nodes: Dict[str, Node] = {root.id: root}

    # ── 结构查询 ──

    @property
    def root(self) -> Node:
        return self.nodes["root"]

    def eligible_nodes(self) -> List[str]:
        """A(T) = {根} ∪ {叶子}（在线模式下=全部已知节点）。"""
        out = ["root"] if "root" in self.nodes else []
        out.extend(nid for nid, n in self.nodes.items()
                   if not n.is_root and n.is_leaf)
        return out

    def child_of(self, node_id: str) -> Optional[Node]:
        """论文中 Child(v;T)：v 的（唯一）已录子节点；无则返回 None。

        注：论文协议下非根节点至多一个子节点（链式细化）；根节点可有
        多个子节点（分支），逐个揭示请用 next_unrevealed_child。
        """
        node = self.nodes.get(node_id)
        if node is None or not node.children:
            return None
        return self.nodes.get(node.children[0])

    def next_unrevealed_child(self, node_id: str,
                              revealed) -> Optional[Node]:
        """回放揭示语义：按录入顺序返回 v 的下一个未揭示子节点。

        对非根节点等价于 Child(v;T)；对根节点对应"从根开新分支"的
        逐次揭示（否则多分支永远无法被回放覆盖）。
        """
        node = self.nodes.get(node_id)
        if node is None:
            return None
        for cid in node.children:
            if cid not in revealed:
                child = self.nodes.get(cid)
                if child is not None:
                    return child
        return None

    def add_child(self, parent_id: str,
                  workspace: Dict[str, Any],
                  artifact: Any = None,
                  diagnostics: Optional[Dict[str, Any]] = None,
                  score: Optional[float] = None) -> Node:
        """执行一次 CONTINUE(parent_id) 的落账：创建并挂接子节点。"""
        parent = self.nodes.get(parent_id)
        if parent is None:
            raise KeyError(f"父节点不存在: {parent_id}")
        node = Node(
            id=uuid.uuid4().hex[:12],
            parent_id=parent_id,
            workspace=workspace or {},
            artifact=artifact,
            diagnostics=diagnostics or {},
            score=score,
            depth=parent.depth + 1,
        )
        self.nodes[node.id] = node
        parent.children.append(node.id)
        return node

    def best_score(self) -> Optional[float]:
        """树中已录尝试的最高得分 max_v s_v（不含根）。"""
        scores = [n.score for n in self.nodes.values()
                  if not n.is_root and n.score is not None]
        return max(scores) if scores else None

    def non_root_count(self) -> int:
        return sum(1 for n in self.nodes.values() if not n.is_root)

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return {
            "tree_id": self.tree_id,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveryTree":
        tree = cls(tree_id=data.get("tree_id"))
        tree.nodes = {nid: Node.from_dict(nd)
                      for nid, nd in data.get("nodes", {}).items()}
        if "root" not in tree.nodes:
            raise ValueError("发现树缺少根节点")
        return tree


class DiscoveryForest:
    """发现历史 H_t = (T_1, ..., T_t)：做梦阶段的回放世界池。"""

    def __init__(self, trees: Optional[List[DiscoveryTree]] = None):
        self.trees: List[DiscoveryTree] = list(trees or [])

    def append(self, tree: DiscoveryTree) -> None:
        self.trees.append(tree)

    def __len__(self) -> int:
        return len(self.trees)

    def summary(self) -> Dict[str, Any]:
        bests = [t.best_score() for t in self.trees if t.best_score() is not None]
        return {
            "trees": len(self.trees),
            "attempts": sum(t.non_root_count() for t in self.trees),
            "best_score": max(bests) if bests else None,
        }

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return {"trees": [t.to_dict() for t in self.trees]}

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveryForest":
        return cls([DiscoveryTree.from_dict(t) for t in data.get("trees", [])])

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False),
                        encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "DiscoveryForest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)
