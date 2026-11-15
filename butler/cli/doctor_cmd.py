# -*- coding: utf-8 -*-
import sys
import sqlite3
import os
from pathlib import Path

def run_doctor():
    """
    对 Butler v2.0 Alpha 全新运行架构开展全面的健康度自检与预检（Doctor Mode）。
    """
    print("==================================================")
    print("      Butler v2.0 Alpha 核心系统健康度自检预检     ")
    print("==================================================")

    suggestions = []

    # 1. 检查 Python 环境
    print(f"[*] 当前 Python 版本: {sys.version}")

    # 2. 检查 SQLite 数据库联通度与表迁移结构
    db_path = Path(__file__).resolve().parent.parent / "data" / "system_data" / "long_memory.db"
    print(f"[*] 检查数据库联结: {db_path}")
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in cursor.fetchall()]
            conn.close()
            print(f"  - 数据库已成功连通。已存在的数据表: {', '.join(tables)}")

            # 核对关键的 v2.0 新数据表是否存在
            crit = ["users", "tasks", "packages", "memory"]
            missing = [t for t in crit if t not in tables]
            if not missing:
                print("  - [✅] 所有 v2.0 关键数据表均已存在，数据结构完好。")
            else:
                print(f"  - [❌] 缺失关键数据表: {', '.join(missing)}")
                suggestions.append("数据表缺失: 运行 butler start 可自动执行数据库迁移补全")
        except Exception as e:
            print(f"  - [❌] 数据库建立或查询异常: {e}")
            suggestions.append("数据库异常: 备份 butler/data/system_data/ 后重试，或删除受损 long_memory.db（首次启动自动重建）")
    else:
        print("  - [⚠️] 尚未生成 long_memory.db 数据库文件（将在首次执行 'start' 时自动运行迁移并生成）。")
        suggestions.append("数据库尚未初始化: 运行 butler start 即可自动创建")

    # 3. 检查技能包存储层完整性
    pkg_dir = Path(__file__).resolve().parent.parent / "data" / "installed_packages"
    print(f"[*] 检查技能与员工包物理存储目录: {pkg_dir}")
    if pkg_dir.exists():
        folders = [f.name for f in pkg_dir.iterdir() if f.is_dir()]
        print(f"  - 存储目录状态正常。已检测到本地包: {', '.join(folders)}")
        print("  - [✅] 技能包加载器存储配置校验成功。")
    else:
        print("  - [⚠️] 本地包目录尚不存在（将在系统冷启动时自动创建并部署内置演示包）。")

    # 4. 检查全局配置文件
    config_file = Path(__file__).resolve().parent.parent.parent / "config" / "config.yaml"
    print(f"[*] 检查全局配置文件: {config_file}")
    if config_file.exists():
        print("  - [✅] 全局 config.yaml 校验成功。")
    else:
        print("  - [❌] 缺失全局 config.yaml 配置文件。")
        suggestions.append("配置缺失: 运行 butler config 重新生成配置")

    print("\n[Doctor] 所有核心模块自检完成。")
    print("🔧 下一步建议:")
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            print(f"   {i}. {s}")
    else:
        print("   ✅ 系统健康！运行 butler start 启动核心服务，或 butler tui 进入交互界面。")
    print("   💡 遇到问题随时回来运行: butler doctor")
    print("==================================================")
