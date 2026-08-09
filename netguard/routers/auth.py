from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models.models import User
from auth.auth import hash_password, verify_password, create_access_token, create_api_key, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    api_key: str
    tier: str


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(req.username) < 3 or len(req.username) > 64:
        raise HTTPException(status_code=400, detail="Username must be 3-64 characters")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = await db.execute(select(User).where((User.username == req.username) | (User.email == req.email)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already registered")

    api_key = create_api_key()
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        tier="free",
        api_key=api_key,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": user.id})
    return TokenResponse(access_token=token, api_key=api_key, tier="free")


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account deactivated")

    token = create_access_token(data={"sub": user.id})
    return TokenResponse(access_token=token, api_key=user.api_key, tier=user.tier)


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "tier": current_user.tier,
        "api_key": current_user.api_key,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
    }


@router.post("/upgrade")
async def upgrade_tier(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.tier == "pro":
        raise HTTPException(status_code=400, detail="Already on Pro plan")
    current_user.tier = "pro"
    await db.commit()
    return {"message": "Upgraded to Pro plan", "tier": "pro"}


@router.post("/regenerate-api-key")
async def regenerate_api_key(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    new_key = create_api_key()
    current_user.api_key = new_key
    await db.commit()
    return {"api_key": new_key}
