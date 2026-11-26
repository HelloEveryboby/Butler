"""media / system / network 三个核心能力的注册与安全动作测试。

涉及 GUI、摄像头、删除、卸载的真实动作只校验 schema，不实际执行。
"""

from __future__ import annotations

import zipfile

import pytest

from butler.core.capabilities import capability_registry

CAPABILITIES = ("media", "system", "network")


def test_capabilities_registered_with_actions():
    names = set(capability_registry.names())
    for name in CAPABILITIES:
        assert name in names
        spec = capability_registry.get(name)
        assert spec is not None
        assert spec.actions, f"{name} 缺少 action 声明"
        schema = spec.tool_schema()["function"]["parameters"]
        assert schema["properties"]["action"]["enum"]
        assert "action" in schema["required"]


def test_destructive_capabilities_marked_caution():
    assert capability_registry.get("system").risk == "caution"
    assert capability_registry.get("network").risk == "caution"


def test_media_capture_schema_only():
    """截图/录屏动作只做 schema 校验，避免依赖 GUI 环境。"""
    spec = capability_registry.get("media")
    assert "capture" in spec.actions
    assert spec.properties["op"]["type"] == "string"


@pytest.fixture
def sample_zip(tmp_path):
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("hello.txt", "butler")
    yield archive
    archive.unlink(missing_ok=True)


def test_system_list_archive_reads_zip(sample_zip):
    result = capability_registry.execute(
        "system", "list_archive", {"archive_path": str(sample_zip)}
    )
    assert result["success"] is True
    assert "hello.txt" in result["result"]


def test_network_list_has_no_side_effects():
    result = capability_registry.execute("network", "list", {})
    assert "tasks" in result
    assert set(result["tasks"]) >= {"active", "waiting", "stopped"}


def test_media_status_is_safe():
    result = capability_registry.execute("media", "status", {})
    assert isinstance(result, dict)
    assert "initialized" in result or "state" in result
