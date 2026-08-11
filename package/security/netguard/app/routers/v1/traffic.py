"""流量分析路由"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.traffic import (
    PacketAnalysisRequest,
    PacketAnalysisResponse,
    TrafficHistoryResponse,
)
from app.services.traffic_service import TrafficService

router = APIRouter(prefix="/api/v1/traffic", tags=["Traffic Analysis"])


@router.post("/analyze", response_model=PacketAnalysisResponse)
async def traffic_analyze(
    req: PacketAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.tier == "free" and len(req.packets) > 20:
        raise HTTPException(
            status_code=429,
            detail="Free tier limited to 20 packets per request",
        )

    service = TrafficService(db)
    return await service.analyze_packets(req.packets, current_user.id)


@router.get("/history", response_model=TrafficHistoryResponse)
async def traffic_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TrafficService(db)
    records = await service.get_history(current_user.id, limit)
    return TrafficHistoryResponse(records=records)
