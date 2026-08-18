"""知识库只读授权令牌服务测试。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from api.services.access_token_service import AccessTokenService


class Registry:
    def __init__(self):
        self.items = [
            {"kb_id": "finance", "kb_name": "Finance", "status": "active"},
            {"kb_id": "hr", "kb_name": "HR", "status": "active"},
            {"kb_id": "old", "kb_name": "Old", "status": "deleted"},
        ]

    def get_kb(self, kb_id):
        return next((item for item in self.items if item["kb_id"] == kb_id), None)

    def list_kbs(self):
        return list(self.items)


def make_service(tmp_path):
    return AccessTokenService(
        store_path=tmp_path / "access_tokens.json",
        pepper_path=tmp_path / "token-pepper",
        admin_key_path=tmp_path / "admin-key",
        registry=Registry(),
    )


def test_create_returns_plaintext_once_and_store_contains_only_hash(tmp_path):
    service = make_service(tmp_path)
    created = service.create_token(name="robot", kb_ids=["finance"])
    assert created["token"].startswith("nak_ro_")
    raw = (tmp_path / "access_tokens.json").read_text(encoding="utf-8")
    assert created["token"] not in raw
    payload = json.loads(raw)
    assert payload[0]["secret_hash"]
    assert "token" not in payload[0]
    assert service.list_tokens()[0].get("secret_hash") is None
    assert os.stat(tmp_path / "access_tokens.json").st_mode & 0o777 == 0o600
    assert os.stat(tmp_path / "token-pepper").st_mode & 0o777 == 0o600


def test_verify_enforces_scope_expiry_and_revocation(tmp_path):
    service = make_service(tmp_path)
    active = service.create_token(name="robot", kb_ids=["finance", "hr"])
    context = service.verify_token(active["token"])
    assert service.authorize_kb(context, "finance")["kb_id"] == "finance"
    with pytest.raises(PermissionError, match="not authorized"):
        service.authorize_kb(context, "old")

    expired = service.create_token(
        name="expired",
        kb_ids=["finance"],
        expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
    )
    with pytest.raises(PermissionError, match="expired"):
        service.verify_token(expired["token"])

    service.revoke_token(active["token_id"])
    with pytest.raises(PermissionError, match="revoked"):
        service.verify_token(active["token"])


def test_create_rejects_unknown_or_inactive_kb(tmp_path):
    service = make_service(tmp_path)
    with pytest.raises(ValueError, match="not active"):
        service.create_token(name="bad", kb_ids=["old"])
    with pytest.raises(ValueError, match="not active"):
        service.create_token(name="bad", kb_ids=["missing"])
    with pytest.raises(ValueError, match="at least one"):
        service.create_token(name="bad", kb_ids=[])


def test_admin_key_is_stable_and_private(tmp_path):
    service = make_service(tmp_path)
    first = service.get_admin_key()
    second = service.get_admin_key()
    assert first == second
    assert len(first) >= 32
    assert os.stat(tmp_path / "admin-key").st_mode & 0o777 == 0o600


def test_create_rejects_invalid_expiry_format_with_stable_error(tmp_path):
    """非法过期时间应作为输入错误拒绝，而不是泄露底层解析异常。"""
    service = make_service(tmp_path)
    with pytest.raises(ValueError, match="Invalid expires_at"):
        service.create_token(name="robot", kb_ids=["finance"], expires_at="not-a-date")
