"""
内置工具集 — FileEditor + BashTool。

参考架构：
    - Claude Code: Read, Write, Edit, MultiEdit, Glob, Grep, LS, Bash
    - OpenHands: StrReplaceEditorTool, BashTool, IPythonTool

工具清单：
    FileEditor 工具组：
        - read: 读取文件内容（支持行范围）
        - write: 写入文件（创建或覆盖）
        - edit: 精确字符串匹配替换（str_replace）
        - multi_edit: 单文件批量编辑
        - glob: 文件模式匹配
        - grep: 内容搜索（正则表达式）
        - ls: 列出目录内容
        - delete: 删除文件或目录（递归）
        - move: 移动或重命名文件/目录
        - copy: 复制文件或目录（递归）

    Shell 工具组：
        - bash: 持久 Shell 会话执行命令
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from .tool_registry import ToolRegistry
from .types import PermissionLevel

logger = logging.getLogger(__name__)


def register_builtin_tools(
    registry: ToolRegistry,
    workspace_root: str | None = None,
) -> None:
    """
    注册所有内置工具到 ToolRegistry。

    参数:
        registry: 工具注册表
        workspace_root: 工作区根目录（用于路径安全检查）
    """
    ws_root = Path(workspace_root or os.getcwd()).resolve()

    _register_read_tool(registry, ws_root)
    _register_write_tool(registry, ws_root)
    _register_edit_tool(registry, ws_root)
    _register_multi_edit_tool(registry, ws_root)
    _register_glob_tool(registry, ws_root)
    _register_grep_tool(registry, ws_root)
    _register_ls_tool(registry, ws_root)
    _register_delete_tool(registry, ws_root)
    _register_move_tool(registry, ws_root)
    _register_copy_tool(registry, ws_root)
    _register_bash_tool(registry, ws_root)

    logger.info(f"Registered {len(registry.list_names())} builtin tools")


def _safe_path(path_str: str, ws_root: Path) -> Path:
    """确保路径在 workspace_root 内（防止路径遍历攻击）。"""
    path = Path(path_str)
    if not path.is_absolute():
        path = ws_root / path
    path = path.resolve()

    # 检查是否在 workspace_root 内
    try:
        path.relative_to(ws_root)
    except ValueError:
        # 允许临时目录
        temp_dir = Path(tempfile.gettempdir()).resolve()
        try:
            path.relative_to(temp_dir)
        except ValueError:
            raise PermissionError(
                f"Path '{path_str}' is outside workspace root '{ws_root}'"
            )

    return path


# ── Read 工具 ──────────────────────────────────────────────

def _register_read_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 read 工具。"""

    def read_file(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        path = _safe_path(arguments["path"], ws_root)

        if not path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        if not path.is_file():
            return {"success": False, "error": f"Not a file: {path}"}

        try:
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # 支持行范围
            offset = arguments.get("offset", 1)
            limit = arguments.get("limit", 2000)

            start = max(0, offset - 1)
            end = min(len(lines), start + limit)

            selected = lines[start:end]

            # 添加行号
            numbered = []
            for i, line in enumerate(selected, start=start + 1):
                numbered.append(f"{i:>6}\t{line}")

            result = "\n".join(numbered)
            if end < len(lines):
                result += f"\n... ({len(lines) - end} more lines)"

            return {
                "success": True,
                "content": result,
                "metadata": {
                    "file": str(path),
                    "total_lines": len(lines),
                    "shown_lines": f"{start + 1}-{end}",
                },
            }
        except UnicodeDecodeError:
            return {"success": False, "error": f"Binary file: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    registry.register(
        handler=read_file,
        name="read",
        description="Read the contents of a file. Supports line range via offset and limit parameters.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The absolute or relative path to the file to read.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-based). Default: 1.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Default: 2000.",
                },
            },
            "required": ["path"],
        },
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
        is_concurrency_safe=True,
    )


# ── Write 工具 ─────────────────────────────────────────────

def _register_write_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 write 工具。"""

    def write_file(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        path = _safe_path(arguments["path"], ws_root)
        content = arguments["content"]

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "content": f"Successfully wrote {len(content)} characters to {path}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    registry.register(
        handler=write_file,
        name="write",
        description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
        is_destructive=True,
    )


# ── Edit (str_replace) 工具 ────────────────────────────────

def _register_edit_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 edit 工具（精确字符串匹配替换）。"""

    def edit_file(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        path = _safe_path(arguments["path"], ws_root)
        old_str = arguments["old_string"]
        new_str = arguments["new_string"]

        if not old_str:
            return {"success": False, "error": "old_string must not be empty"}

        if not path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return {"success": False, "error": str(e)}

        # 检查 old_string 是否存在
        count = content.count(old_str)
        if count == 0:
            return {
                "success": False,
                "error": f"old_string not found in {path}. Ensure the string matches exactly, including whitespace.",
            }

        if count > 1:
            return {
                "success": False,
                "error": f"old_string found {count} times in {path}. Provide a more specific string or use multi_edit.",
            }

        # 执行替换
        new_content = content.replace(old_str, new_str, 1)

        try:
            path.write_text(new_content, encoding="utf-8")
            return {
                "success": True,
                "content": f"Successfully edited {path}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    registry.register(
        handler=edit_file,
        name="edit",
        description="Edit a file by replacing a specific string. The old_string must appear exactly once in the file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to edit.",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to replace. Must appear exactly once in the file.",
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace old_string with.",
                },
            },
            "required": ["path", "old_string", "new_string"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
        is_destructive=True,
    )


# ── MultiEdit 工具 ─────────────────────────────────────────

def _register_multi_edit_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 multi_edit 工具（单文件批量编辑）。"""

    def multi_edit_file(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        path = _safe_path(arguments["path"], ws_root)
        edits = arguments["edits"]

        if not path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return {"success": False, "error": str(e)}

        # 按顺序应用所有编辑
        applied = 0
        for edit in edits:
            old_str = edit.get("old_string", "")
            new_str = edit.get("new_string", "")

            if old_str not in content:
                return {
                    "success": False,
                    "error": f"old_string not found (edit #{applied + 1}): {old_str[:80]}...",
                }

            count = content.count(old_str)
            if count > 1:
                return {
                    "success": False,
                    "error": f"old_string found {count} times (edit #{applied + 1}). Provide more context.",
                }

            content = content.replace(old_str, new_str, 1)
            applied += 1

        try:
            path.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "content": f"Successfully applied {applied} edits to {path}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    registry.register(
        handler=multi_edit_file,
        name="multi_edit",
        description="Apply multiple edits to a single file in sequence. Each edit is a str_replace operation.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to edit.",
                },
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_string": {"type": "string"},
                            "new_string": {"type": "string"},
                        },
                        "required": ["old_string", "new_string"],
                    },
                    "description": "List of edits to apply in sequence.",
                },
            },
            "required": ["path", "edits"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
        is_destructive=True,
    )


# ── Glob 工具 ──────────────────────────────────────────────

def _register_glob_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 glob 工具（文件模式匹配）。"""

    def glob_files(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        pattern = arguments["pattern"]
        path_str = arguments.get("path", ".")
        search_path = _safe_path(path_str, ws_root)

        matches: list[str] = []
        for root, dirs, files in os.walk(search_path):
            # 跳过隐藏目录和 __pycache__
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    full = Path(root) / f
                    rel = full.relative_to(ws_root) if full.is_relative_to(ws_root) else full
                    matches.append(str(rel))

            for d in dirs:
                if fnmatch.fnmatch(d, pattern):
                    full = Path(root) / d
                    rel = full.relative_to(ws_root) if full.is_relative_to(ws_root) else full
                    matches.append(str(rel) + "/")

        matches.sort()
        return {
            "success": True,
            "content": "\n".join(matches[:200]) if matches else "No matches found.",
            "metadata": {"count": len(matches), "pattern": pattern},
        }

    registry.register(
        handler=glob_files,
        name="glob",
        description="Find files matching a glob pattern. Returns relative paths.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '*.py', '**/*.ts').",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Default: current directory.",
                },
            },
            "required": ["pattern"],
        },
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
        is_concurrency_safe=True,
    )


# ── Grep 工具 ──────────────────────────────────────────────

def _register_grep_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 grep 工具（内容搜索）。"""

    def grep_content(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        pattern = arguments["pattern"]
        path_str = arguments.get("path", ".")
        case_insensitive = arguments.get("case_insensitive", False)
        include_pattern = arguments.get("include", "*")

        search_path = _safe_path(path_str, ws_root)

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {"success": False, "error": f"Invalid regex: {e}"}

        matches: list[str] = []
        files_searched = 0

        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            for f in files:
                if not fnmatch.fnmatch(f, include_pattern):
                    continue

                file_path = Path(root) / f
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    files_searched += 1

                    for i, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            rel = file_path.relative_to(ws_root) if file_path.is_relative_to(ws_root) else file_path
                            matches.append(f"{rel}:{i}: {line.strip()[:200]}")

                            if len(matches) >= 200:
                                matches.append("... (truncated, more matches exist)")
                                return {
                                    "success": True,
                                    "content": "\n".join(matches),
                                    "metadata": {"count": len(matches), "files_searched": files_searched},
                                }
                except Exception:
                    continue

        return {
            "success": True,
            "content": "\n".join(matches) if matches else "No matches found.",
            "metadata": {"count": len(matches), "files_searched": files_searched},
        }

    registry.register(
        handler=grep_content,
        name="grep",
        description="Search file contents using regex. Returns matching lines with file paths and line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Default: current directory.",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Whether to perform case-insensitive search. Default: false.",
                },
                "include": {
                    "type": "string",
                    "description": "File name glob pattern to include (e.g., '*.py'). Default: '*'.",
                },
            },
            "required": ["pattern"],
        },
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
        is_concurrency_safe=True,
    )


# ── LS 工具 ────────────────────────────────────────────────

def _register_ls_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 ls 工具（列出目录内容）。"""

    def list_dir(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        path_str = arguments.get("path", ".")
        list_path = _safe_path(path_str, ws_root)

        if not list_path.exists():
            return {"success": False, "error": f"Path not found: {list_path}"}

        if not list_path.is_dir():
            return {"success": False, "error": f"Not a directory: {list_path}"}

        entries: list[str] = []
        for entry in sorted(list_path.iterdir()):
            # 跳过隐藏文件
            if entry.name.startswith("."):
                continue

            if entry.is_dir():
                entries.append(f"{entry.name}/")
            else:
                size = entry.stat().st_size
                entries.append(f"{entry.name} ({size} bytes)")

        return {
            "success": True,
            "content": "\n".join(entries) if entries else "(empty directory)",
            "metadata": {"count": len(entries)},
        }

    registry.register(
        handler=list_dir,
        name="ls",
        description="List directory contents. Returns file names and sizes.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Default: current directory.",
                },
            },
        },
        permission_level=PermissionLevel.ALWAYS_ALLOW,
        is_read_only=True,
        is_concurrency_safe=True,
    )


# ── Delete 工具 ────────────────────────────────────────────

def _register_delete_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 delete 工具（删除文件或目录，目录递归删除）。"""

    def delete_path(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        path = _safe_path(arguments["path"], ws_root)

        if not path.exists():
            return {"success": False, "error": f"Path not found: {path}"}

        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return {
                "success": True,
                "content": f"Successfully deleted {path}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    registry.register(
        handler=delete_path,
        name="delete",
        description="Delete a file or directory. Directories are removed recursively. This operation cannot be undone.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file or directory to delete.",
                },
            },
            "required": ["path"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
        is_destructive=True,
    )


# ── Move 工具 ──────────────────────────────────────────────

def _register_move_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 move 工具（移动或重命名文件/目录）。"""

    def move_path(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        src = _safe_path(arguments["source"], ws_root)
        dst = _safe_path(arguments["destination"], ws_root)

        if not src.exists():
            return {"success": False, "error": f"Source not found: {src}"}
        if dst.exists():
            return {
                "success": False,
                "error": f"Destination already exists: {dst}. Delete it first or choose another path.",
            }

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {
                "success": True,
                "content": f"Successfully moved {src} to {dst}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    registry.register(
        handler=move_path,
        name="move",
        description="Move or rename a file or directory. Fails if the destination already exists (to avoid silent overwrites).",
        parameters={
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The path to the file or directory to move.",
                },
                "destination": {
                    "type": "string",
                    "description": "The destination path. Must not already exist.",
                },
            },
            "required": ["source", "destination"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
        is_destructive=True,
    )


# ── Copy 工具 ──────────────────────────────────────────────

def _register_copy_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 copy 工具（复制文件或目录，目录递归复制）。"""

    def copy_path(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        src = _safe_path(arguments["source"], ws_root)
        dst = _safe_path(arguments["destination"], ws_root)

        if not src.exists():
            return {"success": False, "error": f"Source not found: {src}"}
        if dst.exists():
            return {
                "success": False,
                "error": f"Destination already exists: {dst}. Delete it first or choose another path.",
            }

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
            return {
                "success": True,
                "content": f"Successfully copied {src} to {dst}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    registry.register(
        handler=copy_path,
        name="copy",
        description="Copy a file or directory. Directories are copied recursively. Fails if the destination already exists (to avoid silent overwrites).",
        parameters={
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The path to the file or directory to copy.",
                },
                "destination": {
                    "type": "string",
                    "description": "The destination path. Must not already exist.",
                },
            },
            "required": ["source", "destination"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
        is_destructive=False,
    )


# ── Bash 工具（持久 Shell 会话）─────────────────────────────

class PersistentShell:
    """
    持久 Shell 会话。

    参考 Claude Code 的持久 Shell 设计：
        - 工作目录跨调用持久（通过追踪 cwd）
        - 环境变量跨调用持久（通过 source 状态文件）
        - 默认超时 120 秒

    实现方式：
        使用状态文件持久化环境变量。每次执行前 source 状态文件，
        执行后导出新的环境变量到状态文件。
    """

    _global_lock = threading.Lock()

    def __init__(self, cwd: str | None = None, timeout: int = 120):
        self._cwd = cwd or os.getcwd()
        self._timeout = timeout
        self._history: list[dict[str, Any]] = []
        # 环境变量状态文件
        self._env_file = Path(tempfile.gettempdir()) / f"butler_shell_env_{id(self)}.sh"
        self._env_file.write_text("# Butler shell environment state\n", encoding="utf-8")

    @property
    def cwd(self) -> str:
        return self._cwd

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def execute(self, command: str) -> dict[str, Any]:
        """
        在持久 shell 中执行命令。

        通过 source 状态文件恢复环境变量，执行命令后
        导出环境变量到状态文件以实现跨调用持久化。

        参数:
            command: 要执行的命令

        返回:
            dict: {
                "stdout": 标准输出,
                "stderr": 标准错误,
                "returncode": 返回码,
                "cwd": 执行后的工作目录,
            }
        """
        with self._global_lock:
            try:
                # 构建完整命令：source 环境文件 → 执行命令 → 导出环境 → 获取 pwd 和 rc
                env_file = str(self._env_file)
                wrapped = (
                    f"source {env_file} 2>/dev/null; "
                    f"{command}; "
                    f"__BUTLER_RC=$?; "
                    f"export -p > {env_file}; "
                    f"pwd; "
                    f"exit $__BUTLER_RC"
                )

                result = subprocess.run(
                    ["bash", "-c", wrapped],
                    capture_output=True,
                    text=True,
                    cwd=self._cwd,
                    timeout=self._timeout,
                )

                stdout = result.stdout
                stderr = result.stderr

                # 从 stdout 末尾提取 pwd（最后一行）
                lines = stdout.rstrip().split("\n") if stdout else []
                if lines and lines[-1].startswith("/"):
                    new_cwd = lines[-1]
                    self._cwd = new_cwd
                    # 移除 pwd 行从输出
                    stdout = "\n".join(lines[:-1])

                record = {
                    "command": command,
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": result.returncode,
                    "cwd": self._cwd,
                }
                self._history.append(record)

                return record

            except subprocess.TimeoutExpired:
                record = {
                    "command": command,
                    "stdout": "",
                    "stderr": f"Command timed out after {self._timeout}s",
                    "returncode": -1,
                    "cwd": self._cwd,
                }
                self._history.append(record)
                return record
            except Exception as e:
                record = {
                    "command": command,
                    "stdout": "",
                    "stderr": str(e),
                    "returncode": -1,
                    "cwd": self._cwd,
                }
                self._history.append(record)
                return record

    def __del__(self):
        """清理环境状态文件。"""
        try:
            if self._env_file.exists():
                self._env_file.unlink()
        except Exception:
            pass


# 全局持久 Shell 实例（每个 workspace 一个）
_shells: dict[str, PersistentShell] = {}


def _get_shell(workspace_root: str) -> PersistentShell:
    """获取或创建工作区的持久 Shell。"""
    if workspace_root not in _shells:
        _shells[workspace_root] = PersistentShell(cwd=workspace_root)
    return _shells[workspace_root]


def _register_bash_tool(registry: ToolRegistry, ws_root: Path) -> None:
    """注册 bash 工具（持久 Shell 会话）。"""

    def execute_bash(arguments: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        command = arguments["command"]
        timeout = arguments.get("timeout", 120)

        shell = _get_shell(str(ws_root))
        shell._timeout = timeout

        result = shell.execute(command)

        # 格式化输出
        output_parts: list[str] = []
        if result["stdout"]:
            output_parts.append(result["stdout"].rstrip())
        if result["stderr"]:
            output_parts.append(f"[stderr]: {result['stderr'].rstrip()}")
        output_parts.append(f"[exit code: {result['returncode']}]")
        output_parts.append(f"[cwd: {result['cwd']}]")

        success = result["returncode"] == 0
        return {
            "success": success,
            "content": "\n".join(output_parts),
            "metadata": {
                "returncode": result["returncode"],
                "cwd": result["cwd"],
            },
        }

    registry.register(
        handler=execute_bash,
        name="bash",
        description="Execute a bash command in a persistent shell session. Working directory and environment variables persist between calls.",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds. Default: 120.",
                },
            },
            "required": ["command"],
        },
        permission_level=PermissionLevel.REQUIRE_CONFIRM,
        is_destructive=False,
    )
