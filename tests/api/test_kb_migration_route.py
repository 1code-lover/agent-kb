"""历史知识库迁移路由测试。"""

from fastapi.testclient import TestClient

from api.app import app
from api.routers import kb_migration


class FakeService:
    def __init__(self):
        self.calls = []

    def get_status(self):
        return {"state": "idle"}

    def scan(self):
        return {"plan_digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd", "knowledge_bases": []}

    def start(self, **kwargs):
        self.calls.append(kwargs)
        return {"state": "running", "plan_digest": kwargs["plan_digest"]}, True

    def rollback(self, batch_id):
        return {"state": "rolled_back", "batch_id": batch_id}


def test_migration_routes_expose_status_scan_start_and_rollback(monkeypatch):
    fake = FakeService()
    monkeypatch.setattr(kb_migration, "kb_migration_service", fake)
    client = TestClient(app)

    assert client.get("/api/kb/migration/status").json()["data"]["state"] == "idle"
    assert client.post("/api/kb/migration/scan").json()["data"]["plan_digest"] == "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    response = client.post("/api/kb/migration/start", json={"plan_digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd", "kb_ids": ["finance"]})
    assert response.status_code == 202
    assert fake.calls == [{
        "plan_digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        "kb_ids": ["finance"],
        "retry_failed_only": False,
        "recompute_missing_embeddings": False,
    }]
    assert client.post("/api/kb/migration/rollback", json={"batch_id": "batch-1"}).json()["data"]["state"] == "rolled_back"


def test_migration_start_returns_conflict_when_running(monkeypatch):
    fake = FakeService()
    fake.start = lambda **kwargs: ({"state": "running"}, False)
    monkeypatch.setattr(kb_migration, "kb_migration_service", fake)
    response = TestClient(app).post("/api/kb/migration/start", json={"plan_digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"})
    assert response.status_code == 409


def test_migration_validation_errors_are_400(monkeypatch):
    fake = FakeService()
    fake.scan = lambda: (_ for _ in ()).throw(ValueError("bad plan"))
    monkeypatch.setattr(kb_migration, "kb_migration_service", fake)
    response = TestClient(app).post("/api/kb/migration/scan")
    assert response.status_code == 400
    assert response.json()["message"] == "bad plan"
