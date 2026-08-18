"""Embedding 本地缓存恢复路由。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.embedding_cache_service import (
    EmbeddingDownloadConflictError,
    InsufficientDiskSpaceError,
    embedding_cache_service,
)
from utils.api_response import success_response

router = APIRouter(prefix="/api/embedding/cache", tags=["embedding-cache"])


class EmbeddingCacheProviderRequest(BaseModel):
    """缓存请求；只开放 ModelScope 白名单来源。"""

    provider: Literal["modelscope"] = "modelscope"


@router.get("")
def get_embedding_cache_status() -> dict:
    """返回缓存准备后台任务状态。"""
    return success_response(embedding_cache_service.get_status())


@router.post("/preflight")
def preflight_embedding_cache(request: EmbeddingCacheProviderRequest) -> dict:
    """检查缓存目标磁盘空间，不启动下载。"""
    try:
        return success_response(embedding_cache_service.preflight(provider=request.provider))
    except EmbeddingDownloadConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/prepare")
def prepare_embedding_cache(request: EmbeddingCacheProviderRequest) -> dict:
    """幂等触发 ModelScope 缓存准备任务。"""
    try:
        status, started = embedding_cache_service.start_prepare(provider=request.provider)
    except InsufficientDiskSpaceError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    except EmbeddingDownloadConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success_response({"started": started, "status": status})


@router.post("/cancel")
def cancel_embedding_cache() -> dict:
    """协作式取消当前缓存下载任务。"""
    return success_response(embedding_cache_service.request_cancel())
