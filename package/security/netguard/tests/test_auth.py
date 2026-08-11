"""认证接口测试"""

import pytest
from httpx import AsyncClient

from tests.conftest import api_key_headers, auth_headers


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "api_key" in data
    assert data["tier"] == "free"


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    payload = {
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "securepass123",
    }
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "shortpw",
            "email": "short@example.com",
            "password": "123",
        },
    )
    assert resp.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    # 先注册
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "securepass123",
        },
    )
    # 登录
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "loginuser", "password": "securepass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "wrongpw",
            "email": "wrong@example.com",
            "password": "securepass123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "wrongpw", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, test_user):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["tier"] == "free"


@pytest.mark.asyncio
async def test_get_me_with_api_key(client: AsyncClient, test_user):
    resp = await client.get("/api/v1/auth/me", headers=api_key_headers(test_user))
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upgrade(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/v1/auth/upgrade", headers=auth_headers(test_user)
    )
    assert resp.status_code == 200
    assert resp.json()["tier"] == "pro"


@pytest.mark.asyncio
async def test_regenerate_api_key(client: AsyncClient, test_user):
    old_key = test_user.api_key
    resp = await client.post(
        "/api/v1/auth/regenerate-api-key", headers=auth_headers(test_user)
    )
    assert resp.status_code == 200
    assert resp.json()["api_key"] != old_key
