"""统计路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.stats import DashboardResponse
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api/v1/stats", tags=["Statistics"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StatsService(db)
    return await service.get_dashboard(current_user.id, current_user.tier)
