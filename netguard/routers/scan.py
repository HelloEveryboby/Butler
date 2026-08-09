from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.models import User
from auth.auth import get_current_user
from modules.scanner import port_scan, vulnerability_probe, get_scan_history

router = APIRouter(prefix="/api/v1/scan", tags=["Scanner"])


class PortScanRequest(BaseModel):
    target: str
    port_range: str = "common"


class VulnProbeRequest(BaseModel):
    target: str


@router.post("/port-scan")
async def run_port_scan(
    req: PortScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.tier == "free" and req.port_range not in ["common", "1-1024"]:
        raise HTTPException(status_code=429, detail="Free tier limited to common ports or 1-1024 range")
    return await port_scan(req.target, req.port_range, current_user.id, db)


@router.post("/vuln-probe")
async def run_vuln_probe(
    req: VulnProbeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await vulnerability_probe(req.target, current_user.id, db)


@router.get("/history")
async def scan_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"records": await get_scan_history(current_user.id, db, limit)}
