# -*- coding: utf-8 -*-
"""
Dream-RSI 经验回放存储 (Experience Replay Store)

记录每一次任务尝试及其结果，供做梦引擎在「做梦」阶段回放分析，
推导策略引导（避免清单、优选策略、停止条件、替代路径）。

设计遵循 Dream-RSI 思想：
- 记录已发生的尝试与结果（成功/失败/绕行）
- 回放时无需重新执行任务，仅基于历史记录推导策略
- 推导的策略可直接作用于下一轮执行
"""
import json
import os
import time
import threading
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("dream_experience")


class ExperienceStore:
    """
    基于 JSONL 的追加式经验存储。
    每一次任务尝试记录为一条 JSON，包含意图、路径、结果与耗时。
    """

    def __init__(self, root: Optional[str] = None):
        p_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        self.root = os.path.abspath(root or os.path.join(p_root, "data", "butler_memory"))
        self.log_path = os.path.join(self.root, "experience_log.jsonl")
        os.makedirs(self.root, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, task_input: str, intent: str = "", entities: Optional[Dict] = None,
               status: str = "unknown", output_summary: str = "", error: str = "",
               turns: int = 0, path: str = "autonomous", plan: Optional[List] = None) -> str:
        """
        记录一次任务尝试。

        Args:
            task_input: 原始用户输入
            intent: 识别出的意图
            entities: 提取的实体参数
            status: success / failed / partial / unknown
            output_summary: 执行结果摘要（截断）
            error: 错误信息（如有）
            turns: 执行消耗的轮次
            path: 执行路径 (autonomous / verb / local_nlu / agent)
            plan: 规划步骤列表（如有）

        Returns:
            记录 ID
        """
        record_id = f"exp_{int(time.time() * 1000)}_{threading.get_ident() & 0xffff}"
        record = {
            "id": record_id,
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "task_input": task_input[:500],
            "intent": intent,
            "entities": entities or {},
            "status": status,
            "output_summary": output_summary[:1000],
            "error": error[:500],
            "turns": turns,
            "path": path,
            "plan": plan or [],
        }
        try:
            with self._lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"经验记录写入失败: {e}")
        return record_id

    def get_recent(self, n: int = 50) -> List[Dict[str, Any]]:
        """获取最近 n 条经验记录（倒序）。"""
        return self._read_tail(n)

    def get_failures(self, n: int = 30) -> List[Dict[str, Any]]:
        """获取最近 n 条失败记录。"""
        records = self._read_all()
        failures = [r for r in records if r.get("status") == "failed"]
        return failures[-n:]

    def get_successes(self, n: int = 30) -> List[Dict[str, Any]]:
        """获取最近 n 条成功记录。"""
        records = self._read_all()
        successes = [r for r in records if r.get("status") == "success"]
        return successes[-n:]

    def get_by_intent(self, intent: str, n: int = 20) -> List[Dict[str, Any]]:
        """按意图筛选最近 n 条记录。"""
        records = self._read_all()
        matched = [r for r in records if r.get("intent") == intent]
        return matched[-n:]

    def _read_all(self) -> List[Dict[str, Any]]:
        records = []
        if not os.path.exists(self.log_path):
            return records
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"经验日志读取失败: {e}")
        return records

    def _read_tail(self, n: int) -> List[Dict[str, Any]]:
        records = self._read_all()
        return records[-n:]

    def prune(self, max_records: int = 2000):
        """修剪经验日志，保留最近 max_records 条。"""
        records = self._read_all()
        if len(records) <= max_records:
            return
        try:
            with self._lock:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    for r in records[-max_records:]:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
            logger.info(f"经验日志已修剪，保留最近 {max_records} 条。")
        except Exception as e:
            logger.warning(f"经验日志修剪失败: {e}")


# 全局单例
experience_store = ExperienceStore()
