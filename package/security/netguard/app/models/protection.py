"""ProtectionEvent 模型"""

from sqlalchemy import Boolean, Integer, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ProtectionEvent(TimestampMixin, Base):
    __tablename__ = "protection_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    source_ip: Mapped[str] = mapped_column(String(64))
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    action_taken: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="protection_events")
