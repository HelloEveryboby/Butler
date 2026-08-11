"""定时扫描模型"""

from sqlalchemy import Integer, ForeignKey, JSON, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ScheduledScan(TimestampMixin, Base):
    __tablename__ = "scheduled_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    target: Mapped[str] = mapped_column(String(256))
    scan_type: Mapped[str] = mapped_column(String(32))
    cron_expr: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_result: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship()
