"""认证服务"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.security import (
    create_access_token,
    create_api_key,
    hash_password,
    verify_password,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, username: str, email: str, password: str) -> dict:
        """注册新用户，返回 token + api_key"""
        # 检查重复
        existing = await self.db.execute(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Username or email already registered")

        api_key = create_api_key()
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            tier="free",
            api_key=api_key,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        token = create_access_token(data={"sub": user.id})
        return {
            "access_token": token,
            "token_type": "bearer",
            "api_key": api_key,
            "tier": "free",
        }

    async def login(self, username: str, password: str) -> dict:
        """登录，返回 token + api_key"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("Account deactivated")

        token = create_access_token(data={"sub": user.id})
        return {
            "access_token": token,
            "token_type": "bearer",
            "api_key": user.api_key,
            "tier": user.tier,
        }

    async def get_user_by_api_key(self, api_key: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.api_key == api_key)
        )
        return result.scalar_one_or_none()

    async def upgrade_tier(self, user: User) -> dict:
        if user.tier == "pro":
            raise ValueError("Already on Pro plan")
        user.tier = "pro"
        await self.db.commit()
        return {"message": "Upgraded to Pro plan", "tier": "pro"}

    async def regenerate_api_key(self, user: User) -> str:
        new_key = create_api_key()
        user.api_key = new_key
        await self.db.commit()
        return new_key
