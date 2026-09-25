# -*- coding: utf-8 -*-
"""动词识别引擎 —— 把自然语言的动词/宾语精确归一到规范意图。

解决的问题: "记录当前画面 / 记录当前眼前画面 / 截个屏 / 屏幕留个档" 是同一个动作,
但字面完全不同。本引擎用**同义词典(规则) + 示例句(语义)双通道**归一:

    输入: "记录当前眼前画面"
    输出: VerbMatch(intent_id='screen.capture', confidence=1.0,
                    channel='mixed', slots={'scope': 'fullscreen'})

流水线: 分句/复合句拆分 → 填充词归一 → 双通道匹配打分 → 槽位抽取 → 置信度分级
  confidence >= 0.85 → 直接执行 (need_confirm=False)
  0.60 ~ 0.85        → 执行但破坏性操作需确认 (need_confirm=True)
  < 0.60             → 无匹配, 交上层(既有 NLU / LLM)兜底

词典: butler/core/intents/verb_lexicon.yaml (数据驱动, 加词不加代码)。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from butler.core.algorithms import char_ngram_cosine

logger = logging.getLogger("VerbEngine")

DEFAULT_LEXICON_PATH = Path(__file__).resolve().parent / "intents" / "verb_lexicon.yaml"

# 口语填充词: 匹配前剔除（"帮我截一下屏幕" → "截屏幕"）
FILLER_RE = re.compile(r"(帮我|请您|请|麻烦|劳烦|来帮忙|一下|一哈)")
# 动宾间插入语: "截个屏" → "截屏"（仅动词后、宾语前）
INTERFIX_RE = re.compile(r"(?<=[截拍录存留抓])(?:个|一下)(?=[屏图画面像档])")
# 复合句拆分: 标点 + 连接词
SPLIT_RE = re.compile(r"[，,。；;！!？?\n]+|(?:然后|接着|之后|随后|并且|同时|顺手)")

PATH_RE = re.compile(r"(/[a-zA-Z0-9._/\-]+|[a-zA-Z]:\\[a-zA-Z0-9._\\\-]+)")
QUOTED_RE = re.compile(r"[\"'“”‘’『』「」]([^\"'“”‘’『』「」]{1,60})[\"'“”‘’『』「」]")
TARGET_RE = re.compile(r"(?:到|至|进|入)\s*([^\s，,。；;！!？?]+)")
SOURCE_RE = re.compile(r"从\s*([^\s，,。；;！!？?]+)")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

CONFIDENCE_AUTO = 0.85   # 直接执行
CONFIDENCE_ASK = 0.60    # 执行但需确认 / 作为建议
SEMANTIC_FLOOR = 0.35    # 语义通道低于此分视为未命中


@dataclass
class VerbMatch:
    """一次动词识别的结果。"""
    intent_id: str
    confidence: float
    channel: str                      # 'rule' | 'semantic' | 'mixed'
    slots: Dict[str, Any] = field(default_factory=dict)
    text: str = ""

    @property
    def need_confirm(self) -> bool:
        return self.confidence < CONFIDENCE_AUTO


class VerbEngine:
    """同义词归一 + 意图匹配 + 槽位抽取。单例见模块底部 ``verb_engine``。"""

    def __init__(self, lexicon_path: Optional[Path] = None):
        path = Path(lexicon_path or DEFAULT_LEXICON_PATH)
        with open(path, "r", encoding="utf-8") as f:
            self.lexicon: Dict[str, Any] = yaml.safe_load(f) or {}
        self.actions: Dict[str, Dict[str, Any]] = self.lexicon.get("actions", {})
        self.scopes: Dict[str, List[str]] = self.lexicon.get("scopes", {})
        if not self.actions:
            raise ValueError(f"动词词典为空或格式错误: {path}")

    # ---------- 对外入口 ----------

    def parse(self, text: str) -> List[VerbMatch]:
        """识别一句话（可含复合指令），按出现顺序返回意图列表。"""
        text = (text or "").strip()
        if not text:
            return []
        results: List[VerbMatch] = []
        for seg in self.split_segments(text):
            match = self._match_segment(seg)
            if match is not None:
                results.append(match)
        return results

    def split_segments(self, text: str) -> List[str]:
        """复合句拆分（标点 + 连接词），返回非空子句列表。"""
        return [seg.strip() for seg in SPLIT_RE.split(text or "") if seg.strip()]

    def explain(self, text: str) -> List[Dict[str, Any]]:
        """评测/调试用: 返回可读的匹配细节。"""
        return [
            {
                "text": m.text,
                "intent": m.intent_id,
                "confidence": round(m.confidence, 3),
                "channel": m.channel,
                "slots": m.slots,
                "need_confirm": m.need_confirm,
            }
            for m in self.parse(text)
        ]

    # ---------- 内部: 匹配 ----------

    @staticmethod
    def _normalize(seg: str) -> str:
        s = FILLER_RE.sub("", seg)
        s = INTERFIX_RE.sub("", s)
        return re.sub(r"\s+", "", s)

    def _match_segment(self, seg: str) -> Optional[VerbMatch]:
        norm = self._normalize(seg)
        rule = self._rule_match(norm)          # (intent_id, score, verb, obj) | None
        sem = self._semantic_match(norm)       # (intent_id, score) | None

        intent_id: Optional[str] = None
        confidence = 0.0
        channel = "rule"

        if rule and sem:
            rule_id, rule_score, _, _ = rule
            sem_id, sem_score = sem
            if rule_id == sem_id:
                intent_id, channel = rule_id, "mixed"
                confidence = min(0.99, max(rule_score, sem_score) + 0.05)
            elif rule_score >= sem_score:
                intent_id, channel = rule_id, "rule"
                confidence = rule_score * 0.95
            else:
                intent_id, channel = sem_id, "semantic"
                confidence = sem_score * 0.90
        elif rule:
            intent_id, confidence, _, _ = rule
            channel = "rule"
        elif sem:
            intent_id, confidence = sem
            channel = "semantic"
        else:
            return None

        if confidence < CONFIDENCE_ASK:
            return None

        slots = self._extract_slots(seg, norm, intent_id)
        return VerbMatch(
            intent_id=intent_id,
            confidence=round(confidence, 4),
            channel=channel,
            slots=slots,
            text=seg,
        )

    def _rule_match(self, norm: str) -> Optional[Tuple[str, float, str, str]]:
        """规则通道: 动词 0.55 + 宾语 0.45 (+范围词补充 0.3)，取最高分。"""
        scope_hit = any(w in norm for words in self.scopes.values() for w in words)
        best: Optional[Tuple[str, float, str, str]] = None
        best_key = (-1.0, -1)  # (score, matched-token-length)
        for action_id, spec in self.actions.items():
            verb = self._longest_hit(spec.get("verbs", []), norm)
            obj = self._longest_hit(spec.get("objects", []), norm)
            if not verb and not obj:
                continue
            score = (0.55 if verb else 0.0) + (0.45 if obj else 0.0)
            # “截取指定区域/记录当前窗口”：动词+范围词即完整语义
            if verb and scope_hit and action_id == "screen.capture":
                score = min(1.0, score + 0.3)
            key = (score, len(verb or "") + len(obj or ""))
            if key > best_key:
                best_key = key
                best = (action_id, score, verb or "", obj or "")
        return best

    def _semantic_match(self, norm: str) -> Optional[Tuple[str, float]]:
        """语义通道: 与示例句的最大字符余弦相似度。"""
        best_id: Optional[str] = None
        best_score = -1.0
        for action_id, spec in self.actions.items():
            for example in spec.get("examples", []):
                score = char_ngram_cosine(norm, self._normalize(str(example)))
                if score > best_score:
                    best_score = score
                    best_id = action_id
        if best_id is None or best_score < SEMANTIC_FLOOR:
            return None
        return best_id, best_score

    @staticmethod
    def _longest_hit(words: List[str], norm: str) -> Optional[str]:
        """返回命中 norm 的最长同义词（长词更具体，优先）。"""
        hits = [w for w in words if w and str(w) in norm]
        return max(hits, key=len) if hits else None

    # ---------- 内部: 槽位 ----------

    def _extract_slots(self, seg: str, norm: str, intent_id: str) -> Dict[str, Any]:
        slots: Dict[str, Any] = {}

        # 范围 (screen.capture): 全屏/区域/窗口，缺省全屏
        for scope, words in self.scopes.items():
            if any(w in norm for w in words):
                slots["scope"] = scope
                break
        if intent_id == "screen.capture":
            slots.setdefault("scope", "fullscreen")

        # 路径 / 目标 / 来源
        path = PATH_RE.search(seg)
        if path:
            slots["path"] = path.group(1)
        src = SOURCE_RE.search(seg)
        if src:
            slots["source"] = src.group(1).strip()
        dst = TARGET_RE.search(seg)
        if dst:
            slots["target"] = dst.group(1).strip()

        # 引号内容 → 新名字 / 写入内容 / 话题查询
        quoted = QUOTED_RE.search(seg)
        if quoted:
            value = quoted.group(1).strip()
            if intent_id == "file.rename":
                slots["name"] = value
            elif intent_id == "textfile.edit":
                slots["content"] = value
            elif intent_id.startswith("topic."):
                slots["query"] = value
            else:
                slots.setdefault("name", value)

        # 话题查询回退: 去掉动作词后剩余部分
        if intent_id.startswith("topic.") and "query" not in slots:
            residue = seg
            for w in self.actions[intent_id].get("verbs", []):
                residue = residue.replace(str(w), "")
            for w in self.actions[intent_id].get("objects", []):
                residue = residue.replace(str(w), "")
            residue = re.sub(r"[的了啊吧呢是这个那些个\s]", "", residue)
            if residue:
                slots["query"] = residue[:24]

        nums = NUMBER_RE.findall(seg)
        if nums:
            slots["numbers"] = [float(n) for n in nums]
        return slots


# 全局单例
verb_engine = VerbEngine()
