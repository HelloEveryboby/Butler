"""统计接口测试"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_dashboard_empty(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/v1/stats/dashboard",
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "free"
    assert data["stats"]["threat_lookups"] == 0
    assert data["stats"]["scans"] == 0


@pytest.mark.asyncio
async def test_dashboard_with_data(client: AsyncClient, test_user):
    # 先做一次威胁查询
    await client.get(
        "/api/v1/threat-intel/lookup",
        params={"target": "8.8.8.8"},
        headers=auth_headers(test_user),
    )

    resp = await client.get(
        "/api/v1/stats/dashboard",
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["threat_lookups"] == 1


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "endpoints" in data
