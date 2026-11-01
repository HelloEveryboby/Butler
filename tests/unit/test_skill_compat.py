# -*- coding: utf-8 -*-
import shutil
import tempfile
from pathlib import Path

import pytest

from butler.core.skill_registry import (
    iter_root_entries,
    parse_invocation_policy,
    resolve_skill_roots,
)
from butler.core.plugin_bundle import install_plugin
from butler.core.skill_manager import SkillManager


@pytest.fixture
def project():
    tmp = Path(tempfile.mkdtemp(prefix="test_skill_compat_"))
    (tmp / ".git").mkdir()
    (tmp / "skills").mkdir()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _write_skill(path: Path, name: str, frontmatter: str = ""):
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n{frontmatter}---\n# body\n",
        encoding="utf-8",
    )


def test_resolve_roots_includes_standard_agent_dirs(project):
    _write_skill(project / "skills" / "native", "native")
    _write_skill(project / ".agents" / "skills" / "shared", "shared")
    _write_skill(project / ".dsh" / "skills" / "dsh_skill", "dsh_skill")

    roots = resolve_skill_roots(project, include_user=False, include_plugins=False)
    sources = [r["source"] for r in roots]
    assert sources == ["butler", "project-dsh", "project-agents"]
    assert roots[0]["rank"] == 0
    assert roots[1]["rank"] == 100
    assert roots[2]["rank"] == 200


def test_discovery_first_wins_and_flat_md(project):
    _write_skill(project / "skills" / "dup", "dup")
    _write_skill(project / ".agents" / "skills" / "dup", "dup")
    flat = project / ".agents" / "skills" / "flat_cmd.md"
    flat.write_text("---\nname: flat_cmd\ndescription: flat\n---\n", encoding="utf-8")

    roots = resolve_skill_roots(project, include_user=False, include_plugins=False)
    entries = []
    seen = set()
    for root in roots:
        for skill_id, skill_path in iter_root_entries(root):
            if skill_id in seen:
                continue
            seen.add(skill_id)
            entries.append((skill_id, skill_path, root["source"]))

    by_id = {sid: (path, src) for sid, path, src in entries}
    assert by_id["dup"][1] == "butler"
    assert by_id["flat_cmd"][1] == "project-agents"
    assert by_id["flat_cmd"][0].suffix == ".md"


def test_invocation_policy_parsing():
    assert parse_invocation_policy({}) == (True, True, True)
    assert parse_invocation_policy({"disable-model-invocation": "yes"}) == (False, True, True)
    assert parse_invocation_policy({"user-invocable": "off"}) == (True, False, True)
    assert parse_invocation_policy({"disable-model-invocation": "maybe"})[2] is False
    assert parse_invocation_policy({"disableModelInvocation": True})[2] is False


def test_skill_manager_loads_external_root_and_filters_model_visibility(project):
    _write_skill(project / "skills" / "native", "native")
    _write_skill(
        project / ".agents" / "skills" / "hidden",
        "hidden",
        "disable-model-invocation: true\n",
    )

    sm = SkillManager(skills_dir=Path(project / "skills"))
    sm.project_root = project
    sm.include_external_roots = True
    sm.load_skills()

    assert sm.manifests["native"]["source"] == "butler"
    assert sm.manifests["hidden"]["source"] == "project-agents"
    assert sm.manifests["hidden"]["model_invocable"] is False

    tool_names = [t["function"]["name"] for t in sm.export_openai_tools()]
    assert "hidden" not in tool_names
    assert "native" in tool_names


def test_skill_manager_loads_plugin_assets(project):
    src = project / "bundle-src"
    (src / "skills" / "demo-skill").mkdir(parents=True)
    (src / "skills" / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: from plugin\n---\n", encoding="utf-8"
    )
    (src / "commands").mkdir()
    (src / "commands" / "hello.md").write_text(
        "---\nname: hello\ndescription: hello\n---\n", encoding="utf-8"
    )
    (src / "package.json").write_text(
        '{"name": "@acme/demo", "version": "1.0.0", "dsh": {"bundle": {"patch": "./cordis.patch.yml"}}}',
        encoding="utf-8",
    )
    install_plugin(str(src), plugins_dir=project / "plugins")

    sm = SkillManager(skills_dir=Path(project / "skills"))
    sm.project_root = project
    sm.include_external_roots = True
    sm.load_skills()

    assert sm.manifests["demo-skill"]["source"] == "plugin:acme-demo"
    assert sm.manifests["acme-demo-hello"]["kind"] == "commands"
    assert sm.manifests["acme-demo-hello"]["source"] == "plugin:acme-demo"
