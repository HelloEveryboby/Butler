from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.models import User, APICallLog, ThreatRecord, ScanRecord, TrafficAnalysisRecord, ProtectionEvent
from auth.auth import get_current_user

router = APIRouter(prefix="/api/v1/stats", tags=["Statistics"])


@router.get("/dashboard")
async def get_dashboard(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user.id

    threat_count = await db.execute(
        select(func.count()).select_from(ThreatRecord).where(ThreatRecord.user_id == user_id)
    )
    scan_count = await db.execute(
        select(func.count()).select_from(ScanRecord).where(ScanRecord.user_id == user_id)
    )
    traffic_count = await db.execute(
        select(func.count()).select_from(TrafficAnalysisRecord).where(TrafficAnalysisRecord.user_id == user_id)
    )
    protection_count = await db.execute(
        select(func.count()).select_from(ProtectionEvent).where(ProtectionEvent.user_id == user_id)
    )
    blocked_count = await db.execute(
        select(func.count()).select_from(ProtectionEvent).where(
            ProtectionEvent.user_id == user_id, ProtectionEvent.blocked == True
        )
    )
    malicious_count = await db.execute(
        select(func.count()).select_from(ThreatRecord).where(
            ThreatRecord.user_id == user_id, ThreatRecord.is_malicious == True
        )
    )

    return {
        "user_id": user_id,
        "tier": current_user.tier,
        "stats": {
            "threat_lookups": threat_count.scalar(),
            "scans": scan_count.scalar(),
            "traffic_analyses": traffic_count.scalar(),
            "protection_events": protection_count.scalar(),
            "blocked_attacks": blocked_count.scalar(),
            "malicious_detections": malicious_count.scalar(),
        },
        "limits": {
            "tier": current_user.tier,
        },
    }
