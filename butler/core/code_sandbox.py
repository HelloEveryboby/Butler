"""
Butler 代码沙箱 (CodeSandbox)。

对 LLM 生成的 Python 代码进行静态安全检查与受限执行。
解决 _execute_with_llm_interpreter 中代码直接在主进程执行的安全风险。

增强：
- 内存限制：通过 resource.setrlimit 限制进程内存
- CPU 时间限制：通过 resource.setrlimit 限制 CPU 秒数
- 子进程隔离：可选在独立进程中执行，主进程不受影响
"""

from __future__ import annotations

import ast
import builtins as _builtins
import io
import logging
import resource
import signal
import subprocess
import sys
import tempfile
import threading
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 资源限制常量（仅 Unix 有效，Windows 下自动降级）
_DEFAULT_MEMORY_LIMIT = 256 * 1024 * 1024  # 256 MB
_DEFAULT_CPU_LIMIT = 5                       # 5 秒 CPU 时间
_DEFAULT_WALL_TIMEOUT = 10                   # 10 秒墙钟超时


class SecurityViolationError(Exception):
    """代码安全检查未通过。"""


class CodeSandbox:
    """
    受限 Python 执行环境。

    通过 AST 静态分析拦截危险导入和调用，在受限命名空间中执行代码。
    支持内存和 CPU 资源限制（Unix），以及子进程隔离执行。
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

    def __init__(
        self,
        allowed_paths: list[str] | None = None,
        memory_limit: int = _DEFAULT_MEMORY_LIMIT,
        cpu_limit: int = _DEFAULT_CPU_LIMIT,
    ):
        self._allowed_paths = [str(p) for p in (allowed_paths or [])]
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit

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
                forbidden = self.FORBIDDEN_BUILTINS
                if self._allowed_paths:
                    forbidden = forbidden - {"open"}
                if isinstance(func, ast.Name) and func.id in forbidden:
                    return False, f"禁止调用内置函数: {func.id}"

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
        timeout: int = _DEFAULT_WALL_TIMEOUT,
        use_subprocess: bool = False,
    ) -> dict[str, Any]:
        """
        在受限命名空间中执行代码。

        参数:
            code: 要执行的 Python 代码
            timeout: 墙钟超时（秒）
            use_subprocess: 是否在独立子进程中执行（更安全但更慢）

        返回执行结果字典，包含 success / result / stdout / error 字段。
        """
        ok, msg = self.validate(code)
        if not ok:
            logger.warning(f"代码安全检查未通过: {msg}")
            return {"success": False, "error": f"安全检查未通过: {msg}", "stdout": ""}

        if use_subprocess:
            return self._execute_in_subprocess(code, timeout)
        return self._execute_in_process(code, timeout)

    def _execute_in_process(self, code: str, timeout: int) -> dict[str, Any]:
        """在当前进程中执行代码（不设置 RLIMIT，避免影响主进程）。"""
        safe_builtins = {
            k: v for k, v in vars(_builtins).items()
            if k not in self.FORBIDDEN_BUILTINS
        }
        print_buffer: list[str] = []
        safe_builtins["print"] = lambda *args, **kwargs: print_buffer.append(
            " ".join(str(a) for a in args)
        )
        if self._allowed_paths:
            safe_builtins["open"] = self._make_safe_open()

        sandbox_globals: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",
            "result": None,
        }

        stdout_buffer = io.StringIO()
        exec_done = threading.Event()
        exec_result: dict[str, Any] = {}

        def _run():
            try:
                with redirect_stdout(stdout_buffer):
                    exec(compile(code, "<sandbox>", "exec"), sandbox_globals)
                exec_result["ok"] = True
                exec_result["result"] = sandbox_globals.get("result")
            except Exception as e:
                exec_result["ok"] = False
                exec_result["error"] = f"{type(e).__name__}: {e}"
            finally:
                exec_done.set()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        exec_done.wait(timeout=timeout)

        if not exec_done.is_set():
            # 线程仍在运行（超时），daemon 线程会在主进程退出时终止
            return {
                "success": False,
                "error": f"执行超时（{timeout}s）",
                "stdout": stdout_buffer.getvalue(),
                "result": None,
            }

        if exec_result.get("ok"):
            return {
                "success": True,
                "result": exec_result.get("result"),
                "stdout": stdout_buffer.getvalue() + "\n".join(print_buffer),
                "error": None,
            }
        return {
            "success": False,
            "error": exec_result.get("error", "未知错误"),
            "stdout": stdout_buffer.getvalue() + "\n".join(print_buffer),
            "result": None,
        }

    def _execute_in_subprocess(self, code: str, timeout: int) -> dict[str, Any]:
        """在独立子进程中执行代码（更安全的隔离）。"""
        wrapper = (
            "import resource, sys\n"
            f"resource.setrlimit(resource.RLIMIT_AS, ({self._memory_limit}, {self._memory_limit}))\n"
            f"resource.setrlimit(resource.RLIMIT_CPU, ({self._cpu_limit}, {self._cpu_limit}))\n"
            "import json\n"
            f"_code = {repr(code)}\n"
            "_ns = {'__name__': '__sandbox__'}\n"
            "try:\n"
            "    exec(compile(_code, '<sandbox>', 'exec'), _ns)\n"
            "    print(json.dumps({'success': True, 'result': str(_ns.get('result')), 'error': None}))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'success': False, 'result': None, 'error': f'{type(e).__name__}: {e}'}))\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(wrapper)
            script_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            import json
            try:
                output = json.loads(result.stdout.strip().split("\n")[-1])
                output["stdout"] = result.stdout
                return output
            except (json.JSONDecodeError, IndexError):
                return {
                    "success": False,
                    "error": result.stderr or "子进程执行无输出",
                    "stdout": result.stdout,
                    "result": None,
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"子进程执行超时（{timeout}s）",
                "stdout": "",
                "result": None,
            }
        finally:
            Path(script_path).unlink(missing_ok=True)

    def _apply_resource_limits(self) -> None:
        """在当前进程设置内存和 CPU 限制（仅 Unix）。"""
        try:
            if hasattr(resource, "RLIMIT_AS"):
                resource.setrlimit(resource.RLIMIT_AS, (self._memory_limit, self._memory_limit))
            if hasattr(resource, "RLIMIT_CPU"):
                resource.setrlimit(resource.RLIMIT_CPU, (self._cpu_limit, self._cpu_limit))
            logger.debug(f"资源限制已设置: memory={self._memory_limit // 1024 // 1024}MB, cpu={self._cpu_limit}s")
        except (ValueError, resource.error) as e:
            logger.warning(f"无法设置资源限制（可能不支持）: {e}")

    def _make_safe_open(self):
        """创建受路径限制的 open 函数。"""
        allowed = self._allowed_paths

        def safe_open(file, mode="r", *args, **kwargs):
            file_str = str(file)
            if not any(file_str.startswith(p) for p in allowed):
                raise PermissionError(f"沙箱禁止访问路径: {file_str}")
            return _builtins.open(file, mode, *args, **kwargs)

        return safe_open
