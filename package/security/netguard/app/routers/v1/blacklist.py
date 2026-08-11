"""IP 黑名单路由"""

from fastapi import APIRouter, Depends

from app.deps import get_current_user, get_store
from app.models.user import User
from app.schemas.tasks import BlacklistCheckResponse, BlacklistFetchResponse
from app.services.blacklist_service import BlacklistService

router = APIRouter(prefix="/api/v1/blacklist", tags=["Blacklist"])


@router.post("/fetch", response_model=BlacklistFetchResponse)
async def fetch_blacklists(
    current_user: User = Depends(get_current_user),
    store=Depends(get_store),
):
    """从所有公开源拉取最新黑名单"""
    service = BlacklistService(store)
    return await service.fetch_all()


@router.get("/check/{ip}", response_model=BlacklistCheckResponse)
async def check_ip_blacklist(
    ip: str,
    current_user: User = Depends(get_current_user),
    store=Depends(get_store),
):
    """检查指定 IP 是否在黑名单中"""
    service = BlacklistService(store)
    return await service.check_ip(ip)


@router.get("/list")
async def list_blacklist(
    source: str | None = None,
    current_user: User = Depends(get_current_user),
    store=Depends(get_store),
):
    """获取黑名单中的所有 IP"""
    service = BlacklistService(store)
    ips = await store.get_blacklist(source)
    return {"source": source, "count": len(ips), "ips": ips[:1000]}
