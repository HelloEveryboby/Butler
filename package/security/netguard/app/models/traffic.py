"""TrafficAnalysisRecord 模型"""

from sqlalchemy import Boolean, Float, Integer, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TrafficAnalysisRecord(TimestampMixin, Base):
    __tablename__ = "traffic_analysis_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    source_ip: Mapped[str] = mapped_column(String(64))
    dest_ip: Mapped[str] = mapped_column(String(64))
    protocol: Mapped[str] = mapped_column(String(32))
    anomaly_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="traffic_records")
