"""
Binary Cleaner — 扫描引擎
扫描项目和系统中不必要的二进制文件、构建产物、编译缓存。
"""

import os
import re
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """单个扫描命中"""
    path: str
    category: str        # python_build / node_build / cpp_build / ...
    reason: str          # 为什么标记为不必要
    size_bytes: int = 0
    is_dir: bool = False
    risk: str = "low"    # low / medium / high
    modified_at: float = 0


@dataclass
class ScanReport:
    """扫描报告"""
    scan_path: str = ""
    scan_time: float = 0
    total_files: int = 0
    total_size_bytes: int = 0
    categories: dict = field(default_factory=dict)  # category -> {count, size}
    results: list = field(default_factory=list)      # list[ScanResult]

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 ** 2)

    @property
    def total_size_gb(self) -> float:
        return self.total_size_bytes / (1024 ** 3)

    def summary(self) -> str:
        lines = [
            f"扫描路径: {self.scan_path}",
            f"扫描时间: {self.scan_time:.1f}s",
            f"发现: {self.total_files} 个不必要文件/目录",
            f"总大小: {self.total_size_mb:.1f} MB ({self.total_size_gb:.2f} GB)",
            "",
            "按类别:",
        ]
        for cat, info in sorted(self.categories.items(), key=lambda x: -x[1]["size"]):
            size_mb = info["size"] / (1024 ** 2)
            lines.append(f"  {cat:<20} {info['count']:>6} 个  {size_mb:>8.1f} MB")
        return "\n".join(lines)


class BinaryScanner:
    """二进制文件扫描器"""

    # ── 排除目录（绝对不扫描） ──
    EXCLUDE_DIRS = {
        ".git", ".svn", ".hg",
        "/proc", "/sys", "/dev", "/run",
        "/usr", "/lib", "/lib64", "/bin", "/sbin",
        "node_modules",  # 整个 node_modules 不扫，只扫其子缓存
    }

    # ── 系统级共享库路径（不标记为不必要） ──
    SYSTEM_LIB_PATHS = {
        "/usr/lib", "/usr/lib64", "/usr/local/lib",
        "/lib", "/lib64",
        "/System/Library",  # macOS
        "C:\\Windows\\System32", "C:\\Windows\\SysWOW64",
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._rules = self._build_rules()

    def _build_rules(self) -> list[dict]:
        """构建扫描规则"""
        return [
            # ── Python 构建产物 ──
            {
                "category": "python_build",
                "name": "__pycache__ 目录",
                "type": "dir",
                "pattern": "__pycache__",
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": ".pyc 编译文件",
                "type": "file_ext",
                "extensions": [".pyc", ".pyo", ".pyd"],
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": "setuptools/build 产物",
                "type": "dir",
                "pattern": "build",
                "parent_check": "has_setup_py",
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": "dist 产物",
                "type": "dir",
                "pattern": "dist",
                "parent_check": "has_setup_py_or_pyproject",
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": "egg-info",
                "type": "dir_pattern",
                "pattern": "*.egg-info",
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": ".eggs",
                "type": "dir",
                "pattern": ".eggs",
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": "mypy 缓存",
                "type": "dir",
                "pattern": ".mypy_cache",
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": "pytest 缓存",
                "type": "dir",
                "pattern": ".pytest_cache",
                "risk": "low",
            },
            {
                "category": "python_build",
                "name": "ruff 缓存",
                "type": "dir",
                "pattern": ".ruff_cache",
                "risk": "low",
            },

            # ── Node.js 构建产物 ──
            {
                "category": "node_build",
                "name": ".next 构建",
                "type": "dir",
                "pattern": ".next",
                "risk": "low",
            },
            {
                "category": "node_build",
                "name": ".nuxt 构建",
                "type": "dir",
                "pattern": ".nuxt",
                "risk": "low",
            },
            {
                "category": "node_build",
                "name": "dist 输出",
                "type": "dir",
                "pattern": "dist",
                "parent_check": "has_package_json",
                "risk": "low",
            },
            {
                "category": "node_build",
                "name": "node_modules 缓存",
                "type": "dir",
                "pattern": ".cache",
                "parent_in": "node_modules",
                "risk": "low",
            },
            {
                "category": "node_build",
                "name": ".parcel-cache",
                "type": "dir",
                "pattern": ".parcel-cache",
                "risk": "low",
            },
            {
                "category": "node_build",
                "name": ".turbo",
                "type": "dir",
                "pattern": ".turbo",
                "risk": "low",
            },

            # ── C/C++ 编译产物 ──
            {
                "category": "cpp_build",
                "name": "目标文件 (.o)",
                "type": "file_ext",
                "extensions": [".o", ".obj"],
                "risk": "low",
            },
            {
                "category": "cpp_build",
                "name": "静态库 (.a)",
                "type": "file_ext",
                "extensions": [".a"],
                "risk": "medium",
                "exclude_system": True,
            },
            {
                "category": "cpp_build",
                "name": "CMake 构建目录",
                "type": "dir",
                "pattern": "build",
                "parent_check": "has_cmake",
                "risk": "low",
            },
            {
                "category": "cpp_build",
                "name": "CMake 缓存",
                "type": "dir",
                "pattern": "CMakeFiles",
                "risk": "low",
            },
            {
                "category": "cpp_build",
                "name": "CMakeCache",
                "type": "file",
                "pattern": "CMakeCache.txt",
                "risk": "low",
            },

            # ── Rust 构建产物 ──
            {
                "category": "rust_build",
                "name": "Cargo target 目录",
                "type": "dir",
                "pattern": "target",
                "parent_check": "has_cargo_toml",
                "risk": "medium",
            },

            # ── Go 构建产物 ──
            {
                "category": "go_build",
                "name": "Go 编译二进制",
                "type": "dir",
                "pattern": "bin",
                "parent_check": "has_go_mod",
                "risk": "medium",
            },

            # ── Java 构建产物 ──
            {
                "category": "java_build",
                "name": ".class 文件",
                "type": "file_ext",
                "extensions": [".class"],
                "risk": "low",
            },
            {
                "category": "java_build",
                "name": "Gradle 构建",
                "type": "dir",
                "pattern": "build",
                "parent_check": "has_gradle",
                "risk": "low",
            },
            {
                "category": "java_build",
                "name": "Gradle 缓存",
                "type": "dir",
                "pattern": ".gradle",
                "risk": "low",
            },
            {
                "category": "java_build",
                "name": "Maven target",
                "type": "dir",
                "pattern": "target",
                "parent_check": "has_pom_xml",
                "risk": "low",
            },

            # ── IDE 缓存 ──
            {
                "category": "ide_cache",
                "name": "IDEA 缓存",
                "type": "dir",
                "pattern": ".idea",
                "sub_path": "caches",
                "risk": "low",
            },
            {
                "category": "ide_cache",
                "name": "VS Code 缓存",
                "type": "dir",
                "pattern": ".vscode",
                "sub_path": "Cache",
                "risk": "low",
            },

            # ── 通用构建产物 ──
            {
                "category": "general_build",
                "name": "core dump 文件",
                "type": "file_pattern",
                "pattern": "core.*",
                "regex": r"^core(\.\d+)?$",
                "risk": "low",
            },
            {
                "category": "general_build",
                "name": "临时可执行文件",
                "type": "file_ext",
                "extensions": [".tmp.exe", ".temp"],
                "risk": "low",
            },
        ]

    # ══════════════════════════════════════════
    # 扫描主入口
    # ══════════════════════════════════════════

    def scan(self, path: str, categories: list[str] = None,
             max_depth: int = 10) -> ScanReport:
        """
        扫描指定路径。
        :param path: 扫描根目录
        :param categories: 限定类别（None=全部）
        :param max_depth: 最大递归深度
        :return: ScanReport
        """
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"路径不存在: {path}")

        start_time = time.time()
        report = ScanReport(scan_path=path)

        # 过滤规则
        rules = self._rules
        if categories:
            rules = [r for r in rules if r["category"] in categories]

        logger.info(f"🔍 扫描 {path} (深度: {max_depth}, 类别: {len(rules)})")

        for root, dirs, files in os.walk(path, topdown=True):
            # 深度控制
            depth = root.replace(path, "").count(os.sep)
            if depth > max_depth:
                dirs.clear()
                continue

            # 排除目录
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]

            for rule in rules:
                # 扫描目录名
                if rule["type"] in ("dir", "dir_pattern"):
                    for d in list(dirs):
                        if self._match_dir(d, rule):
                            dir_path = os.path.join(root, d)
                            if self._check_parent(root, rule) and self._check_not_system(dir_path):
                                result = self._make_result(dir_path, rule)
                                if result:
                                    report.results.append(result)
                                    dirs.remove(d)  # 不再递归

                # 扫描文件
                if rule["type"] in ("file_ext", "file", "file_pattern"):
                    for f in files:
                        if self._match_file(f, rule):
                            file_path = os.path.join(root, f)
                            if self._check_not_system(file_path):
                                result = self._make_result(file_path, rule)
                                if result:
                                    report.results.append(result)

        # 统计
        report.scan_time = time.time() - start_time
        for r in report.results:
            report.total_files += 1
            report.total_size_bytes += r.size_bytes
            if r.category not in report.categories:
                report.categories[r.category] = {"count": 0, "size": 0}
            report.categories[r.category]["count"] += 1
            report.categories[r.category]["size"] += r.size_bytes

        logger.info(f"  ✅ 扫描完成: {report.total_files} 个, "
                     f"{report.total_size_mb:.1f} MB")
        return report

    def scan_home(self) -> ScanReport:
        """快速扫描 home 目录"""
        return self.scan(os.path.expanduser("~"), max_depth=5)

    def scan_project(self, path: str) -> ScanReport:
        """深度扫描单个项目"""
        return self.scan(path, max_depth=15)

    # ══════════════════════════════════════════
    # 匹配逻辑
    # ══════════════════════════════════════════

    def _match_dir(self, dirname: str, rule: dict) -> bool:
        if rule["type"] == "dir":
            return dirname == rule["pattern"]
        if rule["type"] == "dir_pattern":
            # glob 风格匹配
            pattern = rule["pattern"].replace("*", "")
            return dirname.startswith(pattern) or dirname == rule["pattern"].rstrip("*")
        return False

    def _match_file(self, filename: str, rule: dict) -> bool:
        if rule["type"] == "file_ext":
            return any(filename.endswith(ext) for ext in rule["extensions"])
        if rule["type"] == "file":
            return filename == rule["pattern"]
        if rule["type"] == "file_pattern":
            regex = rule.get("regex")
            if regex:
                return bool(re.match(regex, filename))
            return filename.startswith(rule["pattern"].replace("*", ""))
        return False

    def _check_parent(self, parent_dir: str, rule: dict) -> bool:
        """检查父目录条件"""
        check = rule.get("parent_check")
        if not check:
            return True

        if check == "has_setup_py":
            return os.path.isfile(os.path.join(parent_dir, "setup.py"))
        if check == "has_setup_py_or_pyproject":
            return (os.path.isfile(os.path.join(parent_dir, "setup.py")) or
                    os.path.isfile(os.path.join(parent_dir, "pyproject.toml")))
        if check == "has_package_json":
            return os.path.isfile(os.path.join(parent_dir, "package.json"))
        if check == "has_cmake":
            return (os.path.isfile(os.path.join(parent_dir, "CMakeLists.txt")) or
                    os.path.isfile(os.path.join(parent_dir, "Makefile")))
        if check == "has_cargo_toml":
            return os.path.isfile(os.path.join(parent_dir, "Cargo.toml"))
        if check == "has_go_mod":
            return os.path.isfile(os.path.join(parent_dir, "go.mod"))
        if check == "has_gradle":
            return (os.path.isfile(os.path.join(parent_dir, "build.gradle")) or
                    os.path.isfile(os.path.join(parent_dir, "build.gradle.kts")))
        if check == "has_pom_xml":
            return os.path.isfile(os.path.join(parent_dir, "pom.xml"))

        return True

    def _check_not_system(self, path: str) -> bool:
        """确保不是系统级文件"""
        for sys_path in self.SYSTEM_LIB_PATHS:
            if path.startswith(sys_path):
                return False
        return True

    def _make_result(self, path: str, rule: dict) -> ScanResult | None:
        """创建扫描结果"""
        try:
            stat = os.stat(path)
            is_dir = os.path.isdir(path)
            size = 0

            if is_dir:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        try:
                            size += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
            else:
                size = stat.st_size

            return ScanResult(
                path=path,
                category=rule["category"],
                reason=rule["name"],
                size_bytes=size,
                is_dir=is_dir,
                risk=rule.get("risk", "low"),
                modified_at=stat.st_mtime,
            )
        except (OSError, PermissionError):
            return None


class BinaryCleaner:
    """二进制文件清理器"""

    def __init__(self):
        self.deleted: list[ScanResult] = []
        self.failed: list[tuple[ScanResult, str]] = []

    def clean(self, report: ScanReport, dry_run: bool = True,
              categories: list[str] = None,
              confirm_callback=None) -> dict:
        """
        清理扫描报告中的文件。
        :param report: ScanReport 扫描结果
        :param dry_run: True=仅模拟，不实际删除
        :param categories: 限定清理的类别
        :param confirm_callback: 高风险确认回调 callback(result) -> bool
        :return: 清理统计
        """
        self.deleted = []
        self.failed = []

        targets = report.results
        if categories:
            targets = [r for r in targets if r.category in categories]

        logger.info(f"{'🔍 模拟清理' if dry_run else '🗑️ 实际清理'}: "
                     f"{len(targets)} 个目标")

        for result in targets:
            # 高风险需要确认
            if result.risk == "high" and confirm_callback:
                if not confirm_callback(result):
                    logger.info(f"  ⏭️ 跳过 (用户取消): {result.path}")
                    continue

            try:
                if dry_run:
                    logger.info(f"  [dry-run] 将删除: {result.path} "
                                f"({result.size_bytes / 1024:.0f} KB)")
                    self.deleted.append(result)
                else:
                    if result.is_dir:
                        import shutil
                        shutil.rmtree(result.path)
                    else:
                        os.remove(result.path)
                    logger.info(f"  ✅ 已删除: {result.path}")
                    self.deleted.append(result)
            except Exception as e:
                logger.warning(f"  ❌ 删除失败: {result.path} ({e})")
                self.failed.append((result, str(e)))

        freed_bytes = sum(r.size_bytes for r in self.deleted)
        return {
            "dry_run": dry_run,
            "deleted_count": len(self.deleted),
            "failed_count": len(self.failed),
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 ** 2), 1),
            "freed_gb": round(freed_bytes / (1024 ** 3), 2),
        }
