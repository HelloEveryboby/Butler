"""DNS Schema"""

from pydantic import BaseModel, Field


class DNSLookupRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=256)
    record_types: list[str] | None = None  # ["A", "MX", ...]


class DNSLookupResponse(BaseModel):
    domain: str
    records: dict
    queried_at: str


class SubdomainEnumRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=256)


class SubdomainEnumResponse(BaseModel):
    domain: str
    total_checked: int
    found_count: int
    subdomains: list[dict]
    queried_at: str


class ReverseDNSRequest(BaseModel):
    ip: str = Field(..., min_length=1, max_length=64)


class ReverseDNSResponse(BaseModel):
    ip: str
    hostname: str | None
    aliases: list[str] | None = None
    error: str | None = None
