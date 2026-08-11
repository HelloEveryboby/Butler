"""扫描路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.scan import (
    PortScanRequest,
    PortScanResponse,
    ScanHistoryResponse,
    VulnProbeRequest,
    VulnProbeResponse,
)
from app.services.scan_service import ScanService

router = APIRouter(prefix="/api/v1/scan", tags=["Scanner"])


@router.post("/port-scan", response_model=PortScanResponse)
async def run_port_scan(
    req: PortScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Tier 限制
    if current_user.tier == "free" and req.port_range not in ("common", "1-1024"):
        raise HTTPException(
            status_code=429,
            detail="Free tier limited to common ports or 1-1024 range",
        )

    service = ScanService(db)
    try:
        return await service.port_scan(req.target, req.port_range, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vuln-probe", response_model=VulnProbeResponse)
async def run_vuln_probe(
    req: VulnProbeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanService(db)
    try:
        return await service.vulnerability_probe(req.target, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history", response_model=ScanHistoryResponse)
async def scan_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanService(db)
    records = await service.get_history(current_user.id, limit)
    return ScanHistoryResponse(records=records)
