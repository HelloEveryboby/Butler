from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader

logger = LogManager.get_logger(__name__)

class QuotaManager:
    """
    API Token 额度管理器 (基于金额/Token 消耗)。
    负责监控、记录和拦截超出的 API 消耗。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QuotaManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """从配置加载额度设置。"""
        # limit: 总额度 (单位：元/RMB)
        self.limit = float(config_loader.get("api.quota.limit", 100.0))
        # consumed: 已消耗金额 (单位：元/RMB)
        self.consumed = float(config_loader.get("api.quota.consumed", 0.0))
        # token_rate: 每 1M (1,000,000) Tokens 的价格 (单位：元/RMB)
        self.token_rate = float(config_loader.get("api.quota.token_rate", 2.0))

        self.enabled = config_loader.get("api.quota.enabled", True)
        self.halt_system = config_loader.get("api.quota.halt_system", True)

    def check_quota(self) -> bool:
        """检查余额是否允许继续执行。"""
        if not self.enabled:
            return True

        # 重新加载以确保获取最新数据
        self.consumed = float(config_loader.get("api.quota.consumed", 0.0))
        self.limit = float(config_loader.get("api.quota.limit", 100.0))

        return self.consumed < self.limit

    def update_usage(self, tokens: int):
        """根据使用的 Token 数量更新消耗金额。"""
        # 计算本次消耗金额: (tokens / 1,000,000) * self.token_rate
        cost = (tokens / 1000000.0) * self.token_rate

        current_consumed = float(config_loader.get("api.quota.consumed", 0.0))
        new_consumed = current_consumed + cost

        # 更新配置
        config_loader.save({
            "api": {
                "quota": {
                    "consumed": new_consumed
                }
            }
        })

        self.consumed = new_consumed
        logger.info(f"API 余额更新: 已用 {new_consumed:.4f} 元 / 限额 {self.limit:.2f} 元 (本次消耗 {tokens} tokens, 约 {cost:.6f} 元)")

    def reset_usage(self):
        """重置已消耗金额。"""
        config_loader.save({
            "api": {
                "quota": {
                    "consumed": 0.0
                }
            }
        })

        self.consumed = 0.0
        logger.info("API 消耗额度已重置。")

    def get_usage_report(self) -> dict:
        """获取当前额度使用报告。"""
        self.limit = float(config_loader.get("api.quota.limit", 100.0))
        self.consumed = float(config_loader.get("api.quota.consumed", 0.0))

        return {
            "limit": self.limit,
            "consumed": round(self.consumed, 4),
            "remaining": round(max(0, self.limit - self.consumed), 4),
            "percent": round((self.consumed / self.limit * 100), 2) if self.limit > 0 else 100.0,
            "exceeded": self.consumed >= self.limit,
            "unit": "RMB",
            "halt_system": self.halt_system
        }

# 单例实例
quota_manager = QuotaManager()
