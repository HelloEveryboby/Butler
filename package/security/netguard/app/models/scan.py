"""ScanRecord 模型"""

from sqlalchemy import Integer, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ScanRecord(TimestampMixin, Base):
    __tablename__ = "scan_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    target: Mapped[str] = mapped_column(String(256))
    scan_type: Mapped[str] = mapped_column(String(32))
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="scan_records")
