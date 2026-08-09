from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.models import User
from auth.auth import get_current_user
from modules.threat_intel import query_threat, get_threat_history

router = APIRouter(prefix="/api/v1/threat-intel", tags=["Threat Intelligence"])


@router.get("/lookup")
async def threat_lookup(
    target: str = Query(..., description="IP address, domain, or URL to check"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await query_threat(target, current_user.id, db)
    return result


@router.get("/history")
async def threat_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"records": await get_threat_history(current_user.id, db, limit)}
