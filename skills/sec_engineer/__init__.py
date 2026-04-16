import shutil
from butler.core.base_skill import BaseSkill

class SecEngineerSkill(BaseSkill):
    def __init__(self):
        super().__init__("sec_engineer")

    def check_tools(self):
        tools = ["nmap", "sqlmap"]
        results = {}
        for tool in tools:
            results[tool] = shutil.which(tool) is not None
        return results

    def handle_request(self, action, **kwargs):
        if action == "check_tools":
            tools = self.check_tools()
            missing = [t for t, found in tools.items() if not found]
            if missing:
                return f"检测到缺少工具: {', '.join(missing)}。请手动安装以解锁完整功能。"
            return "所有安全工具 (nmap, sqlmap) 已就绪。"

        elif action == "scan":
            target = kwargs.get("target") or kwargs.get("entities", {}).get("target")
            if not target:
                return "请提供扫描目标（IP 或域名）。"

            # 模拟提权请求逻辑
            def start_scan(response_data):
                self.execute_dynamic_script("shell", f"nmap -A {target}", purpose=f"Security scan on {target}")

            self.request_permission(
                title="安全扫描授权",
                content=f"Security Skill 请求授权对目标 {target} 进行深度安全扫描。",
                on_authorized=start_scan
            )
            return f"已发起针对 {target} 的扫描授权请求，请在提醒面板确认。"

        return f"SecEngineer 不支持动作: {action}"

# 符合 SkillManager 的加载约定
skill_instance = SecEngineerSkill()

def handle_request(action, **kwargs):
    return skill_instance.handle_request(action, **kwargs)
