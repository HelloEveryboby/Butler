"""IP 黑名单记录模型"""

from sqlalchemy import Integer, ForeignKey, JSON, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class BlacklistRecord(TimestampMixin, Base):
    __tablename__ = "blacklist_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(128), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
