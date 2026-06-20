import time
from typing import List, Dict, Any

class EbbinghausEngine:
    """
    艾宾浩斯记忆引擎 (P2)
    根据遗忘曲线计算下次复习时间。
    复习周期: 1, 2, 4, 7, 15, 30, 60 天
    """
    INTERVALS = [0, 86400, 172800, 345600, 604800, 1296000, 2592000, 5184000]

    @staticmethod
    def calculate_next_review(current_stage: int, last_review_time: float) -> tuple:
        """
        计算下次复习时间
        :return: (next_stage, next_review_timestamp)
        """
        if current_stage >= len(EbbinghausEngine.INTERVALS) - 1:
            return current_stage, -1 # 已完成长期记忆

        next_stage = current_stage + 1
        next_review = last_review_time + EbbinghausEngine.INTERVALS[next_stage]
        return next_stage, next_review

    @staticmethod
    def get_due_items(memos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从备忘录列表中筛选出到期的复习项"""
        now = time.time()
        due = []
        for m in memos:
            if "#Review" in m.get("tags", []) or "#Memory" in m.get("tags", []):
                # 假设 metadata 中存储了 stage 和 last_review
                meta = m.get("metadata", {})
                next_review = meta.get("next_review", 0)
                if next_review > 0 and now >= next_review:
                    due.append(m)
        return due

ebbinghaus_engine = EbbinghausEngine()
