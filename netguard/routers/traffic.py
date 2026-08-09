from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.models import User
from auth.auth import get_current_user
from modules.traffic_analysis import analyze_packets, get_analysis_history

router = APIRouter(prefix="/api/v1/traffic", tags=["Traffic Analysis"])


class PacketAnalysisRequest(BaseModel):
    packets: list[str]


@router.post("/analyze")
async def traffic_analyze(
    req: PacketAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.tier == "free" and len(req.packets) > 20:
        raise HTTPException(status_code=429, detail="Free tier limited to 20 packets per request")
    if len(req.packets) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 packets per request")

    return await analyze_packets(req.packets, current_user.id, db)


@router.get("/history")
async def traffic_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"records": await get_analysis_history(current_user.id, db, limit)}
