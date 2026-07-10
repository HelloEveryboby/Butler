import sys
from pathlib import Path
import pytest

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from butler.core.skill_manager import SkillManager

def test_core_plugins_auto_load():
    """Verify that core plugins are detected, marked, and forcibly loaded at startup."""
    sm = SkillManager()
    sm.load_skills()

    # Core plugins should be identified correctly
    assert sm.manifests["system_monitor"]["is_core"] is True
    assert sm.manifests["quick_launcher"]["is_core"] is True
    assert sm.manifests["clipboard_history"]["is_core"] is True

    # Standard skills (like media_manager or archive_manager) should not be core
    if "media_manager" in sm.manifests:
        assert sm.manifests["media_manager"]["is_core"] is False

    # Core plugins should be auto-loaded in loaded_skills
    assert "system_monitor" in sm.loaded_skills
    assert "quick_launcher" in sm.loaded_skills
    assert "clipboard_history" in sm.loaded_skills


def test_system_monitor_execution():
    """Verify that system_monitor executes and generates visual meter cards."""
    sm = SkillManager()
    sm.load_skills()

    res = sm.execute("system_monitor", "run")
    assert "Butler 系统监控卡片" in res
    assert "CPU 负载" in res
    assert "内存占用" in res
    assert "电池电量" in res


def test_quick_launcher_operations():
    """Verify registry listing, mapping, and delete operations of quick_launcher."""
    sm = SkillManager()
    sm.load_skills()

    # 1. List registered commands
    res_list = sm.execute("quick_launcher", "list")
    assert "当前注册的快捷启动指令" in res_list

    # 2. Register custom alias command
    res_reg = sm.execute("quick_launcher", "register", alias="echo_test", command="echo 'Hello Core'")
    assert "Successfully registered" in res_reg

    # 3. List contains newly registered alias
    res_list_new = sm.execute("quick_launcher", "list")
    assert "echo_test" in res_list_new

    # 4. Launch newly registered alias
    res_launch = sm.execute("quick_launcher", "launch", alias="echo_test")
    assert "Hello Core" in res_launch

    # 5. Delete alias
    res_del = sm.execute("quick_launcher", "delete", alias="echo_test")
    assert "Successfully deleted" in res_del


def test_clipboard_history_crypto_and_rolling():
    """Verify AES base64 clipboard history, manual adds, and clear operations."""
    sm = SkillManager()
    sm.load_skills()

    # 1. Clear clipboard database
    sm.execute("clipboard_history", "clear")

    # 2. Manual add sensitive string
    sm.execute("clipboard_history", "add", text="TopSecretPassword123")

    # 3. Retrieve and decrypt list
    res_list = sm.execute("clipboard_history", "list")
    assert "TopSecretPassword123" in res_list


def test_core_plugin_uninstall_protection():
    """Verify that uninstall commands fail and protect core plugins from removal."""
    sm = SkillManager()
    sm.load_skills()

    res = sm.execute("skill_manager", "uninstall", skill_name="system_monitor")
    assert "禁止热卸载" in res
