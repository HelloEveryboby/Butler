from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    tier: Mapped[str] = mapped_column(String(16), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class APICallLog(Base):
    __tablename__ = "api_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer)
    endpoint: Mapped[str] = mapped_column(String(256))
    method: Mapped[str] = mapped_column(String(16))
    status_code: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ThreatRecord(Base):
    __tablename__ = "threat_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer)
    target: Mapped[str] = mapped_column(String(256), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    is_malicious: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    categories: Mapped[str] = mapped_column(Text, default="[]")
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScanRecord(Base):
    __tablename__ = "scan_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer)
    target: Mapped[str] = mapped_column(String(256))
    scan_type: Mapped[str] = mapped_column(String(32))
    results: Mapped[str] = mapped_column(Text, default="{}")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrafficAnalysisRecord(Base):
    __tablename__ = "traffic_analysis_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer)
    source_ip: Mapped[str] = mapped_column(String(64))
    dest_ip: Mapped[str] = mapped_column(String(64))
    protocol: Mapped[str] = mapped_column(String(32))
    anomaly_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProtectionEvent(Base):
    __tablename__ = "protection_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    source_ip: Mapped[str] = mapped_column(String(64))
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    action_taken: Mapped[str] = mapped_column(String(64))
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
