"""知识库只读授权令牌服务测试。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

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


def assert_private_file(path: Path) -> None:
    """校验敏感文件已落盘；POSIX 环境额外校验 0600 权限。"""

    assert path.exists()
    mode = os.stat(path).st_mode & 0o777
    if os.name != "nt":
        assert mode == 0o600


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
    assert_private_file(tmp_path / "access_tokens.json")
    assert_private_file(tmp_path / "token-pepper")


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
    assert_private_file(tmp_path / "admin-key")


def test_create_rejects_invalid_expiry_format_with_stable_error(tmp_path):
    """非法过期时间应作为输入错误拒绝，而不是泄露底层解析异常。"""
    service = make_service(tmp_path)
    with pytest.raises(ValueError, match="Invalid expires_at"):
        service.create_token(name="robot", kb_ids=["finance"], expires_at="not-a-date")


def test_get_admin_key_retries_permission_error_and_cleans_tmp_file(tmp_path, monkeypatch):
    """敏感 secret 初次落盘遇到临时锁时，应重试并清理遗留 tmp 文件。"""
    service = make_service(tmp_path)
    real_replace = os.replace
    attempts = {"count": 0}

    def flaky_replace(src, dst):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("locked")
        return real_replace(src, dst)

    sleep = MagicMock()
    monkeypatch.setattr("api.services.access_token_service.os.replace", flaky_replace)
    monkeypatch.setattr("api.services.access_token_service.time.sleep", sleep)

    value = service.get_admin_key()

    assert len(value) >= 32
    assert attempts["count"] == 3
    assert sleep.call_count == 2
    assert_private_file(tmp_path / "admin-key")
    assert list(tmp_path.glob("admin-key.tmp-*")) == []


def test_create_token_retries_permission_error_when_writing_store(tmp_path, monkeypatch):
    """令牌清单落盘遇到临时锁时，应重试成功且不留下 tmp 文件。"""
    service = make_service(tmp_path)
    real_replace = os.replace
    attempts = {"store": 0, "all": 0}

    def flaky_replace(src, dst):
        attempts["all"] += 1
        if Path(dst) == tmp_path / "access_tokens.json":
            attempts["store"] += 1
            if attempts["store"] < 3:
                raise PermissionError("locked")
        return real_replace(src, dst)

    sleep = MagicMock()
    monkeypatch.setattr("api.services.access_token_service.os.replace", flaky_replace)
    monkeypatch.setattr("api.services.access_token_service.time.sleep", sleep)

    created = service.create_token(name="robot", kb_ids=["finance"])

    assert created["token"].startswith("nak_ro_")
    assert attempts["store"] == 3
    assert attempts["all"] >= attempts["store"]
    assert sleep.call_count == 2
    assert json.loads((tmp_path / "access_tokens.json").read_text(encoding="utf-8"))[0]["token_id"] == created["token_id"]
    assert list(tmp_path.glob("access_tokens.json.tmp-*")) == []


def test_create_token_raises_after_retry_exhaustion_and_cleans_tmp_file(tmp_path, monkeypatch):
    """如果写 token store 的 replace 一直失败，应抛错且清理 tmp 文件。"""
    service = make_service(tmp_path)

    monkeypatch.setattr("api.services.access_token_service.os.replace", MagicMock(side_effect=PermissionError("still locked")))
    monkeypatch.setattr("api.services.access_token_service.time.sleep", MagicMock())

    with pytest.raises(PermissionError, match="still locked"):
        service.create_token(name="robot", kb_ids=["finance"])

    assert not (tmp_path / "access_tokens.json").exists()
    assert list(tmp_path.glob("access_tokens.json.tmp-*")) == []
