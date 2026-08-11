"""增强威胁情报 Schema（支持外部 API）"""

from pydantic import BaseModel


class ThreatLookupResponse(BaseModel):
    target: str
    target_type: str
    analysis: dict
    external_sources: list[dict] | None = None
    blacklist: dict | None = None
    recommendations: list[str]


class ThreatHistoryItem(BaseModel):
    id: int
    target: str
    target_type: str
    is_malicious: bool
    score: float
    categories: list
    created_at: str

    model_config = {"from_attributes": True}


class ThreatHistoryResponse(BaseModel):
    records: list[ThreatHistoryItem]
