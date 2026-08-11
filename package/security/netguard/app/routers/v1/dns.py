"""DNS / 子域名路由"""

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models.user import User
from app.schemas.dns import (
    DNSLookupRequest,
    DNSLookupResponse,
    ReverseDNSRequest,
    ReverseDNSResponse,
    SubdomainEnumRequest,
    SubdomainEnumResponse,
)
from app.services.dns_service import DNSService

router = APIRouter(prefix="/api/v1/dns", tags=["DNS"])
dns_service = DNSService()


@router.post("/lookup", response_model=DNSLookupResponse)
async def dns_lookup(
    req: DNSLookupRequest,
    current_user: User = Depends(get_current_user),
):
    return await dns_service.lookup(req.domain, req.record_types)


@router.post("/reverse", response_model=ReverseDNSResponse)
async def reverse_dns(
    req: ReverseDNSRequest,
    current_user: User = Depends(get_current_user),
):
    result = await dns_service.reverse_lookup(req.ip)
    return result


@router.post("/subdomains", response_model=SubdomainEnumResponse)
async def subdomain_enum(
    req: SubdomainEnumRequest,
    current_user: User = Depends(get_current_user),
):
    return await dns_service.subdomain_enum(req.domain)
