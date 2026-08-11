"""统计 Schema"""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    threat_lookups: int
    malicious_detections: int
    scans: int
    traffic_analyses: int
    protection_events: int
    blocked_attacks: int


class DashboardResponse(BaseModel):
    user_id: int
    tier: str
    stats: DashboardStats
    limits: dict
