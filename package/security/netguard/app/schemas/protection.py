"""防护 Schema"""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    source_ip: str = Field(..., min_length=1, max_length=64)
    target_url: str = ""
    payload: str = ""
    target_port: int = Field(0, ge=0, le=65535)


class AnalyzeResponse(BaseModel):
    source_ip: str
    blocked: bool
    detections: list[dict]
    action: str
    recommendations: list[str]


class UnblockRequest(BaseModel):
    ip: str = Field(..., min_length=1, max_length=64)


class UpdateRulesRequest(BaseModel):
    ddos_threshold: int | None = None
    ddos_window_seconds: int | None = None
    port_scan_threshold: int | None = None
    brute_force_threshold: int | None = None
    brute_force_window_seconds: int | None = None


class RulesResponse(BaseModel):
    status: str
    rules: dict


class BlockedIPsResponse(BaseModel):
    blocked_ips: list[str]


class ProtectionHistoryItem(BaseModel):
    id: int
    event_type: str
    source_ip: str
    blocked: bool
    action_taken: str
    details: dict
    created_at: str

    model_config = {"from_attributes": True}


class ProtectionHistoryResponse(BaseModel):
    records: list[ProtectionHistoryItem]
