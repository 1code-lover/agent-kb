"""Embedding 本地缓存恢复路由。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from api.services.embedding_cache_service import embedding_cache_service
from utils.api_response import success_response

router = APIRouter(prefix="/api/embedding/cache", tags=["embedding-cache"])


class PrepareEmbeddingCacheRequest(BaseModel):
    """缓存恢复请求；首版只开放 ModelScope 白名单来源。"""

    provider: Literal["modelscope"] = "modelscope"


@router.get("")
def get_embedding_cache_status() -> dict:
    """返回缓存准备后台任务状态。"""
    return success_response(embedding_cache_service.get_status())


@router.post("/prepare")
def prepare_embedding_cache(request: PrepareEmbeddingCacheRequest) -> dict:
    """幂等触发 ModelScope 缓存准备任务。"""
    status, started = embedding_cache_service.start_prepare(provider=request.provider)
    return success_response({"started": started, "status": status})
