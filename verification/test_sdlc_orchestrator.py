import pytest
import importlib.util
from pathlib import Path

# Load handle_request dynamically to support hyphenated folder names
path = Path(__file__).resolve().parent.parent / "skills" / "security" / "sdlc-security-orchestrator" / "main.py"
spec = importlib.util.spec_from_file_location("sdlc_security_orchestrator", str(path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
handle_request = module.handle_request

def test_sdlc_run_self_audit():
    res = handle_request("run_self_audit")
    assert res["status"] == "success"
    assert res["score"] == "B+"
    assert "docs/SECURITY_AUDIT_REPORT.md" in res["message"]

def test_sdlc_run_pipeline():
    res = handle_request("run_pipeline")
    assert res["status"] == "success"
    assert len(res["stages"]) == 4

    stages_names = [stage["name"] for stage in res["stages"]]
    assert any("SCA" in name for name in stages_names)
    assert any("SAST" in name for name in stages_names)
    assert any("DAST" in name for name in stages_names)
    assert any("System-Self-Audit" in name for name in stages_names)

    assert "Pipeline passed perfectly." in res["recommendation"]
