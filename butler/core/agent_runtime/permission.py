"""
权限系统 — 三层权限 + glob 模式匹配 + auto 模式分类器。

参考架构：Claude Code 的三层权限模型 + 七种权限模式 + AST 解析。

三层权限：
    - Tier 1 (ALWAYS_ALLOW): 只读操作，安全静默执行
    - Tier 2 (REQUIRE_CONFIRM): 状态修改操作，执行前弹出权限提示
    - Tier 3 (NEVER_ALLOW): 危险操作，无论设置如何都阻止

权限模式：
    - default: 标准模式，破坏性操作需确认
    - accept_edits: 自动接受文件编辑
    - auto: ML 分类器自动批准安全操作（轻量级规则分类器）
    - bypass_permissions: 绕过所有确认（CI/CD 环境）
    - plan: 计划模式，只读

权限匹配使用 glob 模式，存储在配置文件中：
    allow: ["Read(*)", "Bash(git *)", "Bash(npm test)"]
    deny: ["Bash(rm -rf *)"]
"""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .types import PermissionLevel

logger = logging.getLogger(__name__)


class PermissionMode(str, Enum):
    """
    权限模式。

    参考 Claude Code 的七种权限模式：
        - DEFAULT: 标准模式，破坏性操作需确认
        - ACCEPT_EDITS: 自动接受文件编辑
        - AUTO: 轻量级分类器自动批准安全操作
        - BYPASS_PERMISSIONS: 绕过所有确认
        - PLAN: 计划模式，只读
        - DONT_ASK: 不询问（静默拒绝非允许操作）
    """

    DEFAULT = "default"
    ACCEPT_EDITS = "accept_edits"
    AUTO = "auto"
    BYPASS_PERMISSIONS = "bypass_permissions"
    PLAN = "plan"
    DONT_ASK = "dont_ask"


class PermissionDecision(str, Enum):
    """权限检查结果。"""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PermissionRule:
    """
    权限规则。

    格式：ToolName(pattern)
    示例：
        "Read(*)" — 允许 Read 工具的所有调用
        "Bash(git *)" — 允许 Bash 工具执行 git 开头的命令
        "Bash(rm -rf *)" — 匹配 rm -rf 开头的命令
    """

    tool_name: str
    pattern: str

    @classmethod
    def parse(cls, rule_str: str) -> PermissionRule:
        """解析规则字符串。"""
        rule_str = rule_str.strip()
        if "(" in rule_str and rule_str.endswith(")"):
            idx = rule_str.index("(")
            return cls(
                tool_name=rule_str[:idx].strip(),
                pattern=rule_str[idx + 1 : -1].strip(),
            )
        return cls(tool_name=rule_str, pattern="*")

    def matches(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """检查工具调用是否匹配此规则。"""
        if self.tool_name != tool_name:
            return False

        if self.pattern == "*":
            return True

        # 对于 Bash 工具，匹配命令内容
        if tool_name.lower() in ("bash", "shell", "powershell"):
            cmd = arguments.get("command", "")
            return fnmatch.fnmatch(cmd, self.pattern)

        # 对于文件工具，匹配文件路径
        if tool_name.lower() in ("read", "write", "edit", "multi_edit"):
            path = arguments.get("path", arguments.get("file_path", ""))
            return fnmatch.fnmatch(path, self.pattern)

        # 其他工具：匹配任意字符串参数
        for v in arguments.values():
            if isinstance(v, str) and fnmatch.fnmatch(v, self.pattern):
                return True

        return False


# ── 危险命令模式 ──────────────────────────────────────────────

_DANGER_PATTERNS = [
    "rm -rf *",
    "rm -rf /*",
    "rm -rf ~*",
    "mkfs*",
    "dd if=*of=/dev/*",
    ":(){ :|:& };:",
    "chmod -R 777 *",
    "curl * | bash",
    "wget * | bash",
    "sudo rm *",
    "> /dev/sda*",
    "shutdown *",
    "reboot *",
    "halt *",
    "init 0",
    "kill -9 *",
]

# ── 只读命令模式 ──────────────────────────────────────────────

_READONLY_PATTERNS = [
    "ls *",
    "cat *",
    "head *",
    "tail *",
    "grep *",
    "find *",
    "git status*",
    "git log*",
    "git diff*",
    "git show*",
    "git branch*",
    "pwd",
    "echo *",
    "which *",
    "whereis *",
    "wc *",
    "file *",
    "stat *",
    "ps *",
    "top *",
    "df *",
    "du *",
    "env",
    "whoami",
    "uname *",
    "python --version*",
    "node --version*",
    "npm list*",
    "pip list*",
    "pip show*",
]


@dataclass
class PermissionConfig:
    """权限系统配置。"""

    mode: PermissionMode = PermissionMode.DEFAULT
    allow_rules: list[PermissionRule] = field(default_factory=list)
    deny_rules: list[PermissionRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PermissionConfig:
        """从配置字典创建。"""
        mode_str = d.get("mode", "default")
        try:
            mode = PermissionMode(mode_str)
        except ValueError:
            mode = PermissionMode.DEFAULT

        allow = [PermissionRule.parse(r) for r in d.get("allow", [])]
        deny = [PermissionRule.parse(r) for r in d.get("deny", [])]
        return cls(mode=mode, allow_rules=allow, deny_rules=deny)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "mode": self.mode.value,
            "allow": [f"{r.tool_name}({r.pattern})" for r in self.allow_rules],
            "deny": [f"{r.tool_name}({r.pattern})" for r in self.deny_rules],
        }


class PermissionSystem:
    """
    权限系统。

    参考 Claude Code 的权限检查流程：
        1. 检查工具的 PermissionLevel（工具定义中的静态权限）
        2. 检查 deny 规则（最高优先级）
        3. 检查 allow 规则
        4. 检查权限模式（bypass / plan / auto 等）
        5. auto 模式下使用轻量级分类器判断

    使用方式::

        perm = PermissionSystem()
        perm.add_allow_rule("Read(*)")
        perm.add_deny_rule("Bash(rm -rf *)")

        decision = perm.check("Bash", {"command": "ls -la"})
        if decision == PermissionDecision.ASK:
            # 弹出确认对话框
            ...
    """

    def __init__(self, config: PermissionConfig | None = None):
        self._config = config or PermissionConfig()

    @property
    def config(self) -> PermissionConfig:
        return self._config

    @property
    def mode(self) -> PermissionMode:
        return self._config.mode

    def set_mode(self, mode: PermissionMode) -> None:
        """设置权限模式。"""
        self._config.mode = mode
        logger.info(f"Permission mode set to: {mode.value}")

    def add_allow_rule(self, rule_str: str) -> None:
        """添加允许规则。"""
        self._config.allow_rules.append(PermissionRule.parse(rule_str))

    def add_deny_rule(self, rule_str: str) -> None:
        """添加拒绝规则。"""
        self._config.deny_rules.append(PermissionRule.parse(rule_str))

    def check(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_permission_level: PermissionLevel = PermissionLevel.REQUIRE_CONFIRM,
    ) -> PermissionDecision:
        """
        检查工具调用权限。

        检查顺序（优先级从高到低）：
            1. 工具定义为 NEVER_ALLOW → 拒绝
            2. 权限模式 BYPASS_PERMISSIONS → 允许
            3. 权限模式 PLAN → 只读工具允许，其他拒绝
            4. deny 规则匹配 → 拒绝
            5. allow 规则匹配 → 允许
            6. 工具定义为 ALWAYS_ALLOW → 允许
            7. 权限模式 AUTO → 分类器判断
            8. 权限模式 ACCEPT_EDITS + 编辑工具 → 允许
            9. 默认 → 询问

        参数:
            tool_name: 工具名称
            arguments: 工具参数
            tool_permission_level: 工具定义中的静态权限层级

        返回:
            PermissionDecision: ALLOW / DENY / ASK
        """
        # 1. NEVER_ALLOW 工具永远拒绝
        if tool_permission_level == PermissionLevel.NEVER_ALLOW:
            logger.warning(f"Tool '{tool_name}' is NEVER_ALLOW, denied")
            return PermissionDecision.DENY

        # 2. BYPASS_PERMISSIONS 模式：全部允许
        if self._config.mode == PermissionMode.BYPASS_PERMISSIONS:
            return PermissionDecision.ALLOW

        # 3. PLAN 模式：只读工具允许，其他拒绝
        if self._config.mode == PermissionMode.PLAN:
            if tool_permission_level == PermissionLevel.ALWAYS_ALLOW:
                return PermissionDecision.ALLOW
            return PermissionDecision.DENY

        # 4. 检查 deny 规则
        for rule in self._config.deny_rules:
            if rule.matches(tool_name, arguments):
                logger.warning(
                    f"Tool '{tool_name}' matched deny rule: {rule.tool_name}({rule.pattern})"
                )
                return PermissionDecision.DENY

        # 5. 检查 allow 规则
        for rule in self._config.allow_rules:
            if rule.matches(tool_name, arguments):
                return PermissionDecision.ALLOW

        # 6. ALWAYS_ALLOW 工具
        if tool_permission_level == PermissionLevel.ALWAYS_ALLOW:
            return PermissionDecision.ALLOW

        # 7. AUTO 模式：分类器判断
        if self._config.mode == PermissionMode.AUTO:
            return self._classify_safety(tool_name, arguments)

        # 8. ACCEPT_EDITS 模式：编辑工具自动允许
        if self._config.mode == PermissionMode.ACCEPT_EDITS:
            if tool_name.lower() in ("write", "edit", "multi_edit"):
                return PermissionDecision.ALLOW

        # 9. DONT_ASK 模式：静默拒绝非允许操作
        if self._config.mode == PermissionMode.DONT_ASK:
            return PermissionDecision.DENY

        # 默认：询问
        return PermissionDecision.ASK

    def _classify_safety(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> PermissionDecision:
        """
        轻量级安全分类器（auto 模式）。

        参考 Claude Code 的 ML 分类器，但使用规则代替 ML 模型：
            - Bash 工具：检查命令是否匹配只读/危险模式
            - 文件工具：检查路径是否在项目目录内
            - 其他工具：默认询问
        """
        if tool_name.lower() in ("bash", "shell", "powershell"):
            cmd = arguments.get("command", "").strip()

            # 检查危险命令
            for pattern in _DANGER_PATTERNS:
                if fnmatch.fnmatch(cmd, pattern):
                    logger.warning(f"Auto-classifier: dangerous command detected: {cmd[:80]}")
                    return PermissionDecision.DENY

            # 检查只读命令
            for pattern in _READONLY_PATTERNS:
                if fnmatch.fnmatch(cmd, pattern):
                    return PermissionDecision.ALLOW

            # 未知命令：询问
            return PermissionDecision.ASK

        if tool_name.lower() in ("read", "glob", "grep", "ls"):
            return PermissionDecision.ALLOW

        if tool_name.lower() in ("write", "edit", "multi_edit"):
            # 检查路径是否在允许的项目目录内
            path = arguments.get("path", arguments.get("file_path", ""))
            if path:
                # 将相对路径解析为绝对路径后检查是否在项目目录内
                abs_path = os.path.abspath(path)
                cwd = os.getcwd()
                if abs_path.startswith(cwd):
                    return PermissionDecision.ALLOW
                # 绝对路径在项目外，需要询问
                return PermissionDecision.ASK
            return PermissionDecision.ASK

        # 其他工具：默认询问
        return PermissionDecision.ASK

    def is_read_only_command(self, command: str) -> bool:
        """检查命令是否为只读（用于 Bash 工具的 AST 分析替代）。"""
        cmd = command.strip()
        return any(fnmatch.fnmatch(cmd, p) for p in _READONLY_PATTERNS)

    def is_dangerous_command(self, command: str) -> bool:
        """检查命令是否危险。"""
        cmd = command.strip()
        return any(fnmatch.fnmatch(cmd, p) for p in _DANGER_PATTERNS)
