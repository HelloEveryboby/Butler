"""认证路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ApiKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpgradeResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        return await service.register(req.username, req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        return await service.login(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        tier=current_user.tier,
        api_key=current_user.api_key,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade_tier(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    try:
        return await service.upgrade_tier(current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/regenerate-api-key", response_model=ApiKeyResponse)
async def regenerate_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    new_key = await service.regenerate_api_key(current_user)
    return ApiKeyResponse(api_key=new_key)
