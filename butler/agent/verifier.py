# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Verifier:
    """
    负责对步骤执行结果、或整个任务规划树的完整执行结果进行自动审查校验。
    """
    def verify_step(self, step: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        验证单个步骤的执行产出是否合法且状态无异常。
        """
        status = result.get("status")
        if status == "failed":
            logger.warning(f"结果校验失败: 步骤 '{step.get('action')}' 返回了失败状态。")
            return False

        if "result" in result and result["result"] is None:
            logger.warning(f"结果校验失败: 步骤 '{step.get('action')}' 执行产出为空（None）。")
            return False

        logger.info(f"结果校验通过: 步骤 '{step.get('action')}' 校验成功。")
        return True

    def verify_overall(self, results: Dict[str, Any]) -> bool:
        """
        对整个运行任务结果集进行全局多维度核对。
        """
        if not results:
            return False
        return all(r.get("status") == "success" for r in results.values())
