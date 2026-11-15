import sys
import os
import sqlite3
from pathlib import Path
from package.core_utils.config_loader import config_loader

def run_doctor():
    print("=== Butler Diagnostics (Doctor Mode) ===")

    suggestions = []

    # 1. Python Version
    version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info.major == 3 and sys.version_info.minor in [10, 11]:
        print(f"✓ Python {version_str} (Recommended version)")
    elif sys.version_info.major == 3 and sys.version_info.minor >= 12:
        print(f"⚠ Python {version_str} (Python 3.10 or 3.11 is recommended, Python 3.12+ might have dependency wheel issues)")
    else:
        print(f"❌ Python {version_str} (Unsupported version! Python 3.10 or 3.11 is required)")
        suggestions.append("切换到 Python 3.10/3.11 后重新安装依赖: python -m package.dependency_manager install_all")

    # 2. Dependencies
    missing_packages = []
    packages_to_check = {
        "pydantic": "pydantic",
        "yaml": "PyYAML",
        "cryptography": "cryptography",
        "websockets": "websockets",
        "requests": "requests",
        "watchdog": "watchdog",
        "redis": "redis"
    }
    for mod_name, pkg_name in packages_to_check.items():
        try:
            __import__(mod_name)
        except ImportError:
            missing_packages.append(pkg_name)

    if not missing_packages:
        print("✓ Dependencies OK")
    else:
        print(f"❌ Missing Dependencies: {', '.join(missing_packages)} (Please run: pip install -r requirements.txt)")
        suggestions.append(f"补齐缺失依赖: python -m package.dependency_manager install_all (或 pip install -r requirements.txt)")

    # 3. API Key
    deepseek_key = os.getenv("DEEPSEEK_API_KEY") or config_loader.get("api.deepseek.key")
    openai_key = os.getenv("OPENAI_API_KEY") or config_loader.get("api.openai.key")

    if deepseek_key and "YOUR_" not in str(deepseek_key):
        print("✓ DEEPSEEK_API_KEY Configured")
    else:
        print("⚠ Missing DEEPSEEK_API_KEY")

    if openai_key and "YOUR_" not in str(openai_key):
        print("✓ OPENAI_API_KEY Configured")
    else:
        print("⚠ Missing OPENAI_API_KEY")

    if not ((deepseek_key and "YOUR_" not in str(deepseek_key)) or (openai_key and "YOUR_" not in str(openai_key))):
        suggestions.append("配置 AI 服务商密钥: 运行 butler config（或编辑 .env 填入 DEEPSEEK_API_KEY），参考 docs/start/env-reference.md")

    # 4. Model configuration / status
    model_provider = config_loader.get("api.provider") or "deepseek"
    print(f"✓ Model Provider: {model_provider}")

    # 5. Directory permissions
    project_root = Path(__file__).resolve().parent.parent.parent
    dirs_to_check = [
        project_root / "config",
        project_root / "data"
    ]
    permission_ok = True
    for d in dirs_to_check:
        d.mkdir(parents=True, exist_ok=True)
        test_file = d / ".permission_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception:
            permission_ok = False
            break

    if permission_ok:
        print("✓ Permission OK")
    else:
        print("❌ Permission Denied (Some directory is not writable!)")
        suggestions.append("目录不可写: 检查 config/ 与 data/ 的属主与权限 (chmod u+w)，或将仓库移至可写路径")

    # 6. Database / Storage
    storage_ok = True
    db_paths = [
        project_root / "butler" / "data" / "system_data" / "long_memory.db",
        project_root / "butler" / "data" / "system_data" / "secrets.db"
    ]
    for db_p in db_paths:
        if db_p.exists():
            try:
                conn = sqlite3.connect(db_p)
                conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                conn.close()
            except Exception as e:
                storage_ok = False
                print(f"⚠ Database corruption detected in {db_p.name}: {e}")

    if storage_ok:
        print("✓ Storage available")
    else:
        print("❌ Database errors or storage unavailable")
        suggestions.append("数据库异常: 备份 butler/data/system_data/ 后运行 butler doctor --fix 或删除受损的 .db 文件（首次启动会自动重建）")

    print("========================================")
    print("🔧 下一步建议:")
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            print(f"   {i}. {s}")
    else:
        print("   ✅ 一切就绪！运行 butler start 启动服务，或 butler tui 进入交互界面。")
    print("   💡 遇到问题随时回来运行: butler doctor")

if __name__ == "__main__":
    run_doctor()
