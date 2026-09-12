"""
Binary Cleaner Skill — 扫描并清理不必要的二进制文件

支持 Python/Node/C++/Rust/Go/Java/Docker 等多语言生态的构建产物清理。
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

SKILL_NAME = "binary_cleaner"
SKILL_VERSION = "1.0.0"


def handle_request(action: str, params: dict = None) -> dict:
    """
    Butler 技能入口 — 处理来自 Butler 的 Action 请求。

    :param action: 操作名称
    :param params: 参数字典
    :return: 响应字典
    """
    params = params or {}

    from .scanner import BinaryScanner, BinaryCleaner
    from .docker_cleaner import DockerCleaner

    scanner = BinaryScanner()
    cleaner = BinaryCleaner()

    if action == "scan":
        path = params.get("path", os.path.expanduser("~"))
        categories = params.get("categories")
        depth = params.get("depth", 10)
        report = scanner.scan(path, categories=categories, max_depth=depth)
        return {
            "scan_path": report.scan_path,
            "total_files": report.total_files,
            "total_size_bytes": report.total_size_bytes,
            "total_size_mb": round(report.total_size_mb, 1),
            "categories": report.categories,
            "results": [
                {
                    "path": r.path,
                    "category": r.category,
                    "reason": r.reason,
                    "size_bytes": r.size_bytes,
                    "is_dir": r.is_dir,
                    "risk": r.risk,
                }
                for r in report.results[:200]  # 限制返回数量
            ],
        }

    elif action == "quick_scan":
        report = scanner.scan_home()
        return {
            "total_files": report.total_files,
            "total_size_mb": round(report.total_size_mb, 1),
            "categories": report.categories,
        }

    elif action == "project_scan":
        path = params.get("path", ".")
        report = scanner.scan_project(path)
        return {
            "scan_path": report.scan_path,
            "total_files": report.total_files,
            "total_size_mb": round(report.total_size_mb, 1),
            "categories": report.categories,
            "top_10": [
                {
                    "path": r.path,
                    "category": r.category,
                    "size_bytes": r.size_bytes,
                }
                for r in sorted(report.results, key=lambda x: -x.size_bytes)[:10]
            ],
        }

    elif action == "clean":
        path = params.get("path", os.path.expanduser("~"))
        categories = params.get("categories")
        dry_run = params.get("dry_run", True)
        depth = params.get("depth", 10)

        report = scanner.scan(path, categories=categories, max_depth=depth)
        result = cleaner.clean(report, dry_run=dry_run, categories=categories)
        return result

    elif action == "docker_clean":
        docker = DockerCleaner()
        if not docker.is_available():
            return {"available": False, "error": "Docker 不可用"}

        dry_run = params.get("dry_run", True)
        scan = docker.scan()
        clean = docker.clean(dry_run=dry_run)
        return {"scan": scan, "clean": clean}

    elif action == "stats":
        return {
            "skill": SKILL_NAME,
            "version": SKILL_VERSION,
            "supported_categories": [
                "python_build", "node_build", "cpp_build",
                "rust_build", "go_build", "java_build",
                "docker", "ide_cache", "general_build",
            ],
        }

    else:
        return {"error": f"未知操作: {action}"}


def get_skill_info() -> dict:
    """返回 Skill 元信息"""
    return {
        "name": SKILL_NAME,
        "version": SKILL_VERSION,
        "description": "扫描并清理不必要的二进制文件、构建产物、编译缓存",
        "trigger_keywords": [
            "清理二进制", "清理构建产物", "清理缓存",
            "删除 .pyc", "清理 __pycache__", "清理 target",
            "清理 node_modules 缓存", "Docker 清理",
            "磁盘空间", "释放空间", "垃圾文件",
        ],
        "actions": ["scan", "quick_scan", "project_scan", "clean", "docker_clean", "stats"],
    }
