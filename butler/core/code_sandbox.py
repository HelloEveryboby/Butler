"""
Butler 代码沙箱 (CodeSandbox)。

对 LLM 生成的 Python 代码进行静态安全检查与受限执行。
解决 _execute_with_llm_interpreter 中代码直接在主进程执行的安全风险。
"""

from __future__ import annotations

import ast
import builtins as _builtins
import io
import logging
from contextlib import redirect_stdout
from typing import Any

logger = logging.getLogger(__name__)


class SecurityViolationError(Exception):
    """代码安全检查未通过。"""


class CodeSandbox:
    """
    受限 Python 执行环境。

    通过 AST 静态分析拦截危险导入和调用，在受限命名空间中执行代码。
    注意：沙箱不是绝对安全的容器。涉及系统操作的任务应走 BHL 二进制链路。
    """

    FORBIDDEN_MODULES = frozenset({
        "os", "sys", "subprocess", "shutil", "socket",
        "ctypes", "multiprocessing", "signal", "asyncio.subprocess",
        "importlib", "builtins",
    })

    FORBIDDEN_BUILTINS = frozenset({
        "open", "exec", "eval", "compile", "__import__",
        "globals", "locals", "vars", "dir", "getattr",
        "setattr", "delattr", "breakpoint", "exit", "quit",
    })

    def __init__(self, allowed_paths: list[str] | None = None):
        self._allowed_paths = [str(p) for p in (allowed_paths or [])]

    def validate(self, code: str) -> tuple[bool, str]:
        """
        静态检查：禁止导入危险模块、禁止调用危险内置函数。

        返回 (是否通过, 失败原因)。
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"语法错误: {e}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in self.FORBIDDEN_MODULES:
                        return False, f"禁止导入模块: {alias.name}"

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in self.FORBIDDEN_MODULES:
                        return False, f"禁止从模块导入: {node.module}"

            elif isinstance(node, ast.Call):
                func = node.func
                # 当配置了 allowed_paths 时，允许 open 调用（受控执行）
                forbidden = self.FORBIDDEN_BUILTINS
                if self._allowed_paths:
                    forbidden = forbidden - {"open"}
                if isinstance(func, ast.Name) and func.id in forbidden:
                    return False, f"禁止调用内置函数: {func.id}"

                # 检测 __import__ 调用
                if isinstance(func, ast.Attribute) and func.attr in {"system", "popen", "fork", "exec", "spawn"}:
                    return False, f"禁止调用危险方法: {func.attr}"

            elif isinstance(node, ast.Attribute) and (
                node.attr.startswith("__")
                and node.attr.endswith("__")
                and node.attr in {"__subclasses__", "__bases__", "__mro__", "__class__"}
            ):
                return False, f"禁止访问 dunder 属性: {node.attr}"

        return True, "通过"

    def execute(
        self,
        code: str,
        timeout: int = 10,
    ) -> dict[str, Any]:
        """
        在受限命名空间中执行代码。

        返回执行结果字典，包含 success / result / stdout / error 字段。
        """
        ok, msg = self.validate(code)
        if not ok:
            logger.warning(f"代码安全检查未通过: {msg}")
            return {"success": False, "error": f"安全检查未通过: {msg}", "stdout": ""}

        safe_builtins = {
            k: v for k, v in vars(_builtins).items()
            if k not in self.FORBIDDEN_BUILTINS
        }
        # 提供安全的 print
        print_buffer: list[str] = []
        safe_builtins["print"] = lambda *args, **kwargs: print_buffer.append(
            " ".join(str(a) for a in args)
        )
        # 提供受控的 open（如果配置了 allowed_paths）
        if self._allowed_paths:
            safe_builtins["open"] = self._make_safe_open()

        sandbox_globals: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",
            "result": None,
        }

        stdout_buffer = io.StringIO()
        try:
            with redirect_stdout(stdout_buffer):
                exec(compile(code, "<sandbox>", "exec"), sandbox_globals)
            return {
                "success": True,
                "result": sandbox_globals.get("result"),
                "stdout": stdout_buffer.getvalue() + "\n".join(print_buffer),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"{type(e).__name__}: {e}",
                "stdout": stdout_buffer.getvalue(),
                "result": None,
            }

    def _make_safe_open(self):
        """创建受路径限制的 open 函数。"""
        allowed = self._allowed_paths

        def safe_open(file, mode="r", *args, **kwargs):
            file_str = str(file)
            if not any(file_str.startswith(p) for p in allowed):
                raise PermissionError(f"沙箱禁止访问路径: {file_str}")
            return _builtins.open(file, mode, *args, **kwargs)

        return safe_open
