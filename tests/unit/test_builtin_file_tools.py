"""
delete / move / copy 三个文件管理工具的单元测试。

直接通过 ToolRegistry.execute 调用注册后的工具，验证文件系统副作用与错误处理。
所有操作限定在 tmp_path 工作区内（_safe_path 沙箱）。
"""

from __future__ import annotations

import pytest

from butler.core.agent_runtime.builtin_tools import register_builtin_tools
from butler.core.agent_runtime.tool_registry import ToolRegistry


@pytest.fixture
def registry(tmp_path):
    """注册全部内置工具，工作区指向临时目录。"""
    reg = ToolRegistry()
    register_builtin_tools(reg, workspace_root=str(tmp_path))
    return reg


# ═══════════════════════════════════════════════════════════════════════
#  delete
# ═══════════════════════════════════════════════════════════════════════

class TestDeleteTool:

    def test_delete_file(self, registry, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hello", encoding="utf-8")

        result = registry.execute("delete", {"path": str(f)})

        assert result.success is True
        assert "Successfully deleted" in result.content
        assert not f.exists()

    def test_delete_directory_recursive(self, registry, tmp_path):
        d = tmp_path / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "nested.txt").write_text("x", encoding="utf-8")
        (d / "top.txt").write_text("y", encoding="utf-8")

        result = registry.execute("delete", {"path": str(d)})

        assert result.success is True
        assert not d.exists()

    def test_delete_nonexistent_returns_error(self, registry, tmp_path):
        result = registry.execute("delete", {"path": str(tmp_path / "nope")})

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_delete_relative_path(self, registry, tmp_path):
        # 相对路径基于 ws_root 解析
        (tmp_path / "rel.txt").write_text("z", encoding="utf-8")

        result = registry.execute("delete", {"path": "rel.txt"})

        assert result.success is True
        assert not (tmp_path / "rel.txt").exists()


# ═══════════════════════════════════════════════════════════════════════
#  move
# ═══════════════════════════════════════════════════════════════════════

class TestMoveTool:

    def test_move_file(self, registry, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("payload", encoding="utf-8")

        result = registry.execute("move", {
            "source": str(src),
            "destination": str(dst),
        })

        assert result.success is True
        assert not src.exists()
        assert dst.read_text(encoding="utf-8") == "payload"

    def test_move_directory(self, registry, tmp_path):
        src = tmp_path / "old_dir"
        (src / "inner").mkdir(parents=True)
        (src / "inner" / "f.txt").write_text("data", encoding="utf-8")
        dst = tmp_path / "new_dir"

        result = registry.execute("move", {
            "source": str(src),
            "destination": str(dst),
        })

        assert result.success is True
        assert not src.exists()
        assert (dst / "inner" / "f.txt").read_text(encoding="utf-8") == "data"

    def test_move_creates_destination_parent(self, registry, tmp_path):
        src = tmp_path / "f.txt"
        src.write_text("c", encoding="utf-8")
        dst = tmp_path / "nested" / "deep" / "f.txt"

        result = registry.execute("move", {
            "source": str(src),
            "destination": str(dst),
        })

        assert result.success is True
        assert dst.exists()

    def test_move_nonexistent_source(self, registry, tmp_path):
        result = registry.execute("move", {
            "source": str(tmp_path / "nope"),
            "destination": str(tmp_path / "dst"),
        })

        assert result.success is False
        assert "source not found" in result.error.lower()

    def test_move_existing_destination_blocked(self, registry, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("a", encoding="utf-8")
        dst.write_text("b", encoding="utf-8")

        result = registry.execute("move", {
            "source": str(src),
            "destination": str(dst),
        })

        assert result.success is False
        assert "already exists" in result.error.lower()
        # 源与目的均应保持原状
        assert src.exists()
        assert dst.read_text(encoding="utf-8") == "b"


# ═══════════════════════════════════════════════════════════════════════
#  copy
# ═══════════════════════════════════════════════════════════════════════

class TestCopyTool:

    def test_copy_file_preserves_source(self, registry, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("payload", encoding="utf-8")

        result = registry.execute("copy", {
            "source": str(src),
            "destination": str(dst),
        })

        assert result.success is True
        assert src.exists()  # 源保留
        assert dst.read_text(encoding="utf-8") == "payload"

    def test_copy_directory_recursive(self, registry, tmp_path):
        src = tmp_path / "tree"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "f.txt").write_text("data", encoding="utf-8")
        (src / "top.txt").write_text("y", encoding="utf-8")
        dst = tmp_path / "tree_copy"

        result = registry.execute("copy", {
            "source": str(src),
            "destination": str(dst),
        })

        assert result.success is True
        assert src.exists()  # 源保留
        assert (dst / "sub" / "f.txt").read_text(encoding="utf-8") == "data"
        assert (dst / "top.txt").read_text(encoding="utf-8") == "y"

    def test_copy_nonexistent_source(self, registry, tmp_path):
        result = registry.execute("copy", {
            "source": str(tmp_path / "nope"),
            "destination": str(tmp_path / "dst"),
        })

        assert result.success is False
        assert "source not found" in result.error.lower()

    def test_copy_existing_destination_blocked(self, registry, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("a", encoding="utf-8")
        dst.write_text("b", encoding="utf-8")

        result = registry.execute("copy", {
            "source": str(src),
            "destination": str(dst),
        })

        assert result.success is False
        assert "already exists" in result.error.lower()
        assert dst.read_text(encoding="utf-8") == "b"


# ═══════════════════════════════════════════════════════════════════════
#  注册与权限元数据
# ═══════════════════════════════════════════════════════════════════════

class TestToolRegistrationMetadata:

    def test_all_three_tools_registered(self, registry):
        names = registry.list_names()
        assert "delete" in names
        assert "move" in names
        assert "copy" in names

    def test_delete_is_destructive_require_confirm(self, registry):
        defn = registry.get("delete").definition
        assert defn.is_destructive is True
        assert defn.permission_level.value == "require_confirm"

    def test_move_is_destructive_require_confirm(self, registry):
        defn = registry.get("move").definition
        assert defn.is_destructive is True
        assert defn.permission_level.value == "require_confirm"

    def test_copy_is_not_destructive_require_confirm(self, registry):
        defn = registry.get("copy").definition
        assert defn.is_destructive is False
        assert defn.permission_level.value == "require_confirm"


# ═══════════════════════════════════════════════════════════════════════
#  路径沙箱
# ═══════════════════════════════════════════════════════════════════════

class TestPathSandbox:

    def test_delete_outside_workspace_blocked(self, registry, tmp_path):
        # /etc/hostname 几乎必然存在于 Linux 沙箱
        result = registry.execute("delete", {"path": "/etc/hostname"})

        assert result.success is False
        # _safe_path 抛 PermissionError → ToolExecutor 包装为错误
        assert "outside workspace" in result.error.lower() or "permission" in result.error.lower()
