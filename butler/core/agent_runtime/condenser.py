"""
Condenser — Token 预算驱动的重要性感知压缩策略。

设计目标：省 token、保质量。
    - 不再按"消息条数"压缩，而是按 token 预算贪婪保留高价值消息。
    - 低价值消息不会被无声丢弃：其关键事实（文件路径、工具、错误、决策、
      用户请求）被抽取浓缩进一条结构化 Context Card，作为降级安全网。
    - 重要性打分无需 LLM；LLM（可选）用于把 Context Card 升级为自然语言摘要。

核心组件：
    - ImportanceScorer: 消息重要性打分器（0-100，无需 LLM）
    - BudgetCondenser:  按 token 预算 + 重要性保留消息的压缩策略

统一接口（与旧设计兼容）：
    condense(messages: list[Message]) -> list[Message]
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Callable

from .types import Message

logger = logging.getLogger(__name__)


# ── 工具集分类（决定 tool_impact 分数）─────────────────────────────
_WRITE_TOOLS = {
    "write", "edit", "create", "delete", "remove", "move", "rename",
    "mkdir", "rmdir", "patch", "apply", "save", "install", "execute",
    "run", "bash", "shell",
}
_READ_TOOLS = {
    "read", "grep", "glob", "ls", "find", "search", "cat", "head",
    "tail", "stat", "list",
}

# 文件路径正则：匹配 /path/to/file、\path\to\file、file.ext
_PATH_RE = re.compile(
    r"(?:[\w.\-]+[/\\])+[\w.\-]+"
    r"|[\w\-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cpp|h|hpp|md|json|ya?ml|txt|sh|toml|xml|html|css)"
)

# 内容信号关键词（出现即提升重要性）
_SIGNAL_KW = {
    "error": ("error", "exception", "traceback", "failed", "failure", "失败", "报错", "错误"),
    "fix": ("fix", "fixed", "resolved", "修复", "解决"),
    "decision": ("decision", "decided", "决定", "should", "must", "需要", "方案"),
    "todo": ("todo", "fixme", "待办"),
    "code": ("```", "def ", "class ", "function ", "import "),
}


def _estimate_tokens(messages: list[Message]) -> int:
    """粗略 token 估算（与 ConversationState 一致：4 字符 ≈ 1 token）。"""
    total_chars = 0
    for m in messages:
        total_chars += len(m.content or "")
        for tc in m.tool_calls:
            # 工具调用的 name + arguments 也占 token
            total_chars += len(tc.name) + sum(
                len(str(v)) for v in tc.arguments.values()
            )
    return total_chars // 4


def _extract_paths(text: str) -> list[str]:
    """从文本中提取文件路径。"""
    if not text:
        return []
    return list(dict.fromkeys(_PATH_RE.findall(text)))


class ImportanceScorer:
    """
    消息重要性打分器（无需 LLM）。

    分数 ∈ [0, 100]，由四个加权维度组成：
        recency   (40%): 在待压缩区间的位置，越新越高（指数衰减）
        role      (20%): user(意图) > assistant(动作) > tool(结果)
        signals   (25%): error/fix/decision/todo/code/路径 等内容信号
        tool_impact(15%): 写操作 > 读操作 > 无工具
    """

    def score(self, msg: Message, index: int, total: int) -> float:
        """
        给消息打分。

        参数:
            msg: 待评分消息
            index: 在待压缩区间中的位置（0=最旧）
            total: 待压缩区间消息总数
        """
        # 1. recency：index 越大（越新）分越高
        if total <= 1:
            recency = 1.0
        else:
            recency = math.exp(-0.18 * (total - 1 - index))

        # 2. role
        if msg.role == "system":
            role = 1.0
        elif msg.role == "user":
            role = 0.9
        elif msg.role == "assistant":
            role = 0.75 if msg.tool_calls else 0.55
        else:  # tool
            role = 0.3

        # 3. signals：扫描内容 + 工具调用参数
        text = msg.content or ""
        hits = 0
        for _, kws in _SIGNAL_KW.items():
            low = text.lower()
            if any(k in low for k in kws):
                hits += 1
        if _PATH_RE.search(text):
            hits += 1
        # 工具调用参数中的路径也算信号
        for tc in msg.tool_calls:
            for v in tc.arguments.values():
                if isinstance(v, str) and _PATH_RE.search(v):
                    hits += 1
                    break
        signals = min(hits / 4.0, 1.0)

        # 4. tool_impact
        if msg.tool_calls:
            names = {tc.name.lower() for tc in msg.tool_calls}
            if names & _WRITE_TOOLS:
                impact = 0.9
            elif names & _READ_TOOLS:
                impact = 0.2
            else:
                impact = 0.5
        else:
            impact = 0.5

        final = 0.40 * recency + 0.20 * role + 0.25 * signals + 0.15 * impact
        return round(final * 100, 1)


class Condenser:
    """
    压缩策略基类。

    所有具体策略继承此类并实现 condense 方法。
    """

    def condense(self, messages: list[Message]) -> list[Message]:
        """压缩消息列表。"""
        raise NotImplementedError


class BudgetCondenser(Condenser):
    """
    Token 预算驱动的压缩策略。

    流程：
        1. 划分 protected 层（所有 system 消息 + 最近 keep_recent 条非系统消息），永不丢弃。
        2. 对其余（older）消息用 ImportanceScorer 打分。
        3. 按分数从高到低贪婪保留，直到 token 预算或 max_messages 上限耗尽。
        4. 被丢弃的消息抽取关键事实 → Context Card（结构化摘要）。
        5. LLM 可选：若提供 llm_summarize_handler，把 Context Card 升级为自然语言摘要。

    两个触发维度（任一超出即压缩）：
        - target_tokens: token 预算上限
        - max_messages:  消息条数上限（防止"大量极短消息"撑爆上下文）
    """

    def __init__(
        self,
        target_tokens: int | None = None,
        keep_recent: int = 6,
        max_messages: int | None = None,
        llm_summarize_handler: Callable[[str], str] | None = None,
    ):
        self.target_tokens = target_tokens
        self.keep_recent = keep_recent
        self.max_messages = max_messages
        self._llm_summarize = llm_summarize_handler
        self._scorer = ImportanceScorer()

    def condense(self, messages: list[Message]) -> list[Message]:
        if not messages:
            return []

        total_tokens = _estimate_tokens(messages)
        msg_count = len(messages)
        target = self.target_tokens if self.target_tokens is not None else total_tokens

        over_tokens = total_tokens > target
        over_count = (
            self.max_messages is not None and msg_count > self.max_messages
        )
        # 既不超预算也不超条数 → 原样返回
        if not over_tokens and not over_count:
            return list(messages)

        # 1. 划分 protected / older
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        if len(non_system) > self.keep_recent:
            recent = non_system[-self.keep_recent:]
            older = non_system[: -self.keep_recent]
        else:
            recent = non_system
            older = []

        # 无可压缩的 older → 直接返回（已尽力）
        if not older:
            return list(messages)

        # 2. 打分并按分数降序排列
        scored = [
            (self._scorer.score(m, idx, len(older)), idx, m)
            for idx, m in enumerate(older)
        ]
        scored_desc = sorted(scored, key=lambda t: (-t[0], t[1]))

        # 3. 计算预算
        protected = system_msgs + recent
        protected_tokens = _estimate_tokens(protected)
        budget_for_older = max(0, target - protected_tokens)

        if self.max_messages is not None:
            max_older = max(0, self.max_messages - len(system_msgs) - len(recent))
        else:
            max_older = len(older)

        # 4. 贪婪保留高分消息
        kept_idx: set[int] = set()
        remaining = budget_for_older
        for _score, idx, m in scored_desc:
            if len(kept_idx) >= max_older:
                break
            mt = _estimate_tokens([m])
            # 整条能塞下才保留（不做半条截断，保持消息完整性）
            if mt <= remaining:
                kept_idx.add(idx)
                remaining -= mt
            # 否则跳过，尝试下一条更小的

        kept_older = [m for idx, m in enumerate(older) if idx in kept_idx]
        dropped = [m for idx, m in enumerate(older) if idx not in kept_idx]

        # 5. 组装结果
        result: list[Message] = list(system_msgs)
        if dropped:
            card = self._build_context_card(dropped)
            if card is not None:
                result.append(card)
        result.extend(kept_older)
        result.extend(recent)
        return result

    # ── Context Card 生成 ──────────────────────────────────────────

    def _build_context_card(self, dropped: list[Message]) -> Message | None:
        """
        从被丢弃的消息中抽取关键事实，生成结构化 Context Card。

        若配置了 LLM 摘要且成功，则用自然语言摘要 + 结构化事实；
        否则仅用结构化事实（无 LLM 降级）。
        """
        structural = self._structural_card(dropped)

        if self._llm_summarize and len(dropped) >= 3:
            try:
                history_text = "\n".join(
                    f"[{m.role}]: {(m.content or '')[:400]}"
                    for m in dropped
                    if m.content
                )
                llm_summary = self._llm_summarize(history_text)
                return Message(
                    role="system",
                    content=(
                        f"[Conversation Summary — {len(dropped)} msgs]: "
                        f"{llm_summary}\n{structural.content}"
                    ),
                )
            except Exception as e:
                logger.warning(f"LLM summarize failed: {e}, using structural card")

        return structural

    def _structural_card(self, dropped: list[Message]) -> Message:
        """无 LLM 的结构化摘要：抽取文件/工具/错误/决策/用户请求。"""
        files: set[str] = set()
        tools: list[str] = []
        errors: list[str] = []
        decisions: list[str] = []
        user_reqs: list[str] = []

        for m in dropped:
            if m.role == "user" and m.content:
                user_reqs.append(m.content.strip()[:120])

            if m.role == "assistant":
                for tc in m.tool_calls:
                    tools.append(tc.name)
                    for v in tc.arguments.values():
                        if isinstance(v, str):
                            files.update(_extract_paths(v))

            text = m.content or ""
            for line in text.splitlines():
                low = line.lower()
                if any(k in low for k in _SIGNAL_KW["error"]):
                    errors.append(line.strip()[:150])
                if any(k in low for k in _SIGNAL_KW["decision"]):
                    decisions.append(line.strip()[:150])

            # 内容中的路径
            files.update(_extract_paths(text))

        parts = [f"[Context Card — {len(dropped)} messages condensed]"]
        if user_reqs:
            parts.append("User requests: " + " | ".join(user_reqs[-3:]))
        if files:
            parts.append("Files touched: " + ", ".join(sorted(files)[:15]))
        if tools:
            parts.append("Tools used: " + ", ".join(dict.fromkeys(tools)))
        if errors:
            parts.append("Errors: " + " || ".join(errors[-3:]))
        if decisions:
            parts.append("Decisions: " + " || ".join(decisions[-3:]))

        return Message(role="system", content="\n".join(parts))
