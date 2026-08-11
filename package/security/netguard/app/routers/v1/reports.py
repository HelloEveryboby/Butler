"""报告导出路由"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@router.get("/threats")
async def export_threats(
    format: str = Query("csv", pattern="^(csv|json)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    content, content_type = await service.export_threats(current_user.id, format)
    ext = "csv" if format == "csv" else "json"
    return StreamingResponse(
        io.StringIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename=threats.{ext}"},
    )


@router.get("/scans")
async def export_scans(
    format: str = Query("csv", pattern="^(csv|json)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    content, content_type = await service.export_scans(current_user.id, format)
    ext = "csv" if format == "csv" else "json"
    return StreamingResponse(
        io.StringIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename=scans.{ext}"},
    )


@router.get("/protection")
async def export_protection(
    format: str = Query("csv", pattern="^(csv|json)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    content, content_type = await service.export_protection(current_user.id, format)
    ext = "csv" if format == "csv" else "json"
    return StreamingResponse(
        io.StringIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename=protection.{ext}"},
    )
