"""令牌管理 API 测试。"""

from fastapi.testclient import TestClient

from api.app import app
from api.routers import access_tokens


class FakeService:
    def get_admin_key(self):
        return "admin-secret"

    def create_token(self, **kwargs):
        return {"token_id": "id1", "token": "nak_ro_id1_secret", **kwargs}

    def list_tokens(self):
        return [{"token_id": "id1", "kb_ids": ["finance"]}]

    def revoke_token(self, token_id):
        return {"token_id": token_id, "status": "revoked"}


def test_access_token_management_requires_loopback_and_admin_key(monkeypatch):
    monkeypatch.setattr(access_tokens, "access_token_service", FakeService())
    monkeypatch.setattr(access_tokens, "_is_loopback", lambda host: True)
    client = TestClient(app)
    assert client.get("/api/access-tokens").status_code == 403
    assert client.get("/api/access-tokens", headers={"X-ThinkRAG-Admin-Key": "bad"}).status_code == 403
    headers = {"X-ThinkRAG-Admin-Key": "admin-secret"}
    assert client.get("/api/access-tokens", headers=headers).status_code == 200
    created = client.post("/api/access-tokens", headers=headers, json={"name": "robot", "kb_ids": ["finance"]})
    assert created.status_code == 201
    assert created.json()["data"]["token"].startswith("nak_ro_")
    revoked = client.post("/api/access-tokens/id1/revoke", headers=headers)
    assert revoked.json()["data"]["status"] == "revoked"


def test_access_token_management_rejects_non_loopback(monkeypatch):
    monkeypatch.setattr(access_tokens, "access_token_service", FakeService())
    monkeypatch.setattr(access_tokens, "_is_loopback", lambda host: False)
    response = TestClient(app).get("/api/access-tokens", headers={"X-ThinkRAG-Admin-Key": "admin-secret"})
    assert response.status_code == 403


def test_invalid_expiry_is_mapped_to_http_400(monkeypatch):
    """令牌过期时间格式错误必须返回 400。"""
    class InvalidExpiryService(FakeService):
        def create_token(self, **kwargs):
            raise ValueError("Invalid expires_at timestamp")

    monkeypatch.setattr(access_tokens, "access_token_service", InvalidExpiryService())
    monkeypatch.setattr(access_tokens, "_is_loopback", lambda host: True)
    response = TestClient(app).post(
        "/api/access-tokens",
        headers={"X-ThinkRAG-Admin-Key": "admin-secret"},
        json={"name": "robot", "kb_ids": ["finance"], "expires_at": "not-a-date"},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Invalid expires_at timestamp"


def test_management_api_create_list_revoke_and_open_api_rejects_revoked_token(tmp_path, monkeypatch):
    """真实管理 API 生命周期应不泄露明文，撤销后开放接口立即拒绝。"""
    from api.routers import open_api
    from api.services.access_token_service import AccessTokenService

    class Registry:
        def get_kb(self, kb_id):
            return {"kb_id": kb_id, "status": "active"} if kb_id == "finance" else None

    class Audit:
        def append(self, **_kwargs):
            return None

    service = AccessTokenService(
        store_path=tmp_path / "tokens.json",
        pepper_path=tmp_path / "pepper",
        admin_key_path=tmp_path / "admin-key",
        registry=Registry(),
    )
    admin_key = service.get_admin_key()
    monkeypatch.setattr(access_tokens, "access_token_service", service)
    monkeypatch.setattr(open_api, "access_token_service", service)
    monkeypatch.setattr(open_api, "open_api_audit", Audit())
    monkeypatch.setattr(access_tokens, "_is_loopback", lambda host: True)
    client = TestClient(app)
    headers = {"X-ThinkRAG-Admin-Key": admin_key}

    created = client.post(
        "/api/access-tokens",
        headers=headers,
        json={"name": "integration robot", "kb_ids": ["finance"]},
    )
    assert created.status_code == 201
    created_data = created.json()["data"]
    token = created_data["token"]
    token_id = created_data["token_id"]
    assert client.get("/api/open/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    listed = client.get("/api/access-tokens", headers=headers)
    assert listed.status_code == 200
    listed_item = listed.json()["data"]["items"][0]
    assert listed_item["token_id"] == token_id
    assert "token" not in listed_item
    assert "secret_hash" not in listed_item

    revoked = client.post(f"/api/access-tokens/{token_id}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["data"]["status"] == "revoked"
    assert client.get("/api/open/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
