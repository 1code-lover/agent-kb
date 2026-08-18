"""本机只读访问令牌管理 API。"""

from __future__ import annotations

import hmac
import ipaddress
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from api.services.access_token_service import access_token_service
from utils.api_response import success_response

router = APIRouter(prefix="/api/access-tokens", tags=["access-tokens"])


class CreateAccessTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=128)
    kb_ids: list[str] = Field(..., min_length=1)
    expires_at: str | None = None


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _require_admin(request: Request, admin_key: str | None) -> None:
    if not _is_loopback(request.client.host if request.client else None):
        raise HTTPException(status_code=403, detail="Token management is restricted to loopback clients")
    expected = access_token_service.get_admin_key()
    if not admin_key or not hmac.compare_digest(admin_key, expected):
        raise HTTPException(status_code=403, detail="Invalid local administrator key")


@router.get("")
def list_access_tokens(request: Request, x_thinkrag_admin_key: str | None = Header(default=None)) -> dict:
    _require_admin(request, x_thinkrag_admin_key)
    return success_response({"items": access_token_service.list_tokens()})


@router.post("", status_code=status.HTTP_201_CREATED)
def create_access_token(
    payload: CreateAccessTokenRequest,
    request: Request,
    x_thinkrag_admin_key: str | None = Header(default=None),
) -> dict:
    _require_admin(request, x_thinkrag_admin_key)
    try:
        result = access_token_service.create_token(name=payload.name, kb_ids=payload.kb_ids, expires_at=payload.expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(result)


@router.post("/{token_id}/revoke")
def revoke_access_token(
    token_id: str,
    request: Request,
    x_thinkrag_admin_key: str | None = Header(default=None),
) -> dict:
    _require_admin(request, x_thinkrag_admin_key)
    try:
        return success_response(access_token_service.revoke_token(token_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
