"""测试配置 + 公共 fixtures"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, get_db
from app.utils.security import create_access_token, create_api_key, hash_password

# 导入所有模型以注册到 Base.metadata
from app.models import user, threat, scan, traffic, protection  # noqa: F401

# 使用文件 SQLite 做测试（避免 in-memory 多连接问题）
import tempfile
import os

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_path}"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    try:
        os.unlink(_test_db_path)
    except OSError:
        pass


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """创建测试引擎并建表，测试结束后销毁"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client(db_engine):
    """测试用 HTTP 客户端"""
    from main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """直接获取 DB session"""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户并返回 user 对象"""
    from app.models.user import User

    api_key = create_api_key()
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("password123"),
        tier="free",
        api_key=api_key,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def pro_user(db_session: AsyncSession):
    """创建 Pro 测试用户"""
    from app.models.user import User

    api_key = create_api_key()
    user = User(
        username="prouser",
        email="pro@example.com",
        hashed_password=hash_password("password123"),
        tier="pro",
        api_key=api_key,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def auth_headers(user) -> dict:
    """生成认证 headers"""
    token = create_access_token(data={"sub": user.id})
    return {"Authorization": f"Bearer {token}"}


def api_key_headers(user) -> dict:
    """生成 API Key headers"""
    return {"X-API-Key": user.api_key}
