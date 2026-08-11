"""ThreatRecord 模型"""

from sqlalchemy import Boolean, Float, Integer, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ThreatRecord(TimestampMixin, Base):
    __tablename__ = "threat_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    target: Mapped[str] = mapped_column(String(256), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    is_malicious: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="threat_records")
