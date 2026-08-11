"""流量分析 Schema"""

from pydantic import BaseModel, Field


class PacketAnalysisRequest(BaseModel):
    packets: list[str] = Field(..., min_length=1, max_length=500)


class PacketAnalysisResponse(BaseModel):
    total_packets_analyzed: int
    anomaly_detected: bool
    anomaly_score: float
    analysis: dict
    recommendations: list[str]


class TrafficHistoryItem(BaseModel):
    id: int
    source_ip: str
    dest_ip: str
    protocol: str
    anomaly_detected: bool
    anomaly_score: float
    details: dict
    created_at: str

    model_config = {"from_attributes": True}


class TrafficHistoryResponse(BaseModel):
    records: list[TrafficHistoryItem]
