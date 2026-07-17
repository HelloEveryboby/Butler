#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from butler.sync_hub.checker import Checker
from butler.sync_hub.manifest import ManifestManager
from butler.sync_hub.sync import SyncEngine
from butler.sync_hub.rollback import RollbackManager
from butler.sync_hub.init import InitManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sync_hub.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("ButlerHub")

def main():
    if "--run" in sys.argv:
        idx = sys.argv.index("--run")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "downloader":
            from skills.downloader.run import main as run_downloader
            run_downloader()
            return

    parser = argparse.ArgumentParser(description="Butler 资产同步中心 (Asset Sync Hub)")
    parser.add_argument("--run", choices=["downloader"], help="拉起并独立运行特定的 Butler 模块/技能 (例如: downloader)")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # Sync
    sync_parser = subparsers.add_parser("sync", help="同步资源到 Android")
    sync_parser.add_argument("--force", action="store_true", help="强制覆盖，忽略冲突")
    sync_parser.add_argument("--no-backup", action="store_true", help="同步前不进行备份")

    # Init
    subparsers.add_parser("init", help="初始化同步环境")

    # Rollback
    rollback_parser = subparsers.add_parser("rollback", help="回滚资源版本")
    rollback_parser.add_argument("--step", type=int, default=1, help="回滚步数 (默认: 1)")

    # Check
    subparsers.add_parser("check-env", help="检查环境与工具链")

    # Reverse Sync
    subparsers.add_parser("reverse-sync", help="从 Android 反向同步资产到 PC (调试用)")

    # Audit
    subparsers.add_parser("audit", help="系统安全审计自检与报告生成")

    if len(sys.argv) == 1:
        # If no arguments, try interactive mode
        run_interactive()
        return

    args = parser.parse_args()
    execute_command(args)

def execute_command(args):
    root = os.getcwd()
    checker = Checker(root)
    manifest_mgr = ManifestManager(root)
    manifest_mgr.load()

    if args.command == "audit":
        from butler.core.sec_utils.audit import run_security_audit
        print(run_security_audit())

    elif args.command == "init":
        im = InitManager(root)
        print(im.init_android())

    elif args.command == "sync":
        # 1. Backup first
        if not args.no_backup:
            rm = RollbackManager(root)
            print(rm.create_backup())

        # 2. Sync
        engine = SyncEngine(root, checker, manifest_mgr)
        stats = engine.sync(force=args.force)

        print("\n--- 同步报告 ---")
        print(f"✅ 已同步: {stats['synced']}")
        print(f"⏩ 已跳过: {stats['skipped']}")
        print(f"❌ 错误: {stats['errors']}")
        print(f"📦 包体大小: {stats['bundle_size_mb']:.2f} MB")

        if stats['conflicts']:
            print("\n⚠️ 检测到冲突 (Android 端已修改):")
            for conflict in stats['conflicts']:
                print(f"  - {conflict['dst']}")
            print("\n💡 建议: 请确认修改，或使用 --force 强制覆盖。")

    elif args.command == "rollback":
        rm = RollbackManager(root)
        print(rm.rollback(args.step))

    elif args.command == "check-env":
        matrix = checker.check_env()
        print(f"\n--- 环境检查 ---")
        print(f"模式: {matrix.mode}")
        print(f"Pillow (图片库): {'✅' if matrix.has_pillow else '❌'}")
        print(f"cwebp (WebP 工具): {'✅' if matrix.has_cwebp else '❌'}")
        print(f"ffmpeg (音频工具): {'✅' if matrix.has_ffmpeg else '❌'}")

        if matrix.mode == "Compatibility":
            print("\n💡 提示: 当前处于兼容模式，音频压缩可能被跳过。")
        elif matrix.mode == "Restricted":
            print("\n⚠️ 警告: 缺少核心工具，同步将仅执行文件复制。")

    elif args.command == "reverse-sync":
        print("Reverse sync logic not fully implemented yet - placeholder.")

def run_interactive():
    try:
        import questionary
    except ImportError:
        print("💡 建议安装 questionary 以获得更好的交互体验: pip install questionary")
        run_simple_interactive()
        return

    print("--- Butler 资产同步中心 (Asset Sync Hub) ---")
    action = questionary.select(
        "请选择操作:",
        choices=[
            "🚀 一键同步到 Android",
            "🔄 回滚到上一个版本",
            "⚙️ 初始化环境",
            "🔍 检查环境",
            "🛡️ 执行安全审计自检",
            "🚪 退出"
        ]
    ).ask()

    if action == "🚀 一键同步到 Android":
        class Args: command = "sync"; force = False; no_backup = False
        execute_command(Args())
    elif action == "🔄 回滚到上一个版本":
        class Args: command = "rollback"; step = 1
        execute_command(Args())
    elif action == "⚙️ 初始化环境":
        class Args: command = "init"
        execute_command(Args())
    elif action == "🔍 检查环境":
        class Args: command = "check-env"
        execute_command(Args())
    elif action == "🛡️ 执行安全审计自检":
        class Args: command = "audit"
        execute_command(Args())

def run_simple_interactive():
    print("\n--- Butler 资产同步中心 ---")
    print("1. 同步 (sync)")
    print("2. 回滚 (rollback)")
    print("3. 初始化 (init)")
    print("4. 检查环境 (check-env)")
    print("5. 执行安全审计自检 (audit)")
    print("6. 退出")

    choice = input("\n请选择 [1-6]: ")
    if choice == '1':
        class Args: command = "sync"; force = False; no_backup = False
        execute_command(Args())
    elif choice == '2':
        class Args: command = "rollback"; step = 1
        execute_command(Args())
    elif choice == '3':
        class Args: command = "init"
        execute_command(Args())
    elif choice == '4':
        class Args: command = "check-env"
        execute_command(Args())
    elif choice == '5':
        class Args: command = "audit"
        execute_command(Args())

if __name__ == "__main__":
    main()
