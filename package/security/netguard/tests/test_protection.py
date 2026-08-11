"""防护接口测试"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_protection_analyze_clean(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/v1/protection/analyze",
        json={"source_ip": "1.2.3.4"},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is False
    assert data["action"] == "allow"


@pytest.mark.asyncio
async def test_protection_analyze_sql_injection(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/v1/protection/analyze",
        json={
            "source_ip": "5.6.7.8",
            "payload": "1' UNION SELECT * FROM users--",
        },
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is True
    assert any(d["attack_type"] == "SQL Injection" for d in data["detections"])


@pytest.mark.asyncio
async def test_protection_analyze_xss(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/v1/protection/analyze",
        json={
            "source_ip": "5.6.7.8",
            "payload": '<script>alert("xss")</script>',
        },
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is True
    assert any(d["attack_type"] == "XSS" for d in data["detections"])


@pytest.mark.asyncio
async def test_blocked_ips(client: AsyncClient, test_user):
    # 触发一次阻断
    await client.post(
        "/api/v1/protection/analyze",
        json={
            "source_ip": "9.9.9.9",
            "payload": "<script>alert(1)</script>",
        },
        headers=auth_headers(test_user),
    )

    resp = await client.get(
        "/api/v1/protection/blocked-ips",
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    assert "9.9.9.9" in resp.json()["blocked_ips"]


@pytest.mark.asyncio
async def test_unblock_ip(client: AsyncClient, test_user):
    # 先阻断
    await client.post(
        "/api/v1/protection/analyze",
        json={
            "source_ip": "7.7.7.7",
            "payload": "<script>alert(1)</script>",
        },
        headers=auth_headers(test_user),
    )

    # 解除
    resp = await client.post(
        "/api/v1/protection/unblock",
        json={"ip": "7.7.7.7"},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "unblocked"


@pytest.mark.asyncio
async def test_rules_read(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/v1/protection/rules",
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    rules = resp.json()["rules"]
    assert "ddos_threshold" in rules


@pytest.mark.asyncio
async def test_rules_update_requires_pro(client: AsyncClient, test_user):
    resp = await client.put(
        "/api/v1/protection/rules",
        json={"ddos_threshold": 200},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rules_update_pro(client: AsyncClient, pro_user):
    resp = await client.put(
        "/api/v1/protection/rules",
        json={"ddos_threshold": 500},
        headers=auth_headers(pro_user),
    )
    assert resp.status_code == 200
    assert resp.json()["rules"]["ddos_threshold"] == 500


@pytest.mark.asyncio
async def test_protection_history(client: AsyncClient, test_user):
    # 触发几次分析
    for i in range(3):
        await client.post(
            "/api/v1/protection/analyze",
            json={"source_ip": f"10.0.0.{i}"},
            headers=auth_headers(test_user),
        )

    resp = await client.get(
        "/api/v1/protection/history",
        params={"limit": 10},
        headers=auth_headers(test_user),
    )
    assert resp.status_code == 200
    assert len(resp.json()["records"]) == 3
