import time
import random
from package.core_utils.log_manager import LogManager
from butler.core.battery_manager import battery_manager
from butler.core.event_bus import event_bus

logger = LogManager.get_logger("proactive_agent")

class ProactiveAgent:
    """
    Butler 主动代理 (Proactive Agent)
    在无人值守时主动检查系统状态或提供建议。
    """
    def __init__(self, jarvis_app=None):
        self.jarvis = jarvis_app
        self.last_activity = time.time()
        self.is_active = True

    def update_activity(self):
        """当有用户输入时更新活跃时间"""
        self.last_activity = time.time()

    def tick(self):
        """
        主动检查逻辑。由 CronScheduler 定期触发。
        """
        if not self.is_active: return

        # 使用 refined 的背景任务检查逻辑
        if not battery_manager.can_run_background_task():
            return

        idle_time = time.time() - self.last_activity

        # 只有在空闲超过 2 小时后才可能触发主动行为
        if idle_time > 2 * 3600:
            self._take_initiative()

    def _take_initiative(self):
        """采取主动行动"""
        logger.info("ProactiveAgent 正在采取主动行动...")

        # 随机选择一个主动任务
        tasks = [
            self._check_system_health,
            self._summarize_day,
            self._suggest_improvement
        ]
        task = random.choice(tasks)
        task()

    def _check_system_health(self):
        """检查系统健康度（静默执行）"""
        try:
            from package.core_utils.health_monitor import HealthMonitor
            monitor = HealthMonitor()
            monitor.run_self_healing()
            logger.info("已完成静默系统健康检查。")
        except Exception as e:
            logger.error(f"健康检查失败: {e}")

    def _summarize_day(self):
        """如果到了傍晚，尝试总结今日"""
        now = time.localtime()
        if 18 <= now.tm_hour <= 22:
             logger.info("正在生成今日工作总结...")
             # 确保 jarvis 和 long_memory 已初始化
             if self.jarvis and hasattr(self.jarvis, 'long_memory'):
                 self.jarvis.long_memory.logs.add_daily_log("[Proactive] 自动回顾：系统今日运行平稳，记忆已准备好在凌晨整合。")
             else:
                 logger.warning("Jarvis LongMemory 尚未就绪，跳过总结。")

    def _suggest_improvement(self):
        """基于历史记录建议改进（极其低频）"""
        logger.info("正在思考潜在的系统改进建议...")
        if not self.jarvis: return

        habit_summary = self.jarvis.habit_manager.get_profile_summary()
        prompt = (
            f"基于以下用户的习惯画像，请主动提供一条改进建议或一个自动化的新点子：\n"
            f"{habit_summary}\n\n"
            f"建议应具有前瞻性（例如：'检测到您常在 9 点处理周报，是否需要我为您预先汇总本周日志？'）。"
        )

        try:
            suggestion = self.jarvis.nlu_service.ask_llm(prompt, use_habit=False)
            self.jarvis.ui_print(f"💡 主动建议: {suggestion}", tag='system_message')
            event_bus.emit("proactive_suggestion", suggestion)
        except Exception as e:
            logger.error(f"Failed to generate proactive suggestion: {e}")
