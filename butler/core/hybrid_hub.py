"""BHL Hub — 把用 C / C++ / Go / Rust 写的功能模块真正接到同一条链路上。

现状
----
`programs/*` 下的混合语言模块大多实现了同一种 JSON-RPC 行协议，但：
* 没有统一的构建入口，源码躺在仓库里，可执行文件并不存在；
* `HybridLinkClient` 只为 sysutil 创建过一个实例，其他语言模块从未被调用；
* 调用失败会静默走 Python 回退，调用方分不清「原生执行」还是「回退」。

本模块提供
----------
* 发现：扫描 `programs/*/manifest.json`，汇总语言、构建命令、方法表；
* 构建：按 manifest 里的 build 命令调用 gcc/g++/go/cargo（缺工具链则跳过）；
* 路由：`method -> [模块...]`，优先已构建/已运行的模块，支持显式指定 module；
* 执行：懒启动子进程、JSON-RPC 调用、超时/崩溃后自动重启；
* 回退：没有可用原生模块时走 `hybrid_fallbacks`，并明确标注 `via="fallback"`。

调用方拿到的永远是同一种信封：

    {"ok": True, "method": "factorize", "module": "hybrid_compute",
     "language": "cpp", "via": "native:cpp", "result": {...}, "elapsed_ms": 1.2}
"""

from __future__ import annotations

import atexit
import contextlib
import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .hybrid_fallbacks import dispatch_fallback
from .hybrid_link import HybridLinkClient

logger = logging.getLogger("BHLHub")

# 语言 -> 构建工具
_TOOLCHAIN = {
    "c": "gcc",
    "cpp": "g++",
    "c++": "g++",
    "go": "go",
    "rust": "cargo",
}

_DEFAULT_PROGRAMS_DIR = Path(__file__).resolve().parent.parent.parent / "programs"


class HybridHub:
    """混合语言模块的发现、构建、路由与调用中心。"""

    def __init__(
        self,
        programs_dir: str | None = None,
        fallback_enabled: bool = True,
        call_timeout: float = 15.0,
        build_timeout: float = 600.0,
    ):
        self.programs_dir = Path(programs_dir or _DEFAULT_PROGRAMS_DIR).resolve()
        self.fallback_enabled = fallback_enabled
        self.call_timeout = call_timeout
        self.build_timeout = build_timeout

        self._modules: dict[str, dict[str, Any]] = {}
        self._workers: dict[str, HybridLinkClient] = {}
        self._lock = threading.RLock()
        self.discover()

    # ------------------------------------------------------------------ 发现
    def discover(self) -> dict[str, dict[str, Any]]:
        """扫描 programs/*/manifest.json，返回 name -> spec。"""
        modules: dict[str, dict[str, Any]] = {}
        if not self.programs_dir.is_dir():
            logger.warning("BHL programs 目录不存在: %s", self.programs_dir)
            self._modules = modules
            return modules

        for manifest_path in sorted(self.programs_dir.glob("*/manifest.json")):
            try:
                spec = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("无法解析 %s: %s", manifest_path, exc)
                continue

            language = str(spec.get("language") or "").strip()
            entry = spec.get("entry") if isinstance(spec.get("entry"), dict) else {}
            executable = spec.get("executable") or entry.get("executable")
            if isinstance(executable, dict):
                # 例如 butler_runner 的 {"path": "runner", "args": [...]}
                executable = executable.get("path")
            raw_methods = spec.get("methods") or []
            if isinstance(raw_methods, dict):
                method_specs = raw_methods
                methods = list(raw_methods)
            else:
                method_specs = {}
                methods = [str(m) for m in raw_methods]
            protocol = str(spec.get("protocol") or "bhl").lower()
            if not language or not isinstance(executable, str) or not executable:
                continue

            build_command = spec.get("build") or spec.get("build_command") or ""
            if isinstance(build_command, dict):
                build_command = build_command.get("command", "")

            name = str(spec.get("name") or manifest_path.parent.name)
            program_dir = manifest_path.parent
            spec.update(
                {
                    "name": name,
                    "language": language,
                    "language_key": language.lower(),
                    "program_dir": program_dir,
                    "executable_path": (program_dir / executable).resolve(),
                    "build_command": build_command,
                    "sources": spec.get("source") or entry.get("source") or [],
                    "methods": methods,
                    "method_specs": method_specs,
                    "protocol": protocol,
                    "manifest_path": manifest_path,
                }
            )
            modules[name] = spec

        self._modules = modules
        return modules

    def modules(self) -> dict[str, dict[str, Any]]:
        return dict(self._modules)

    def method_index(self) -> dict[str, list[str]]:
        """method -> 模块名列表（按已构建优先、名称排序）。"""
        index: dict[str, list[str]] = {}
        for name, spec in self._modules.items():
            for method in spec.get("methods", []):
                index.setdefault(method, []).append(name)
        for names in index.values():
            names.sort(key=lambda n: (not self._is_built(self._modules[n]), n))
        return index

    # ------------------------------------------------------------------ 状态
    @staticmethod
    def _is_built(spec: dict[str, Any]) -> bool:
        path = spec.get("executable_path")
        return bool(path and Path(path).is_file() and os.access(path, os.X_OK))

    @staticmethod
    def _is_running(client: HybridLinkClient | None) -> bool:
        return bool(client and client.process and client.process.poll() is None)

    def status(self) -> list[dict[str, Any]]:
        """每个模块的构建/运行状态，供 CLI 与 Agent 工具展示。"""
        rows = []
        for name, spec in sorted(self._modules.items()):
            client = self._workers.get(name)
            rows.append(
                {
                    "name": name,
                    "language": spec["language"],
                    "protocol": spec.get("protocol", "bhl"),
                    "methods": list(spec.get("methods", [])),
                    "built": self._is_built(spec),
                    "running": self._is_running(client),
                    "pid": getattr(getattr(client, "process", None), "pid", None),
                    "executable": str(spec["executable_path"]),
                }
            )
        return rows

    # ------------------------------------------------------------------ 构建
    def build(self, name: str | None = None, force: bool = False) -> list[dict[str, Any]]:
        """按 manifest 构建一个或全部模块。返回每个模块的结果。"""
        targets = [name] if name else sorted(self._modules)
        results = []
        for module_name in targets:
            spec = self._modules.get(module_name)
            if spec is None:
                results.append({"module": module_name, "status": "error", "message": "模块未找到"})
                continue

            if self._is_built(spec) and not force:
                results.append(
                    {
                        "module": module_name,
                        "status": "skipped",
                        "message": "已构建（用 force 重编）",
                    }
                )
                continue

            command = spec.get("build_command") or ""
            if not command:
                results.append(
                    {
                        "module": module_name,
                        "status": "skipped",
                        "message": "manifest 未提供构建命令",
                    }
                )
                continue

            toolchain = _TOOLCHAIN.get(spec["language_key"])
            if toolchain and shutil.which(toolchain) is None:
                results.append(
                    {
                        "module": module_name,
                        "status": "skipped",
                        "message": f"缺少工具链 {toolchain}",
                    }
                )
                continue

            command = self._render_build_command(spec, command)
            started = time.time()
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(spec["program_dir"]),
                    capture_output=True,
                    text=True,
                    timeout=self.build_timeout,
                )
            except subprocess.TimeoutExpired:
                results.append({"module": module_name, "status": "error", "message": "构建超时"})
                continue
            except Exception as exc:
                results.append({"module": module_name, "status": "error", "message": str(exc)})
                continue

            output = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode != 0:
                results.append(
                    {
                        "module": module_name,
                        "status": "error",
                        "message": output.strip().splitlines()[-1]
                        if output.strip()
                        else f"退出码 {proc.returncode}",
                        "output": output[-2000:],
                    }
                )
                continue

            if not self._is_built(spec):
                # cargo 等把产物放在子目录，manifest 指向的路径不存在
                results.append(
                    {
                        "module": module_name,
                        "status": "error",
                        "message": f"构建完成但找不到可执行文件: {spec['executable_path']}",
                        "output": output[-1000:],
                    }
                )
                continue

            results.append(
                {
                    "module": module_name,
                    "status": "built",
                    "message": f"{spec['language']} 构建成功",
                    "seconds": round(time.time() - started, 1),
                }
            )
        return results

    @staticmethod
    def _render_build_command(spec: dict[str, Any], command: str) -> str:
        sources = spec.get("sources") or []
        if isinstance(sources, str):
            sources = [sources]
        if "{source}" in command:
            command = command.replace("{source}", " ".join(str(s) for s in sources))
        if "{output}" in command:
            command = command.replace("{output}", str(spec["executable_path"]))
        return command

    # ------------------------------------------------------------------ 调用
    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        module: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """调用一个方法，自动路由到实现它的原生模块。"""
        params = params or {}
        timeout = timeout or self.call_timeout
        started = time.time()

        candidates = [module] if module else self.method_index().get(method, [])
        if module and module not in self._modules:
            return self._envelope(False, method, module, None, f"模块不存在: {module}", started)

        last_error = None
        for candidate in candidates:
            spec = self._modules[candidate]
            if spec.get("protocol") == "cli":
                envelope = self._call_cli(spec, method, params, timeout, started)
                if envelope["ok"]:
                    return envelope
                last_error = envelope.get("error")
                continue

            client = self._ensure_worker(spec)
            if client is None:
                last_error = (
                    f"{candidate} 启动失败（可能未构建，或二进制与当前架构不匹配；"
                    f"运行 butler hybrid build {candidate} --force 重编）"
                )
                continue

            result = client.call(method, params, timeout=timeout)
            if isinstance(result, dict) and set(result.keys()) == {"error"}:
                last_error = str(result["error"].get("message") or result["error"])
                # 超时或进程死亡时重启，下一次调用仍有机会走原生
                if not self._is_running(client) or "timed out" in last_error:
                    self._stop_worker(candidate)
                continue

            return self._envelope(
                True, method, candidate, spec["language"], result=result, started=started
            )

        if self.fallback_enabled:
            try:
                fallback = dispatch_fallback(method, params)
            except Exception as exc:
                fallback = None
                last_error = f"{last_error or ''}; 回退失败: {exc}"

            if isinstance(fallback, dict) and set(fallback.keys()) == {"error"}:
                # dispatch_fallback 对未知方法会返回 error 信封，不能当成成功
                last_error = last_error or str(
                    fallback["error"].get("message") or fallback["error"]
                )
                fallback = None

            if fallback is not None:
                return self._envelope(
                    True,
                    method,
                    None,
                    "python",
                    result=fallback,
                    started=started,
                    via="fallback",
                )

        return self._envelope(
            False, method, module, None, last_error or f"没有模块实现方法 '{method}'", started
        )

    def _call_cli(
        self,
        spec: dict[str, Any],
        method: str,
        params: dict[str, Any],
        timeout: float,
        started: float,
    ) -> dict[str, Any]:
        """执行一次性 CLI 工具（protocol: "cli"），把 stdout 作为结果。"""
        method_spec = (spec.get("method_specs") or {}).get(method) or {}
        argv_template = method_spec.get("argv") or []
        if not argv_template:
            return self._envelope(
                False,
                method,
                spec["name"],
                spec["language"],
                "该 CLI 方法未声明 argv 模板",
                started,
            )

        argv = [self._render_arg(str(arg), params) for arg in argv_template]
        if not self._is_built(spec):
            return self._envelope(
                False,
                method,
                spec["name"],
                spec["language"],
                f"{spec['name']} 未构建，先运行 butler hybrid build {spec['name']}",
                started,
            )

        try:
            proc = subprocess.run(
                [str(spec["executable_path"]), *argv],
                cwd=str(spec["program_dir"]),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return self._envelope(
                False, method, spec["name"], spec["language"], "CLI 执行超时", started
            )
        except Exception as exc:
            return self._envelope(False, method, spec["name"], spec["language"], str(exc), started)

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            return self._envelope(
                False,
                method,
                spec["name"],
                spec["language"],
                detail[-1] if detail else f"退出码 {proc.returncode}",
                started,
            )

        return self._envelope(
            True,
            method,
            spec["name"],
            spec["language"],
            started=started,
            result={"stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip()},
        )

    @staticmethod
    def _render_arg(template: str, params: dict[str, Any]) -> str:
        """把 {key} 替换成参数值；缺省为空字符串。"""
        rendered = template
        for key, value in (params or {}).items():
            rendered = rendered.replace("{" + str(key) + "}", str(value))
        return rendered

    def _ensure_worker(self, spec: dict[str, Any]) -> HybridLinkClient | None:
        name = spec["name"]
        with self._lock:
            client = self._workers.get(name)
            if self._is_running(client):
                return client
            if client is not None:
                self._stop_worker(name)

            if not self._is_built(spec):
                logger.info("模块 %s 尚未构建: %s", name, spec["executable_path"])
                return None

            client = HybridLinkClient(
                str(spec["executable_path"]),
                cwd=str(spec["program_dir"]),
                fallback_enabled=False,
            )
            if not client.start():
                return None
            self._workers[name] = client
            logger.info("BHL worker 已启动: %s (%s)", name, spec["language"])
            return client

    def _stop_worker(self, name: str) -> None:
        client = self._workers.pop(name, None)
        if client is not None:
            with contextlib.suppress(Exception):
                client.stop()

    def stop(self) -> None:
        """停止所有 worker（进程退出/测试清理时调用）。"""
        for name in list(self._workers):
            self._stop_worker(name)

    @staticmethod
    def _envelope(
        ok: bool,
        method: str,
        module: str | None,
        language: str | None,
        error: str | None = None,
        started: float | None = None,
        result: Any = None,
        via: str | None = None,
    ) -> dict[str, Any]:
        elapsed = round((time.time() - started) * 1000, 1) if started else None
        if via is None:
            via = f"native:{language}" if ok and language else "none"
        envelope = {
            "ok": ok,
            "method": method,
            "module": module,
            "language": language,
            "via": via,
            "elapsed_ms": elapsed,
        }
        if ok:
            envelope["result"] = result
        else:
            envelope["error"] = error
        return envelope


_default_hub: HybridHub | None = None
_default_lock = threading.Lock()


def get_hub() -> HybridHub:
    """进程级单例，保证 worker 不会重复启动。"""
    global _default_hub
    with _default_lock:
        if _default_hub is None:
            _default_hub = HybridHub()
            # 进程退出时关闭子进程，避免残留 worker
            atexit.register(_default_hub.stop)
        return _default_hub
