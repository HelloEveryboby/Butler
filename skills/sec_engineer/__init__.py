import shutil
import logging
from butler.core.base_skill import BaseSkill

class SecEngineerSkill(BaseSkill):
    """
    信息安全工程技能类。
    定位：安全审计专家。
    功能：擅长调用各种工具，对系统程序进行安全检测和压力测试。
    """
    def __init__(self):
        super().__init__("sec_engineer")
        self.logger = logging.getLogger("SecEngineer")

    def check_tools(self):
        """
        检查系统环境中必要的安全审计工具是否存在。
        :return: 包含工具及其存在状态的字典。
        """
        tools = ["nmap", "sqlmap"]
        results = {}
        for tool in tools:
            results[tool] = shutil.which(tool) is not None
        return results

    def handle_request(self, action, **kwargs):
        """
        统一请求处理入口。
        支持的操作:
          - check_tools: 检测安全工具链。
          - scan: 发起授权后的安全扫描。
        """
        if action == "check_tools":
            tools = self.check_tools()
            missing = [t for t, found in tools.items() if not found]
            if missing:
                return f"⚠️ 检测到缺少工具: {', '.join(missing)}。请手动安装以解锁完整安全审计功能。"
            return "✅ 所有核心安全工具 (nmap, sqlmap) 已就绪，系统处于受监控状态。"

        elif action == "scan":
            # 提取目标 (IP 或域名)
            target = kwargs.get("target") or kwargs.get("entities", {}).get("target")
            if not target:
                return "❌ 请提供扫描目标（IP 或域名）。"

            # 定义授权后的回调执行逻辑
            def start_scan(response_data):
                self.logger.info(f"授权通过，开始扫描目标: {target}")
                self.execute_dynamic_script(
                    "shell",
                    f"nmap -A {target}",
                    purpose=f"对目标 {target} 执行深度安全审计扫描"
                )

            # 发起提权请求
            self.request_permission(
                title="🛡️ 安全扫描授权请求",
                content=f"Security Skill 正在尝试使用 nmap 对目标 {target} 进行深度扫描。此操作具有攻击性，请确认是否授权。",
                on_authorized=start_scan,
                priority=3 # 高优先级
            )
            return f"⏳ 已发起针对 {target} 的扫描授权请求，请在提醒面板处理该提权事务。"

        return f"错误: SecEngineer 不支持动作 '{action}'。"

# 实例化技能
skill_instance = SecEngineerSkill()

def handle_request(action, **kwargs):
    """
    对接 Butler SkillManager 的标准入口函数。
    """
    return skill_instance.handle_request(action, **kwargs)
