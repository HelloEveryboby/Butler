import os
import time
import datetime
from pathlib import Path
from package.core_utils.log_manager import LogManager
from butler.core.battery_manager import battery_manager
from butler.core.memory.memory_engine import hybrid_memory_manager

logger = LogManager.get_logger("dream_engine")

class DreamEngine:
    """
    Butler 做梦引擎 (Dream Engine)
    后台整合碎片化记忆，将其转化为结构化的持久知识 (MEMORY.md)。
    """
    def __init__(self, butler_app=None):
        self.butler = butler_app
        self.memory_dir = Path(hybrid_memory_manager.log_dir)
        self.memory_md = Path(hybrid_memory_manager.long_term_file)
        self.lock_file = self.memory_dir / ".dream_lock"
        self.max_memory_lines = 1000 # Prune 限制

    def should_dream(self):
        """
        检查是否满足做梦条件。
        """
        if not battery_manager.can_run_background_task():
            return False

        last_dream = 0
        if self.lock_file.exists():
            last_dream = self.lock_file.stat().st_mtime

        # 冷却时间 24 小时
        if time.time() - last_dream < 24 * 3600:
            return False

        return True

    def dream(self, force: bool = False):
        """执行记忆整合 + RSI 做梦，返回 RSI 报告摘要（不可用时为 None）。

        force=True 时忽略 24h 冷却（供 ``butler dream run --force`` 使用）。
        """
        if not force and not self.should_dream():
            return None

        logger.info("Butler 开始做梦 (记忆整合)...")
        try:
            # 1. 搜集信号
            signals = self._gather_signals()
            if not signals:
                logger.info("没有发现新信号，跳过记忆整合。")
                return self._self_improve()

            # 2. 整合记忆
            if self.butler and hasattr(self.butler, 'nlu_service'):
                consolidation = self._consolidate(signals)

                # 3. 写入并修剪 MEMORY.md
                self._update_and_prune_memory_md(consolidation)

                # 更新锁文件时间
                self.lock_file.touch()
                logger.info("记忆整合完成。")
            else:
                logger.warning("NLUService 不可用，无法整合记忆。")

            # 4. Dream：在发现历史的回放模拟器上做梦（探索策略自改进）
            return self._self_improve()

        except Exception as e:
            logger.error(f"做梦过程中发生错误: {e}")
            return None

    def _self_improve(self):
        """Dream 阶段：离线回放评估/修订探索策略（论文 §3 做梦）。

        与记忆整合互不依赖：历史非空即可从回放中改进策略；
        由 dream.enabled 配置开关控制。
        """
        try:
            from butler.core.dream import DreamOrchestrator
            from butler.core.dream import butler_adapter

            settings = butler_adapter.load_settings()
            if not settings.get("enabled", True):
                return None
            forest = butler_adapter.load_forest(settings)
            if len(forest) == 0:
                return None

            cfg = butler_adapter.config_from_settings(settings)
            nlu = getattr(self.butler, "nlu_service", None) if self.butler else None
            orch = DreamOrchestrator(
                attempt_fn=lambda ws: butler_adapter.AttemptResult(ws, 0.0),
                policy=butler_adapter.load_policy(settings),
                config=cfg,
                forest=forest,
                developer=butler_adapter.make_developer(nlu, seed=cfg.seed),
                state_path=butler_adapter.policy_path(settings),
            )
            report = orch.dream_phase()
            if report is not None:
                butler_adapter.save_forest(forest, settings)
                # 持久化改进后的策略，让下一次做梦从上次结果继续
                butler_adapter.save_policy(report.best_policy, settings)
                logger.info(f"[Dream] 策略自改进完成: {report.summary()}")
                return report.summary()
        except Exception as e:
            logger.warning(f"[Dream] 做梦阶段失败: {e}")
        return None

    def _gather_signals(self):
        """搜集最近 3 天的日志"""
        signals = []
        for i in range(3):
            date_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            log_path = self.memory_dir / f"{date_str}.md"
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    signals.append(f"--- {date_str} ---\n" + f.read())
        return "\n".join(signals)

    def _consolidate(self, signals):
        """使用 LLM 整合信号"""
        prompt = (
            "你正在执行 Butler 的 '做梦' (Dream) 任务，即记忆整合。\n"
            "以下是最近几天的交互日志。请提取关键信息（用户的偏好、重要的事实、待办事项、已完成的里程碑），"
            "并将其整理成简洁的、结构化的知识点。\n\n"
            "日志内容：\n" + signals + "\n\n"
            "要求：\n"
            "1. 只要最核心的知识点。\n"
            "2. 使用 Markdown 列表格式。\n"
            "3. 如果有重复的信息，请合并。\n"
            "4. 保持语言简洁（中文）。"
        )
        response = self.butler.nlu_service.ask_llm(prompt, [])
        return response

    def _update_and_prune_memory_md(self, new_knowledge):
        """更新并修剪 MEMORY.md 文件"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = f"\n\n## 记忆整合 ({timestamp})\n"

        content = ""
        if self.memory_md.exists():
            with open(self.memory_md, 'r', encoding='utf-8') as f:
                content = f.read()

        # 合并新旧内容
        full_content = content + header + new_knowledge

        # Prune 逻辑：保持文件行数在限制内
        lines = full_content.splitlines()
        if len(lines) > self.max_memory_lines:
            logger.info(f"MEMORY.md 超过 {self.max_memory_lines} 行，正在修剪...")
            # 保留前面的 Header (如有) 和最后的 800 行
            lines = lines[-self.max_memory_lines:]
            full_content = "\n".join(lines)

        with open(self.memory_md, 'w', encoding='utf-8') as f:
            f.write(full_content)

# 单例将在应用初始化时创建
