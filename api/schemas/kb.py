"""知识库相关请求/响应模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class KBCreateRequest(BaseModel):
    """创建知识库请求"""
    kb_id: str = Field(..., min_length=1, max_length=64, description="知识库唯一标识")
    kb_name: str = Field(..., min_length=1, max_length=128, description="知识库名称")


class KBUpdateRequest(BaseModel):
    """更新知识库请求"""
    kb_name: str = Field(..., min_length=1, max_length=128, description="知识库新名称")


class KBResponse(BaseModel):
    """知识库响应"""
    kb_id: str
    kb_name: str
    created_at: str
    updated_at: str
    status: str
    doc_count: int = 0


class KBListResponse(BaseModel):
    """知识库列表响应"""
    items: list[KBResponse]
