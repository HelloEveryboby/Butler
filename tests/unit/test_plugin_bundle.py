# -*- coding: utf-8 -*-
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from butler.core.plugin_bundle import (
    detect_bundle,
    discover_plugin_roots,
    install_plugin,
    list_plugins,
    remove_plugin,
)


@pytest.fixture
def bundle():
    tmp = Path(tempfile.mkdtemp(prefix="test_plugin_bundle_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _make_dsh_bundle(root: Path):
    (root / "package.json").write_text(json.dumps({
        "name": "@acme/dsh-demo",
        "version": "1.0.0",
        "description": "demo plugin",
        "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
    }), encoding="utf-8")

    skill_dir = root / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: demo skill\n---\n# demo\n", encoding="utf-8"
    )

    (root / "commands").mkdir()
    (root / "commands" / "hello.md").write_text(
        "---\nname: hello\ndescription: hello command\n---\n# hello\n", encoding="utf-8"
    )


def test_detect_bundle(bundle):
    _make_dsh_bundle(bundle)
    info = detect_bundle(bundle)
    assert info["type"] == "dsh"
    assert info["version"] == "1.0.0"
    assert [p.name for p in info["skills"]] == ["skills"]
    assert [p.name for p in info["commands"]] == ["commands"]


def test_install_and_remove_plugin(bundle):
    src = bundle / "src"
    src.mkdir()
    _make_dsh_bundle(src)

    plugins_dir = bundle / "plugins"
    marker = install_plugin(str(src), plugins_dir=plugins_dir)
    assert marker["name"] == "acme-dsh-demo"
    assert marker["assets"]["skills"] == ["skills"]
    assert marker["assets"]["commands"] == ["commands"]

    listed = list_plugins(plugins_dir)
    assert [p["name"] for p in listed] == ["acme-dsh-demo"]

    roots = discover_plugin_roots(plugins_dir)
    kinds = {(r["kind"], r["prefix"]) for r in roots}
    assert ("skills", None) in kinds
    assert ("commands", "acme-dsh-demo-") in kinds

    assert remove_plugin("acme-dsh-demo", plugins_dir=plugins_dir) is True
    assert list_plugins(plugins_dir) == []


def test_install_rejects_bundle_without_assets(bundle):
    src = bundle / "empty"
    src.mkdir()
    (src / "package.json").write_text(json.dumps({"name": "empty"}), encoding="utf-8")
    with pytest.raises(ValueError):
        install_plugin(str(src), plugins_dir=bundle / "plugins")
