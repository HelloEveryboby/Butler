"""威胁情报接口测试"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_threat_lookup_malicious(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/v1/threat-intel/lookup",
        params={"target": "192.168.1.100"},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"] == "192.168.1.100"
    assert data["target_type"] == "ip"
    assert data["analysis"]["is_malicious"] is True
    assert data["analysis"]["score"] > 0.7


@pytest.mark.asyncio
async def test_threat_lookup_clean(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/v1/threat-intel/lookup",
        params={"target": "8.8.8.8"},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis"]["is_malicious"] is False


@pytest.mark.asyncio
async def test_threat_lookup_domain(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/v1/threat-intel/lookup",
        params={"target": "malware-c2.example.com"},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_type"] == "domain"
    assert data["analysis"]["is_malicious"] is True


@pytest.mark.asyncio
async def test_threat_history(client: AsyncClient, test_user):
    # 先查询几次
    for target in ["192.168.1.100", "8.8.8.8"]:
        await client.get(
            "/api/v1/threat-intel/lookup",
            params={"target": target},
            headers=auth_headers(test_user),
        )

    resp = await client.get(
        "/api/v1/threat-intel/history",
        params={"limit": 10},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["records"]) == 2


@pytest.mark.asyncio
async def test_threat_lookup_unauthorized(client: AsyncClient):
    resp = await client.get(
        "/api/v1/threat-intel/lookup",
        params={"target": "8.8.8.8"},
    )
    assert resp.status_code == 401
