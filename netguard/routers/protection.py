from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.models import User
from auth.auth import get_current_user
from modules.protection import (
    analyze_request, get_blocked_ips, unblock_ip,
    get_protection_history, update_rules, get_rules,
)

router = APIRouter(prefix="/api/v1/protection", tags=["Protection"])


class AnalyzeRequest(BaseModel):
    source_ip: str
    target_url: str = ""
    payload: str = ""
    target_port: int = 0


class UnblockRequest(BaseModel):
    ip: str


class UpdateRulesRequest(BaseModel):
    ddos_threshold: int = None
    ddos_window_seconds: int = None
    port_scan_threshold: int = None
    brute_force_threshold: int = None
    brute_force_window_seconds: int = None


@router.post("/analyze")
async def protection_analyze(
    req: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await analyze_request(
        source_ip=req.source_ip,
        target_url=req.target_url,
        payload=req.payload,
        target_port=req.target_port,
        user_id=current_user.id,
        db=db,
    )


@router.get("/blocked-ips")
async def get_blocked(current_user: User = Depends(get_current_user)):
    return {"blocked_ips": await get_blocked_ips()}


@router.post("/unblock")
async def unblock(
    req: UnblockRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await unblock_ip(req.ip, current_user.id, db)


@router.get("/rules")
async def read_rules(current_user: User = Depends(get_current_user)):
    return get_rules()


@router.put("/rules")
async def update_protection_rules(
    req: UpdateRulesRequest,
    current_user: User = Depends(get_current_user),
):
    if current_user.tier != "pro":
        raise HTTPException(status_code=403, detail="Only Pro tier can modify rules")
    new_rules = {k: v for k, v in req.model_dump().items() if v is not None}
    return update_rules(new_rules)


@router.get("/history")
async def protection_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"records": await get_protection_history(current_user.id, db, limit)}
