"""面向外部 Agent 的只读开放 API。"""

from __future__ import annotations

import secrets
import time
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from api.services.access_token_service import access_token_service
from api.services.open_api_audit import open_api_audit
from api.services.open_api_service import run_readonly_query, run_readonly_search
from server.kb_registry import KBRegistry
from server.utils.file import get_storage_root
from utils.api_response import success_response

router = APIRouter(prefix="/api/open/v1", tags=["open-readonly"])
kb_registry = KBRegistry(get_storage_root() / "kb_registry.json")


OpenAnswerResponseMode = Literal[
    "compact",
    "refine",
    "tree_summarize",
    "simple_summarize",
    "accumulate",
    "compact_accumulate",
]


class OpenReadonlyRequest(BaseModel):
    """开放只读请求基类，只接受显式声明的只读字段。"""

    model_config = ConfigDict(extra="forbid")
    kb_id: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=20_000)


class OpenSearchRequest(OpenReadonlyRequest):
    """开放结构化检索请求，仅支持检索层安全参数。"""

    top_k: int | None = Field(default=None, ge=1, le=50)


class OpenAnswerRequest(OpenSearchRequest):
    """开放问答请求，支持与主链路一致的只读检索参数。"""

    response_mode: OpenAnswerResponseMode | None = None
    use_reranker: bool | None = None
    top_n: int | None = Field(default=None, ge=1, le=50)
    reranker_model: str | None = Field(default=None, min_length=1, max_length=128)


def _bearer_token(authorization: str | None = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token is required")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token is required")
    return token


def _authenticate(authorization: str | None) -> dict[str, Any]:
    token = _bearer_token(authorization)
    try:
        return access_token_service.verify_token(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or secrets.token_hex(8)


@router.get("/me")
def get_identity(request: Request, authorization: str | None = Header(default=None)) -> dict:
    record = _authenticate(authorization)
    access_token_service.touch_last_used(record["token_id"])
    open_api_audit.append(token_id=record["token_id"], route="/me", kb_id=None, status_code=200, duration_ms=0, request_id=_request_id(request))
    return success_response(record)


@router.get("/knowledge-bases")
def list_authorized_knowledge_bases(request: Request, authorization: str | None = Header(default=None)) -> dict:
    record = _authenticate(authorization)
    allowed = set(record.get("kb_ids") or [])
    items = [
        item for item in kb_registry.list_kbs()
        if item.get("status", "active") == "active" and item.get("kb_id") in allowed
    ]
    access_token_service.touch_last_used(record["token_id"])
    open_api_audit.append(token_id=record["token_id"], route="/knowledge-bases", kb_id=None, status_code=200, duration_ms=0, request_id=_request_id(request))
    return success_response({"items": items})


def _run_open_executor(
    *,
    route_name: str,
    kb_id: str,
    request: Request,
    authorization: str | None,
    executor,
    question: str,
    **executor_kwargs,
) -> dict:
    started = time.perf_counter()
    record = _authenticate(authorization)
    status_code = 200
    try:
        access_token_service.authorize_kb(record, kb_id)
        result = executor(
            token_id=record["token_id"],
            kb_id=kb_id,
            question=question,
            **executor_kwargs,
        )
        access_token_service.touch_last_used(record["token_id"])
        return success_response(result)
    except PermissionError as exc:
        status_code = 403
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 400
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        status_code = 503
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        open_api_audit.append(
            token_id=record["token_id"],
            route=route_name,
            kb_id=kb_id,
            status_code=status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            request_id=_request_id(request),
        )


@router.post("/search")
def search(payload: OpenSearchRequest, request: Request, authorization: str | None = Header(default=None)) -> dict:
    return _run_open_executor(
        route_name="/search",
        kb_id=payload.kb_id,
        question=payload.question,
        request=request,
        authorization=authorization,
        executor=run_readonly_search,
        top_k=payload.top_k,
    )


@router.post("/answer")
def answer(payload: OpenAnswerRequest, request: Request, authorization: str | None = Header(default=None)) -> dict:
    return _run_open_executor(
        route_name="/answer",
        kb_id=payload.kb_id,
        question=payload.question,
        request=request,
        authorization=authorization,
        executor=run_readonly_query,
        top_k=payload.top_k,
        response_mode=payload.response_mode,
        use_reranker=payload.use_reranker,
        top_n=payload.top_n,
        reranker_model=payload.reranker_model,
    )


