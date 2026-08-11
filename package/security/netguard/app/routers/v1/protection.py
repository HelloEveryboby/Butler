"""防护路由"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_store, require_tier
from app.models.user import User
from app.schemas.protection import (
    AnalyzeRequest,
    AnalyzeResponse,
    BlockedIPsResponse,
    ProtectionHistoryResponse,
    RulesResponse,
    UnblockRequest,
    UpdateRulesRequest,
)
from app.services.protection_service import ProtectionService
from app.store.base import StateStore

router = APIRouter(prefix="/api/v1/protection", tags=["Protection"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def protection_analyze(
    req: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    store: StateStore = Depends(get_store),
):
    service = ProtectionService(db, store)
    return await service.analyze(
        source_ip=req.source_ip,
        target_url=req.target_url,
        payload=req.payload,
        target_port=req.target_port,
        user_id=current_user.id,
    )


@router.get("/blocked-ips", response_model=BlockedIPsResponse)
async def get_blocked(
    current_user: User = Depends(get_current_user),
    store: StateStore = Depends(get_store),
):
    service = ProtectionService(None, store)
    blocked = await service.get_blocked_ips()
    return BlockedIPsResponse(blocked_ips=blocked)


@router.post("/unblock")
async def unblock(
    req: UnblockRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    store: StateStore = Depends(get_store),
):
    service = ProtectionService(db, store)
    return await service.unblock_ip(req.ip, current_user.id)


@router.get("/rules", response_model=RulesResponse)
async def read_rules(
    current_user: User = Depends(get_current_user),
    store: StateStore = Depends(get_store),
):
    service = ProtectionService(None, store)
    rules = await service.get_rules()
    return RulesResponse(status="ok", rules=rules)


@router.put("/rules", response_model=RulesResponse)
async def update_protection_rules(
    req: UpdateRulesRequest,
    current_user: User = Depends(require_tier("pro")),
    store: StateStore = Depends(get_store),
):
    service = ProtectionService(None, store)
    new_rules = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await service.update_rules(new_rules)
    return RulesResponse(status=result["status"], rules=result["rules"])


@router.get("/history", response_model=ProtectionHistoryResponse)
async def protection_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    store: StateStore = Depends(get_store),
):
    service = ProtectionService(db, store)
    records = await service.get_history(current_user.id, limit)
    return ProtectionHistoryResponse(records=records)
