"""KB CRUD 路由测试"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import kb_service
from server.kb_registry import KBRegistry

# 用临时路径覆盖 registry 存储路径
TMP_DIR = tempfile.mkdtemp()
REGISTRY_PATH = Path(TMP_DIR) / "kb_registry.json"

client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup_and_teardown():
    """每个测试前重建空 registry"""
    registry = KBRegistry(storage_path=REGISTRY_PATH)
    # 替换服务层的全局 registry
    import api.services.kb_service as ks
    ks._registry = registry
    yield
    if REGISTRY_PATH.exists():
        REGISTRY_PATH.unlink()


class TestKbSchemas:
    """KB 请求/响应 schema 验证"""

    def test_create_kb_valid(self):
        resp = client.post("/api/kb", json={"kb_id": "my-docs", "kb_name": "我的文档"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["kb_id"] == "my-docs"
        assert data["data"]["kb_name"] == "我的文档"

    def test_create_kb_missing_kb_id(self):
        resp = client.post("/api/kb", json={"kb_name": "我的文档"})
        assert resp.status_code == 422

    def test_create_kb_missing_kb_name(self):
        resp = client.post("/api/kb", json={"kb_id": "my-docs"})
        assert resp.status_code == 422

    def test_create_kb_duplicate(self):
        client.post("/api/kb", json={"kb_id": "my-docs", "kb_name": "我的文档"})
        resp = client.post("/api/kb", json={"kb_id": "my-docs", "kb_name": "重复"})
        assert resp.status_code == 409
        assert "已存在" in resp.json()["message"]

    def test_list_kbs(self):
        client.post("/api/kb", json={"kb_id": "kb1", "kb_name": "库1"})
        client.post("/api/kb", json={"kb_id": "kb2", "kb_name": "库2"})
        resp = client.get("/api/kb")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]["items"]) == 2

    def test_get_kb(self):
        client.post("/api/kb", json={"kb_id": "my-docs", "kb_name": "我的文档"})
        resp = client.get("/api/kb/my-docs")
        assert resp.status_code == 200
        assert resp.json()["data"]["kb_name"] == "我的文档"

    def test_get_nonexistent_kb(self):
        resp = client.get("/api/kb/nonexistent")
        assert resp.status_code == 404

    def test_update_kb(self):
        client.post("/api/kb", json={"kb_id": "my-docs", "kb_name": "我的文档"})
        resp = client.put("/api/kb/my-docs", json={"kb_name": "新产品文档"})
        assert resp.status_code == 200
        assert resp.json()["data"]["kb_name"] == "新产品文档"

    def test_update_nonexistent_kb(self):
        resp = client.put("/api/kb/nonexistent", json={"kb_name": "新名称"})
        assert resp.status_code == 404

    def test_delete_kb(self):
        client.post("/api/kb", json={"kb_id": "my-docs", "kb_name": "我的文档"})
        resp = client.delete("/api/kb/my-docs")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

    def test_delete_nonexistent_kb(self):
        resp = client.delete("/api/kb/nonexistent")
        assert resp.status_code == 404
