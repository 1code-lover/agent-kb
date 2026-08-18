"""本机只读授权令牌 CLI 测试。"""

from __future__ import annotations

import json

from scripts import manage_access_tokens


class _Service:
    """记录 CLI 命令调用并返回稳定结果。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create_token(self, *, name, kb_ids, expires_at=None):
        self.calls.append(("create", name, kb_ids, expires_at))
        return {"token_id": "tok-1", "token": "nak_ro_tok-1_secret", "kb_ids": kb_ids}

    def list_tokens(self):
        self.calls.append(("list",))
        return [{"token_id": "tok-1", "kb_ids": ["finance"]}]

    def revoke_token(self, token_id):
        self.calls.append(("revoke", token_id))
        return {"token_id": token_id, "status": "revoked"}


def test_cli_create_list_and_revoke(monkeypatch, capsys):
    """CLI 三类命令应调用服务并输出机器可读 JSON。"""
    service = _Service()
    monkeypatch.setattr(manage_access_tokens, "access_token_service", service)

    assert manage_access_tokens.main([
        "create",
        "--name",
        "robot",
        "--kb",
        "finance",
        "--kb",
        "hr",
        "--expires-at",
        "2026-12-31T00:00:00Z",
    ]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["token"] == "nak_ro_tok-1_secret"

    assert manage_access_tokens.main(["list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["items"][0]["token_id"] == "tok-1"

    assert manage_access_tokens.main(["revoke", "tok-1"]) == 0
    revoked = json.loads(capsys.readouterr().out)
    assert revoked["status"] == "revoked"
    assert service.calls == [
        ("create", "robot", ["finance", "hr"], "2026-12-31T00:00:00Z"),
        ("list",),
        ("revoke", "tok-1"),
    ]
