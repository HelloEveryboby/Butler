"""BHL Hub 测试：真实子进程 JSON-RPC、方法路由、回退、崩溃重启、Agent 工具。"""

import json
import shutil
from pathlib import Path

import pytest

from butler.core.agent_runtime.native_tools import register_native_tools
from butler.core.agent_runtime.tool_registry import ToolRegistry
from butler.core.hybrid_hub import HybridHub
from butler.core.hybrid_scaffold import scaffold, supported_languages

WORKER = """#!/usr/bin/env python3
import json, os, sys, time

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    req = json.loads(line)
    method = req.get("method")
    params = req.get("params") or {}
    req_id = req.get("id")

    if method == "add":
        result = {"sum": params.get("a", 0) + params.get("b", 0)}
    elif method == "echo":
        result = {"who": params.get("who"), "tag": os.environ.get("WORKER_TAG", "")}
    elif method == "slow":
        time.sleep(float(params.get("seconds", 3)))
        result = {"done": True}
    elif method == "crash":
        os._exit(1)
    elif method == "exit":
        break
    else:
        print(json.dumps({"jsonrpc": "2.0", "error": {"code": -32601, "message": "method not found"}, "id": req_id}), flush=True)
        continue

    print(json.dumps({"jsonrpc": "2.0", "result": result, "id": req_id}), flush=True)
"""


def _make_module(root: Path, name: str, methods, tag=""):
    module_dir = root / name
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": name,
                "language": "python",
                "executable": "worker.py",
                "methods": methods,
            }
        ),
        encoding="utf-8",
    )
    worker = module_dir / "worker.py"
    worker.write_text(WORKER, encoding="utf-8")
    worker.chmod(0o755)
    return module_dir


def test_hub_discovers_and_calls_native_worker(tmp_path):
    _make_module(tmp_path, "math_mod", ["add"])

    hub = HybridHub(programs_dir=str(tmp_path))
    try:
        envelope = hub.call("add", {"a": 20, "b": 22})
    finally:
        hub.stop()

    assert envelope["ok"] is True
    assert envelope["via"] == "native:python"
    assert envelope["module"] == "math_mod"
    assert envelope["result"] == {"sum": 42}
    assert envelope["elapsed_ms"] is not None


def test_hub_routes_duplicate_method_by_explicit_module(tmp_path):
    _make_module(tmp_path, "mod_a", ["echo"])
    _make_module(tmp_path, "mod_b", ["echo"])

    hub = HybridHub(programs_dir=str(tmp_path))
    try:
        envelope = hub.call("echo", {"who": "butler"}, module="mod_b")
    finally:
        hub.stop()

    assert envelope["ok"] is True
    assert envelope["module"] == "mod_b"
    assert envelope["result"]["who"] == "butler"


def test_hub_falls_back_to_python(tmp_path):
    hub = HybridHub(programs_dir=str(tmp_path))

    envelope = hub.call("factorize", {"number": 12})

    assert envelope["ok"] is True
    assert envelope["via"] == "fallback"
    assert envelope["result"]["factors"] == [2, 2, 3]


def test_hub_reports_timeout_and_restarts_after_crash(tmp_path):
    _make_module(tmp_path, "flaky", ["slow", "crash", "add"])
    hub = HybridHub(programs_dir=str(tmp_path), call_timeout=2)

    try:
        slow = hub.call("slow", {"seconds": 5}, timeout=0.3)
        assert slow["ok"] is False
        assert "timed out" in slow["error"].lower()

        crashed = hub.call("crash", {}, timeout=1)
        assert crashed["ok"] is False

        recovered = hub.call("add", {"a": 1, "b": 2}, timeout=5)
        assert recovered["ok"] is True
        assert recovered["result"] == {"sum": 3}
    finally:
        hub.stop()


class FakeHub:
    def __init__(self):
        self.calls = []

    def call(self, method, params, module=None, timeout=None):
        self.calls.append((method, params, module))
        return {
            "ok": True,
            "method": method,
            "module": "hybrid_compute",
            "language": "cpp",
            "via": "native:cpp",
            "result": {"factors": [97]},
        }

    def status(self):
        return [
            {
                "name": "hybrid_compute",
                "language": "cpp",
                "built": True,
                "running": True,
                "methods": ["factorize"],
            }
        ]


def test_native_tools_wrap_hub():
    hub = FakeHub()
    registry = ToolRegistry()
    register_native_tools(registry, hub=hub)

    assert {"native_call", "native_status"} <= set(registry.list_names())

    result = registry.execute("native_call", {"method": "factorize", "params": {"number": 97}})

    assert result.success is True
    payload = json.loads(result.content)
    assert payload["via"] == "native:cpp"
    assert hub.calls == [("factorize", {"number": 97}, None)]

    status = registry.execute("native_status", {})
    assert status.success is True
    assert "hybrid_compute" in status.content


_TOOLCHAIN = {"c": "gcc", "cpp": "g++", "go": "go", "rust": "rustc", "python": "python3"}


@pytest.mark.parametrize("language", supported_languages())
def test_scaffold_build_and_ping(tmp_path, language):
    tool = _TOOLCHAIN[language]
    if shutil.which(tool) is None:
        pytest.skip(f"缺少工具链 {tool}")

    scaffold(f"demo_{language}", language, programs_dir=str(tmp_path))
    hub = HybridHub(programs_dir=str(tmp_path))

    try:
        build = hub.build(name=f"demo_{language}")
        assert build[0]["status"] in ("built", "skipped"), build[0]
        envelope = hub.call("ping", module=f"demo_{language}")
    finally:
        hub.stop()

    assert envelope["ok"] is True, envelope
    assert envelope["via"] == f"native:{language}"
    assert envelope["result"]["module"] == f"demo_{language}"


def test_scaffold_rejects_existing_directory(tmp_path):
    scaffold("dup", "python", programs_dir=str(tmp_path))

    with pytest.raises(ValueError):
        scaffold("dup", "python", programs_dir=str(tmp_path))


def test_cli_protocol_adapter_runs_one_shot_tool(tmp_path):
    module_dir = tmp_path / "cli_tool"
    module_dir.mkdir()
    (module_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": "cli_tool",
                "language": "python",
                "protocol": "cli",
                "executable": "tool.py",
                "methods": {
                    "echo_args": {"argv": ["{a}", "{b}"]},
                    "fail": {"argv": ["boom"]},
                },
            }
        ),
        encoding="utf-8",
    )
    tool = module_dir / "tool.py"
    tool.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if len(sys.argv) > 1 and sys.argv[1] == 'boom':\n"
        "    print('bad input', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "print('cli:' + ','.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)

    hub = HybridHub(programs_dir=str(tmp_path))
    try:
        ok = hub.call("echo_args", {"a": "x", "b": "y"})
        failed = hub.call("fail", {})
    finally:
        hub.stop()

    assert ok["ok"] is True, ok
    assert ok["via"] == "native:python"
    assert ok["result"]["stdout"] == "cli:x,y"

    assert failed["ok"] is False
    assert "bad input" in failed["error"]
