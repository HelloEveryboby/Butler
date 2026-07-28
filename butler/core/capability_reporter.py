"""
Butler 能力诊断报告器 (CapabilityReporter)。

启动时扫描各 capability 的可用性，显式报告而非静默降级。
解决 try/except ImportError 静默降级导致的行为不可见问题。
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CapabilityStatus:
    """单个能力维度的状态。"""

    name: str
    status: str  # "full" / "partial" / "absent"
    available: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def icon(self) -> str:
        return {"full": "[OK]", "partial": "[--]", "absent": "[!!]"}[self.status]


class CapabilityReporter:
    """
    扫描系统中各功能维度的依赖可用性。

    使用方式::

        reporter = CapabilityReporter()
        report = reporter.report()
        banner = reporter.format_banner()
    """

    CAPABILITIES: dict[str, list[str]] = {
        "ai": ["openai", "anthropic", "deepseek"],
        "memory_vec": ["redis", "redisvl", "zvec", "numpy"],
        "doc": ["openpyxl", "docx", "pptx", "pdfplumber", "pypdf"],
        "vision": ["cv2", "pytesseract", "PIL", "mss"],
        "voice": ["pyaudio", "pydub", "sounddevice", "pvrecorder"],
        "crypto": ["cryptography"],
        "network": ["paramiko", "websockets"],
        "crawler": ["scrapy", "selenium"],
    }

    def _check_module(self, mod_name: str) -> bool:
        try:
            importlib.import_module(mod_name)
            return True
        except ImportError:
            return False

    def report(self) -> dict[str, CapabilityStatus]:
        """扫描所有 capability，返回状态字典。"""
        result: dict[str, CapabilityStatus] = {}
        for cap_name, modules in self.CAPABILITIES.items():
            available: list[str] = []
            missing: list[str] = []
            for mod in modules:
                if self._check_module(mod):
                    available.append(mod)
                else:
                    missing.append(mod)

            if not missing:
                status = "full"
            elif available:
                status = "partial"
            else:
                status = "absent"

            result[cap_name] = CapabilityStatus(
                name=cap_name, status=status, available=available, missing=missing
            )
        return result

    def format_banner(self) -> str:
        """生成启动横幅中的 capability 诊断信息。"""
        report = self.report()
        lines = ["  Capability 诊断:"]
        for cap in report.values():
            lines.append(f"  {cap.icon} {cap.name:12s} {cap.status}")
            if cap.status == "partial" and cap.missing:
                lines.append(f"               缺失: {', '.join(cap.missing)}")
        return "\n".join(lines)

    def get_memory_backend(self) -> str:
        """
        根据可用性推荐记忆后端。

        返回值: "redis" / "zvec" / "sqlite"
        """
        report = self.report()
        vec_status = report.get("memory_vec")
        if vec_status and vec_status.status != "absent":
            if "redis" in vec_status.available and "redisvl" in vec_status.available:
                return "redis"
            if "zvec" in vec_status.available:
                return "zvec"
        return "sqlite"
