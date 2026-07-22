#!/usr/bin/env python3
"""
Butler 跨平台 Android 壳管理与构建工具
支持针对 Kotlin Gradle 壳 (native) 与 Flutter 壳 (flutter) 的同步与一键打包
"""

import argparse
import fnmatch
import json
import os
import shutil
import sys
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 目标壳路径映射
TARGET_MAP = {
    "native": BASE_DIR / "butler_android",
    "flutter": BASE_DIR / "butler_android_flutter",
}

# === 同步规则 ===
PYTHON_INCLUDES = [
    "butler/core/",
    "butler/skills/",
    "butler/butler_app.py",
    "butler/__init__.py",
    "package/core_utils/",
    "package/document/",
    "package/file_system/",
    "package/device/hardware_manager.py",
    "package/algorithm/",
    "package/__init__.py",
]

PYTHON_EXCLUDES = [
    "**/__pycache__/",
    "**/*.pyc",
    "**/test_*.py",
    "**/tests/",
    "**/*_test.py",
    "**/conftest.py",
    "butler/gui/",
    "butler/core/hybrid_link/",
    "package/device/usb_*.py",
    "package/device/stm32_*.py",
    "package/custom_tools/",
]

SKILL_INCLUDES = [
    "skills/chat/",
    "skills/system_info/",
    "skills/file_manager/",
    "skills/note/",
    "skills/weather/",
    "skills/search/",
]

ANDROID_REQUIREMENTS = [
    "requests>=2.31.0",
    "pyyaml>=6.0",
    "chardet>=5.0",
    "beautifulsoup4",
    "markdownify",
    "python-dateutil",
    "tqdm",
]


def should_exclude(path: str, patterns: list[str]) -> bool:
    """检查路径是否匹配排除规则"""
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path + "/", pattern):
            return True
        parts = path.split("/")
        for i in range(len(parts)):
            partial = "/".join(parts[:i + 1])
            if fnmatch.fnmatch(partial, pattern.rstrip("/")):
                return True
    return False


def sync_assets(target_type: str, dry_run: bool = False):
    target_path = TARGET_MAP.get(target_type)
    if not target_path or not target_path.exists():
        print(f"❌ Error: 目标目录 {target_path} 不存在！", file=sys.stderr)
        sys.exit(1)

    print(f"📦 正在针对 [{target_type.upper()}] 壳工程执行静态资源与 Go/Python 核心同步...")

    # Determine Python and Frontend targets based on target type
    if target_type == "native":
        python_target = target_path / "app" / "src" / "main" / "python"
        frontend_target = target_path / "app" / "src" / "main" / "assets" / "www"
    else:  # flutter
        python_target = target_path / "android" / "app" / "src" / "main" / "python"
        frontend_target = target_path / "assets" / "www"

    # Sync Python modules
    if python_target.exists() and not dry_run:
        shutil.rmtree(python_target)
        print(f"  🗑️  清理 {python_target.relative_to(BASE_DIR)}")

    synced = 0
    skipped = 0

    for include in PYTHON_INCLUDES:
        src = BASE_DIR / include
        if not src.exists():
            print(f"  ⚠️  跳过 (不存在): {include}")
            continue

        if src.is_file():
            rel = src.relative_to(BASE_DIR)
            dst = python_target / rel
            if should_exclude(str(rel), PYTHON_EXCLUDES):
                skipped += 1
                continue
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            synced += 1
        else:
            for file in src.rglob("*"):
                if not file.is_file():
                    continue
                rel = file.relative_to(BASE_DIR)
                if should_exclude(str(rel), PYTHON_EXCLUDES):
                    skipped += 1
                    continue
                dst = python_target / rel
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, dst)
                synced += 1

    # Sync Skills
    for include in SKILL_INCLUDES:
        src = BASE_DIR / include
        if not src.exists():
            continue

        for file in src.rglob("*"):
            if not file.is_file():
                continue
            rel = file.relative_to(BASE_DIR)
            if should_exclude(str(rel), PYTHON_EXCLUDES):
                skipped += 1
                continue
            dst = python_target / rel
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dst)
            synced += 1

    # Generate requirements.txt
    if not dry_run:
        req_path = python_target / "requirements.txt"
        req_path.parent.mkdir(parents=True, exist_ok=True)
        with open(req_path, "w", encoding="utf-8") as f:
            f.write("# Butler Android — 裁剪版依赖\n")
            f.write("# 由 sync_android.py 自动生成，请勿手动编辑\n\n")
            for req in ANDROID_REQUIREMENTS:
                f.write(req + "\n")

    print(f"  ✅ Python 核心同步完成: {synced} 文件, {skipped} 跳过")

    # Sync Frontend assets (frontend_modern is the upgraded version)
    frontend_dist = BASE_DIR / "frontend_modern" / "dist"
    if not frontend_dist.exists():
        print(f"  ⚠️  前端未构建! 建议先在 frontend_modern/ 运行 npm run build")
    else:
        if frontend_target.exists() and not dry_run:
            shutil.rmtree(frontend_target)
        if not dry_run:
            shutil.copytree(frontend_dist, frontend_target)
        print(f"  ✅ 前端资源同步完成 -> {frontend_target.relative_to(BASE_DIR)}")

    print(f"✅ [{target_type.upper()}] 壳工程同步完成！")


def build_apk(target_type: str, release: bool = False):
    sync_assets(target_type)
    build_mode = "Release" if release else "Debug"
    print(f"🚀 开始构建 [{target_type.upper()}] 安卓包 ({build_mode})...")

    target_path = TARGET_MAP.get(target_type)
    if target_type == "native":
        # 运行 Gradle 构建
        gradlew = "./gradlew" if os.name != "nt" else "gradlew.bat"
        task = "assembleRelease" if release else "assembleDebug"
        print(f"  -> 正在运行 Gradle 构建: {target_path} task={task}")
        import subprocess
        try:
            subprocess.run([gradlew, task], cwd=target_path, check=True)
            print(f"🎉 Kotlin Native APK 构建成功！")
        except Exception as e:
            print(f"❌ Kotlin Native APK 构建失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif target_type == "flutter":
        # 运行 Flutter 构建
        cmd = ["flutter", "build", "apk"]
        if release:
            cmd.append("--release")
        else:
            cmd.append("--debug")
        print(f"  -> 正在运行 Flutter 构建: {target_path}")
        import subprocess
        try:
            subprocess.run(cmd, cwd=target_path, check=True)
            print(f"🎉 Flutter APK 构建成功！")
        except Exception as e:
            print(f"❌ Flutter APK 构建失败: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Butler 跨平台 Android 壳管理与构建工具")
    parser.add_argument(
        "--target",
        "-t",
        choices=["native", "flutter"],
        default="native",
        help="指定目标安卓壳：native (Kotlin Gradle 壳) 或 flutter (Flutter 壳)",
    )
    parser.add_argument(
        "--build",
        "-b",
        action="store_true",
        help="同步后直接触发 APK 构建",
    )
    parser.add_argument(
        "--release",
        "-r",
        action="store_true",
        help="配合 --build 参数构建 Release 版本",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际复制",
    )

    args = parser.parse_args()

    if args.build:
        build_apk(args.target, release=args.release)
    else:
        sync_assets(args.target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
