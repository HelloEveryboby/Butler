"""plugin_market 安装/体检/生命周期测试（stdlib unittest，无外部依赖）。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from butler_dsh.plugin_market import (  # noqa: E402
    MarketError,
    PluginMarket,
    glob_to_regex,
)


def make_plugin(dirpath: Path, *, name="demo-tool", js_code='console.log("hi")', meta=None) -> Path:
    """造一个市场插件形态的目录。"""
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "package.json").write_text(
        json.dumps(meta or {"name": name, "version": "1.2.3", "description": "demo"}), encoding="utf-8"
    )
    (dirpath / "index.js").write_text(js_code, encoding="utf-8")
    return dirpath


class TestGlobToRegex(unittest.TestCase):
    def test_glob_matching(self):
        import re

        rx = re.compile(glob_to_regex("github:trusted/*"))
        self.assertTrue(rx.match("github:trusted/plugin"))
        self.assertFalse(rx.match("github:evil/plugin"))
        self.assertTrue(re.compile(glob_to_regex("*")).match("anything"))


class TestInstallLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plugins_dir = Path(self.tmp.name) / "plugins"
        self.market = PluginMarket(self.plugins_dir)
        self.src = make_plugin(Path(self.tmp.name) / "src-plugin")

    def test_install_records_manifest(self):
        info = self.market.install(str(self.src))
        self.assertEqual(info.name, "demo-tool")
        self.assertEqual(info.version, "1.2.3")
        self.assertTrue((self.plugins_dir / "demo-tool" / "index.js").exists())

        installed = self.market.list_installed()
        self.assertEqual(len(installed), 1)
        self.assertEqual(installed[0]["name"], "demo-tool")
        self.assertTrue(installed[0]["enabled"])
        self.assertEqual(len(installed[0]["sha256"]), 64)  # 目录 hash

    def test_lifecycle_disable_enable_uninstall(self):
        self.market.install(str(self.src))
        self.assertTrue(self.market.set_enabled("demo-tool", False))
        self.assertFalse(self.market.list_installed()[0]["enabled"])
        self.assertTrue(self.market.set_enabled("demo-tool", True))
        self.assertTrue(self.market.uninstall("demo-tool"))
        self.assertFalse(self.market.uninstall("demo-tool"))  # 幂等
        self.assertFalse((self.plugins_dir / "demo-tool").exists())

    def test_missing_local_path(self):
        with self.assertRaises(MarketError):
            self.market.install(str(Path(self.tmp.name) / "nope"))


class TestPreflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_ui_skin_rejected_by_default(self):
        src = make_plugin(
            Path(self.tmp.name) / "skin",
            name="cool-skin",
            meta={"name": "cool-skin", "version": "1.0", "description": "a pretty skin"},
        )
        market = PluginMarket(Path(self.tmp.name) / "p1")
        with self.assertRaises(MarketError) as ctx:
            market.install(str(src))
        self.assertIn("UI/皮肤", str(ctx.exception))

    def test_ui_skin_allowed_with_flag(self):
        src = make_plugin(
            Path(self.tmp.name) / "skin",
            name="cool-skin",
            meta={"name": "cool-skin", "version": "1.0", "description": "skin"},
        )
        market = PluginMarket(Path(self.tmp.name) / "p2", allow_ui=True)
        info = market.install(str(src))
        self.assertEqual(info.kind, "ui-skin")

    def test_source_whitelist(self):
        src = make_plugin(Path(self.tmp.name) / "wl")
        market = PluginMarket(
            Path(self.tmp.name) / "p3", allowed_sources=["github:trusted/*"]
        )
        with self.assertRaises(MarketError) as ctx:
            market.install(str(src))
        self.assertIn("白名单", str(ctx.exception))

    def test_risk_hints_detected(self):
        src = make_plugin(
            Path(self.tmp.name) / "risky",
            js_code='const cp = require("child_process"); cp.exec("rm -rf /"); fetch("http://x");',
        )
        market = PluginMarket(Path(self.tmp.name) / "p4")
        info = market.install(str(src))
        joined = "；".join(info.risk_hints)
        self.assertIn("系统命令", joined)
        self.assertIn("网络", joined)

    def test_provider_kind_warning(self):
        src = make_plugin(
            Path(self.tmp.name) / "prov",
            name="my-model-provider",
            meta={"name": "my-model-provider", "version": "1.0", "description": "llm provider"},
        )
        market = PluginMarket(Path(self.tmp.name) / "p5")
        info = market.install(str(src))
        self.assertEqual(info.kind, "provider")
        self.assertTrue(any("冲突" in w for w in info.warnings))


class TestSkillRegistry(unittest.TestCase):
    def test_sync_and_tools_for_llm(self):
        from butler_dsh.skill_registry import SkillRegistry

        reg = SkillRegistry()
        reg.sync([
            {"name": "b.tool", "description": "b", "risk": "read_only", "source": "p"},
            {"name": "a.tool", "description": "a", "risk": "write", "source": "p",
             "schema": {"type": "object", "properties": {"x": {"type": "string"}}}},
        ])
        tools = reg.tools_for_llm()
        self.assertEqual([t["function"]["name"] for t in tools], ["a.tool", "b.tool"])
        self.assertEqual(tools[0]["function"]["parameters"]["type"], "object")
        self.assertEqual(tools[1]["function"]["parameters"], {"type": "object", "properties": {}})
        self.assertEqual(reg.risk_summary(), {"write": 1, "read_only": 1})

    def test_disable_hides_tool(self):
        from butler_dsh.skill_registry import SkillRegistry

        reg = SkillRegistry()
        reg.sync([{"name": "t", "description": "d", "risk": "unknown", "source": "p"}])
        self.assertTrue(reg.disable("t"))
        self.assertEqual(reg.tools_for_llm(), [])
        self.assertTrue(reg.enable("t"))
        self.assertEqual(len(reg.tools_for_llm()), 1)

    def test_incremental_upsert_remove(self):
        from butler_dsh.skill_registry import SkillRegistry

        reg = SkillRegistry()
        reg.upsert([{"name": "t1", "description": "d", "risk": "read_only", "source": "p"}])
        reg.upsert([{"name": "t2", "description": "d", "risk": "read_only", "source": "p"}])
        reg.remove(["t1"])
        self.assertEqual([c["name"] for c in reg.capabilities()], ["t2"])


if __name__ == "__main__":
    unittest.main()
