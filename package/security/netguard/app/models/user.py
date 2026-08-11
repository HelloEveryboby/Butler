"""User 模型"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    tier: Mapped[str] = mapped_column(String(16), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # ── 关系 ──
    threat_records: Mapped[list["ThreatRecord"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    scan_records: Mapped[list["ScanRecord"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    traffic_records: Mapped[list["TrafficAnalysisRecord"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    protection_events: Mapped[list["ProtectionEvent"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )


# 延迟导入以解决循环引用（relationship 字符串引用已在上面声明）
from app.models.threat import ThreatRecord  # noqa: E402, F401
from app.models.scan import ScanRecord  # noqa: E402, F401
from app.models.traffic import TrafficAnalysisRecord  # noqa: E402, F401
from app.models.protection import ProtectionEvent  # noqa: E402, F401
