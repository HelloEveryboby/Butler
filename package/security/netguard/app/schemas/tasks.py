"""任务 / 抓包 / 黑名单 / 定时扫描 Schema"""

from pydantic import BaseModel, Field


# ── 任务 ──
class TaskSubmitResponse(BaseModel):
    task_id: str
    task_type: str
    status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    result: dict | None = None
    created_at: str
    updated_at: str


class TaskListResponse(BaseModel):
    tasks: list[TaskStatusResponse]


# ── 抓包 ──
class CaptureRequest(BaseModel):
    interface: str = "eth0"
    duration: int = Field(10, ge=1, le=120)
    filter_expr: str = ""
    packet_count: int = Field(100, ge=1, le=10000)


class CaptureResponse(BaseModel):
    total_packets: int
    duration_seconds: float
    interface: str
    protocols: dict
    top_sources: dict
    top_destinations: dict
    total_bytes: int
    pcap_file: str | None = None


# ── 黑名单 ──
class BlacklistFetchResponse(BaseModel):
    sources: dict
    total_ips: int
    fetched_at: str


class BlacklistCheckResponse(BaseModel):
    ip: str
    is_blacklisted: bool
    sources: list[str]
    checked_at: str


# ── 定时扫描 ──
class ScheduleCreateRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=256)
    scan_type: str = "port_scan"
    cron_expr: str = Field(..., min_length=1, max_length=64)


class ScheduleResponse(BaseModel):
    id: int
    target: str
    scan_type: str
    cron_expr: str
    is_active: bool
    last_run_at: str | None = None
    created_at: str


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResponse]
