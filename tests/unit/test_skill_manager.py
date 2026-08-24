import pytest
import sys
import shutil
import tempfile
from pathlib import Path
from butler.core.skill_manager import SkillManager

@pytest.fixture
def temp_skills_dir():
    """Create a temporary skills directory and cleanup after test."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="test_skills_"))
    yield tmp_dir
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)

def test_skill_discovery_and_schema(temp_skills_dir):
    # 1. Create a mock valid skill with SKILL.md
    valid_skill_dir = temp_skills_dir / "test_valid_skill"
    valid_skill_dir.mkdir(parents=True)

    skill_md = valid_skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: test_valid_skill
description: A test valid skill for unit testing
parameters:
  query:
    type: string
    description: Search query
---
# Test Valid Skill Body
""", encoding="utf-8")

    main_py = valid_skill_dir / "main.py"
    main_py.write_text("""def handle_request(action, **kwargs):
    return {"status": "ok", "action": action}
""", encoding="utf-8")

    sm = SkillManager(skills_dir=temp_skills_dir)
    sm.load_skills()

    assert "test_valid_skill" in sm.manifests
    assert sm.skill_status.get("test_valid_skill") == "ENABLED"

    # Test export_openai_tools
    tools = sm.export_openai_tools()
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "test_valid_skill"
    assert tools[0]["function"]["description"] == "A test valid skill for unit testing"
    assert "query" in tools[0]["function"]["parameters"]["properties"]

def test_skill_unload_and_sys_modules_purge(temp_skills_dir):
    skill_dir = temp_skills_dir / "test_purge_skill"
    skill_dir.mkdir(parents=True)

    (skill_dir / "SKILL.md").write_text("""---
name: test_purge_skill
description: Test skill for sys.modules purging
---
""", encoding="utf-8")

    (skill_dir / "main.py").write_text("""def handle_request(action, **kwargs):
    return "purged_result"
""", encoding="utf-8")

    sm = SkillManager(skills_dir=temp_skills_dir)
    sm.load_skills()

    # Load python runtime
    assert sm._load_python_runtime("test_purge_skill") is True
    assert "skills.test_purge_skill" in sys.modules

    # Now unload
    sm.unload_skill("test_purge_skill")
    assert "test_purge_skill" not in sm.manifests
    assert "skills.test_purge_skill" not in sys.modules

def test_bad_skill_error_isolation(temp_skills_dir):
    skill_dir = temp_skills_dir / "bad_skill"
    skill_dir.mkdir(parents=True)

    (skill_dir / "SKILL.md").write_text("""---
name: bad_skill
description: A faulty skill with broken python code
---
""", encoding="utf-8")

    # Broken python code syntax
    (skill_dir / "main.py").write_text("""def handle_request(action, **kwargs
    syntax error here!
""", encoding="utf-8")

    sm = SkillManager(skills_dir=temp_skills_dir)
    sm.load_skills()

    # Try loading runtime for faulty skill
    res = sm._load_python_runtime("bad_skill")
    assert res is False
    assert sm.skill_status.get("bad_skill") == "DISABLED"

    # Execution should be rejected gracefully
    exec_res = sm.execute("bad_skill", "run")
    assert "DISABLED" in exec_res
