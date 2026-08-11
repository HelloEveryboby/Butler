"""威胁情报路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_store
from app.models.user import User
from app.schemas.threat import ThreatHistoryResponse, ThreatLookupResponse
from app.services.threat_service import ThreatIntelService
from app.store.base import StateStore

router = APIRouter(prefix="/api/v1/threat-intel", tags=["Threat Intelligence"])


@router.get("/lookup", response_model=ThreatLookupResponse)
async def threat_lookup(
    target: str = Query(..., description="IP address, domain, or URL to check"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    store: StateStore = Depends(get_store),
):
    service = ThreatIntelService(db, store)
    return await service.query(target, current_user.id)


@router.get("/history", response_model=ThreatHistoryResponse)
async def threat_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ThreatIntelService(db)
    records = await service.get_history(current_user.id, limit)
    return ThreatHistoryResponse(records=records)
