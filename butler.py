#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Butler 统一入口脚本。

能力：
- ``--run <skill>``  独立运行指定技能
- ``audit``          系统安全审计自检与报告生成

（原先的资产同步中心 sync_hub 已随 Android 子模块一并移除。）
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 可独立运行的技能：名称 -> 入口模块（暴露 main()）
SKILL_RUNNERS = {
    "downloader": "skills.downloader.run",
    "format_convert": "skills.format_convert.run",
}


def run_skill(name: str) -> None:
    module_path = SKILL_RUNNERS.get(name)
    if module_path is None:
        print(f"未知技能: {name}（可用: {', '.join(sorted(SKILL_RUNNERS))}）")
        sys.exit(1)
    module = __import__(module_path, fromlist=["main"])
    module.main()


def main() -> None:
    parser = argparse.ArgumentParser(description="Butler 统一入口")
    parser.add_argument("--run", choices=sorted(SKILL_RUNNERS), help="独立运行指定技能")
    parser.add_argument("command", nargs="?", choices=["audit"], help="audit: 系统安全审计自检与报告生成")
    args = parser.parse_args()

    if args.command == "audit":
        from butler.core.sec_utils.audit import run_security_audit

        print(run_security_audit())
        return

    if args.run:
        run_skill(args.run)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
