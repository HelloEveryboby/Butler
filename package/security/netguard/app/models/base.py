"""公共 ORM 基类 + Mixin — 从 app.database 导入 Base 以保持单例"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base  # 统一使用同一个 Base


class TimestampMixin:
    """统一 created_at 字段，由数据库生成"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
