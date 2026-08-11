"""扫描 Schema"""

from pydantic import BaseModel, Field


class PortScanRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=256)
    port_range: str = "common"


class VulnProbeRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=256)


class PortScanResponse(BaseModel):
    target: str
    scan_type: str
    total_ports: int
    open_ports: list[dict]
    open_count: int
    duration_ms: int


class VulnProbeResponse(BaseModel):
    target: str
    open_ports_found: int
    service_probes: list[dict]
    potential_vulnerabilities: list[dict]
    risk_level: str


class ScanHistoryItem(BaseModel):
    id: int
    target: str
    scan_type: str
    results: dict
    duration_ms: int
    created_at: str

    model_config = {"from_attributes": True}


class ScanHistoryResponse(BaseModel):
    records: list[ScanHistoryItem]
