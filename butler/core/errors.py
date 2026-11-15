# -*- coding: utf-8 -*-
"""Butler 统一错误码规范 (BTL-xxxx)。

设计目标：每个报错 = 人话原因 + 可复制的修复命令。
错误码分段：
    BTL-1xxx  环境问题 (Python / 依赖 / 权限 / 端口)
    BTL-2xxx  配置问题 (.env / config.yaml / 密钥)
    BTL-3xxx  技能问题 (加载 / 运行 / 包)
    BTL-4xxx  硬件问题 (HAL / 外设，可优雅降级)

用法：
    from butler.core.errors import format_error
    print(format_error("BTL-2001"))
    print(format_error("BTL-1002", detail="psutil, Crypto"))
"""

from typing import Dict

# code -> (标题, 原因, 修复命令/建议)
ERROR_CATALOG: Dict[str, tuple] = {
    # ── 环境 ──
    "BTL-1001": (
        "Python 版本不受支持",
        "Butler 需要 Python 3.10 / 3.11（3.12+ 可能遇到依赖 wheel 兼容问题）。",
        "安装 Python 3.10/3.11 后重建环境: python -m package.dependency_manager install_all",
    ),
    "BTL-1002": (
        "缺少 Python 依赖包",
        "运行所需的第三方库未安装或安装不完整。",
        "python -m package.dependency_manager install_all   # 或: pip install -r requirements.txt",
    ),
    "BTL-1003": (
        "目录不可写",
        "config/ 或 data/ 目录没有写权限，无法持久化配置与记忆。",
        "chmod u+w config data   # 或将仓库移动到可写路径",
    ),
    "BTL-1004": (
        "端口被占用",
        "API 网关端口已被其他进程占用。",
        "butler start --port 5002   # 换个端口，或先停止占用进程",
    ),
    "BTL-1005": (
        "缺少系统级依赖",
        "PortAudio / Redis 等系统库缺失（语音或爬虫功能受影响）。",
        "Debian/Ubuntu: sudo apt-get install portaudio19-dev redis-server  |  macOS: brew install portaudio redis",
    ),
    # ── 配置 ──
    "BTL-2001": (
        "AI 服务连不上 / Key 无效",
        "API Key 未配置、已过期，或 API 地址不可达。",
        "butler config    # 重新配置并校验密钥（参考 docs/start/env-reference.md）",
    ),
    "BTL-2002": (
        ".env 配置缺失",
        "未找到 .env 文件或缺少所选服务商的密钥变量。",
        "cp .env.example .env && butler init   # 3 分钟配置向导",
    ),
    "BTL-2003": (
        "配置文件冲突",
        "多个配置文件定义了同一个键（如 config.yaml 与 settings.yaml），存在不一致风险。",
        "butler config check   # 查看冲突明细；以 config.yaml 为准",
    ),
    # ── 技能 ──
    "BTL-3001": (
        "技能加载失败",
        "技能的 Python 运行时导入出错（依赖缺失或代码异常）。",
        "butler skill info <技能名>   # 查看依赖要求；或重新安装该技能",
    ),
    "BTL-3002": (
        "技能不存在",
        "指定的技能名未在技能目录中注册。",
        "butler skills list   # 浏览可用技能（或查看 skills/CATALOG.md）",
    ),
    "BTL-3003": (
        "技能包损坏",
        "技能包缺少 SKILL.md / manifest.json 或结构不合法。",
        "参考 docs/SKILLS_GUIDE.md 重新创建技能；或 butler plugin remove <包名> 后重装",
    ),
    # ── 硬件 ──
    "BTL-4001": (
        "外设未连接（可忽略）",
        "USB 屏 / 红外 / 蓝牙等硬件未接入，已自动降级为纯软件模式。",
        "无需处理；接入硬件后自动恢复。",
    ),
}

_STANDARD_TIP = "💡 遇到问题随时运行: butler doctor（带「下一步建议」的一键体检）"


def format_error(code: str, detail: str = "") -> str:
    """返回标准格式的错误说明块（原因 + 修复命令）。"""
    entry = ERROR_CATALOG.get(code)
    if entry is None:
        return f"❌ [{code}] 未知错误码\n{_STANDARD_TIP}"
    title, reason, fix = entry
    lines = [
        f"❌ [{code}] {title}",
        f"   原因：{reason}",
    ]
    if detail:
        lines.append(f"   详情：{detail}")
    lines.append(f"   修复：{fix}")
    lines.append(f"   {_STANDARD_TIP}")
    return "\n".join(lines)


def all_errors() -> Dict[str, tuple]:
    return dict(ERROR_CATALOG)
