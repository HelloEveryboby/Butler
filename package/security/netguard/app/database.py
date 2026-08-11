"""数据库引擎、会话工厂、依赖注入"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


async def get_db():
    """FastAPI 依赖：提供 async session，请求结束后自动关闭"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """启动时创建所有表（开发用，生产应走 Alembic）"""
    from app.models import (
        user,
        threat,
        scan,
        traffic,
        protection,
        blacklist,
        schedule,
        task,
    )  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
