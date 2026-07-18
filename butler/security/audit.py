# -*- coding: utf-8 -*-
import datetime
from pathlib import Path

class SecurityAuditor:
    """
    负责系统运行期内的安全审计，记录用户和数字员工之间的敏感操作（例如权限验证与人工授权结果）。
    """
    def __init__(self, audit_file_path: str = None):
        if audit_file_path is None:
            current_dir = Path(__file__).resolve().parent
            self.audit_file_path = current_dir.parent / "data" / "security_audit.log"
        else:
            self.audit_file_path = Path(audit_file_path)

    def log_action_permission(self, agent_name: str, action: str, permission_status: str = "approved") -> str:
        """
        生成并追加一条标准格式的安全审计和人工授权检查记录。
        """
        self.audit_file_path.parent.mkdir(parents=True, exist_ok=True)

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"[{now_str}]\n"
            f"Agent: {agent_name}\n"
            f"Action: {action}\n"
            f"Permission: {permission_status}\n"
            f"{'-'*30}\n"
        )

        with open(self.audit_file_path, "a", encoding="utf-8") as f:
            f.write(entry)

        return entry

    def read_audit_logs(self) -> str:
        if not self.audit_file_path.exists():
            return "暂无安全审计日志。"
        return self.audit_file_path.read_text(encoding="utf-8")
