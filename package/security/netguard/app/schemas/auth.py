"""认证 Schema"""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., max_length=128)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    api_key: str
    tier: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    tier: str
    api_key: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class UpgradeResponse(BaseModel):
    message: str
    tier: str


class ApiKeyResponse(BaseModel):
    api_key: str
