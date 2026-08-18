"""历史知识库迁移 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.services.kb_migration_service import kb_migration_service
from utils.api_response import success_response

router = APIRouter(prefix="/api/kb/migration", tags=["kb-migration"])


class MigrationStartRequest(BaseModel):
    """启动迁移请求。"""

    plan_digest: str = Field(..., min_length=16)
    kb_ids: list[str] | None = None
    retry_failed_only: bool = False
    recompute_missing_embeddings: bool = False


class MigrationRollbackRequest(BaseModel):
    """回滚迁移批次请求。"""

    batch_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")


@router.get("/status")
def get_migration_status() -> dict:
    """返回当前迁移状态。"""
    return success_response(kb_migration_service.get_status())


@router.post("/scan")
def scan_migration() -> dict:
    """扫描历史共享索引并生成 dry-run 计划。"""
    try:
        return success_response(kb_migration_service.scan())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
def start_migration(request: MigrationStartRequest) -> dict:
    """后台启动迁移。"""
    try:
        snapshot, started = kb_migration_service.start(
            plan_digest=request.plan_digest,
            kb_ids=request.kb_ids,
            retry_failed_only=request.retry_failed_only,
            recompute_missing_embeddings=request.recompute_missing_embeddings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not started:
        raise HTTPException(status_code=409, detail="Migration is already running")
    return success_response(snapshot)


@router.post("/rollback")
def rollback_migration(request: MigrationRollbackRequest) -> dict:
    """隔离指定批次创建的目标索引。"""
    try:
        return success_response(kb_migration_service.rollback(request.batch_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
