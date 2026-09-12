"""
Binary Cleaner — 主入口

用法：
    # 扫描当前目录
    python main.py

    # 扫描指定路径
    python main.py ~/Projects

    # 快速扫描 home 目录
    python main.py --quick

    # 扫描并清理（dry-run）
    python main.py --clean --dry-run

    # 扫描并实际清理
    python main.py --clean

    # 只扫描特定类别
    python main.py --categories python_build,node_build

    # 清理 Docker
    python main.py --docker

    # 指定扫描深度
    python main.py --depth 5 ~/code
"""

import os
import sys
import json
import argparse
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.binary_cleaner.scanner import BinaryScanner, BinaryCleaner
from skills.binary_cleaner.docker_cleaner import DockerCleaner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("binary-cleaner")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    return f"{size_bytes / (1024 ** 3):.2f} GB"


def print_report(report):
    """打印扫描报告"""
    print(f"\n{'='*60}")
    print(f"  🔍 扫描报告")
    print(f"{'='*60}")
    print(f"  路径: {report.scan_path}")
    print(f"  耗时: {report.scan_time:.1f}s")
    print(f"  发现: {report.total_files} 个不必要文件/目录")
    print(f"  总大小: {format_size(report.total_size_bytes)}")

    if report.categories:
        print(f"\n  {'类别':<22} {'数量':>8} {'大小':>12}")
        print(f"  {'-'*22} {'-'*8} {'-'*12}")
        for cat, info in sorted(report.categories.items(), key=lambda x: -x[1]["size"]):
            print(f"  {cat:<22} {info['count']:>8} {format_size(info['size']):>12}")

    if report.results:
        print(f"\n  前 20 个最大文件/目录:")
        print(f"  {'-'*60}")
        sorted_results = sorted(report.results, key=lambda r: -r.size_bytes)[:20]
        for i, r in enumerate(sorted_results, 1):
            size_str = format_size(r.size_bytes)
            type_icon = "📁" if r.is_dir else "📄"
            # 截断过长路径
            display_path = r.path
            if len(display_path) > 50:
                display_path = "..." + display_path[-47:]
            print(f"  {i:>3}. {type_icon} {display_path:<50} {size_str:>10} [{r.category}]")

    print()


def print_clean_result(result):
    """打印清理结果"""
    mode = "模拟清理" if result["dry_run"] else "实际清理"
    print(f"\n{'='*60}")
    print(f"  🗑️ {mode}结果")
    print(f"{'='*60}")
    print(f"  删除: {result['deleted_count']} 个")
    print(f"  失败: {result['failed_count']} 个")
    print(f"  释放: {format_size(result['freed_bytes'])}")
    if result["dry_run"]:
        print(f"\n  ⚠️  以上为模拟结果，未实际删除。")
        print(f"  执行实际清理请去掉 --dry-run 参数")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Binary Cleaner — 扫描并清理不必要的二进制文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=".", help="扫描路径（默认当前目录）")
    parser.add_argument("--quick", action="store_true", help="快速扫描 home 目录")
    parser.add_argument("--clean", action="store_true", help="执行清理")
    parser.add_argument("--dry-run", action="store_true", default=True, help="模拟模式（默认）")
    parser.add_argument("--force", action="store_true", help="实际删除（去掉 dry-run）")
    parser.add_argument("--categories", help="限定类别（逗号分隔）")
    parser.add_argument("--depth", type=int, default=10, help="扫描深度（默认 10）")
    parser.add_argument("--docker", action="store_true", help="清理 Docker 孤立资源")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--all", action="store_true", help="扫描所有已知路径")

    args = parser.parse_args()

    categories = None
    if args.categories:
        categories = [c.strip() for c in args.categories.split(",")]

    scanner = BinaryScanner()

    # Docker 清理
    if args.docker:
        docker = DockerCleaner()
        if not docker.is_available():
            print("❌ Docker 不可用")
            sys.exit(1)

        print("🔍 扫描 Docker 资源...")
        scan_result = docker.scan()
        if args.json:
            print(json.dumps(scan_result, indent=2, ensure_ascii=False))
        else:
            print(f"\n  Dangling images: {scan_result['dangling_images']['count']} 个")
            print(f"  Stopped containers: {scan_result['stopped_containers']['count']} 个")
            print(f"  Unused volumes: {scan_result['unused_volumes']['count']} 个")
            print(f"  总大小: {format_size(scan_result['total_size_bytes'])}")

        if args.clean:
            dry_run = not args.force
            print(f"\n{'🔍 模拟清理' if dry_run else '🗑️ 实际清理'} Docker 资源...")
            clean_result = docker.clean(dry_run=dry_run)
            if args.json:
                print(json.dumps(clean_result, indent=2, ensure_ascii=False))
        return

    # 全路径扫描
    if args.all:
        home = os.path.expanduser("~")
        scan_paths = [home]
    elif args.quick:
        scan_paths = [os.path.expanduser("~")]
    else:
        scan_paths = [os.path.expanduser(args.path)]

    for scan_path in scan_paths:
        print(f"\n🔍 扫描: {scan_path}")
        report = scanner.scan(scan_path, categories=categories, max_depth=args.depth)

        if args.json:
            output = {
                "scan_path": report.scan_path,
                "scan_time": report.scan_time,
                "total_files": report.total_files,
                "total_size_bytes": report.total_size_bytes,
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
                    for r in report.results
                ],
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print_report(report)

        # 清理
        if args.clean:
            dry_run = not args.force
            cleaner = BinaryCleaner()

            if not dry_run:
                # 实际删除前确认
                print(f"⚠️  即将删除 {report.total_files} 个文件/目录，"
                      f"释放 {format_size(report.total_size_bytes)}")
                confirm = input("  确认删除？(输入 YES): ")
                if confirm != "YES":
                    print("  取消操作")
                    continue

            result = cleaner.clean(report, dry_run=dry_run, categories=categories)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print_clean_result(result)


if __name__ == "__main__":
    main()
