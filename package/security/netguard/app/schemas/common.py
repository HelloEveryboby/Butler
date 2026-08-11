"""通用 Schema"""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str


class PaginatedResponse(BaseModel):
    """分页响应基类"""
    total: int
    page: int
    page_size: int
