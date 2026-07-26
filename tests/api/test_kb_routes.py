"""KB CRUD 路由测试"""

import tempfile
from unittest.mock import patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import kb_service
from server.kb_errors import KBNotFoundError, KBUnavailableError, KBValidationError
from server.kb_registry import KBRegistry

# 用临时路径覆盖 registry 存储路径
TMP_DIR = tempfile.mkdtemp()
REGISTRY_PATH = Path(TMP_DIR) / "kb_registry.json"

client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup_and_teardown(tmp_path, monkeypatch):
    """隔离测试用 registry、索引目录和 data 目录。"""
    monkeypatch.chdir(tmp_path)
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    # 让服务层延迟创建测试 registry。
    import api.services.kb_service as ks
    ks._registry = registry
    yield
    ks._registry = None

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


class TestKbWebImport:
    """KB 网页导入路由测试"""

    def test_web_import_passes_kb_id_to_service(self):
        with patch("api.routers.kb.kb_service.import_urls") as mock_import_urls:
            mock_import_urls.return_value = {"imported": 1, "kb_id": "my-kb"}

            resp = client.post(
                "/api/kb/web/import",
                json={
                    "urls": ["https://example.com"],
                    "chunk_size": 2048,
                    "chunk_overlap": 512,
                    "kb_id": "my-kb",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        mock_import_urls.assert_called_once_with(
            ["https://example.com"],
            2048,
            512,
            kb_id="my-kb",
        )

    @pytest.mark.parametrize(
        ("exc", "expected_status"),
        [
            (KBNotFoundError("知识库不存在: missing"), 404),
            (KBValidationError("非法知识库ID"), 400),
            (KBUnavailableError("知识库不可用: inactive-kb"), 400),
        ],
    )
    def test_web_import_maps_kb_errors(self, exc, expected_status):
        with patch("api.routers.kb.kb_service.import_urls", side_effect=exc):
            resp = client.post(
                "/api/kb/web/import",
                json={"urls": ["https://example.com"], "kb_id": "missing"},
            )

        assert resp.status_code == expected_status


class TestKbLatestImportReceiptRoute:
    """最近导入回执路由测试。"""

    def test_latest_import_receipt_returns_service_payload(self):
        payload = {
            "kb_id": "my-kb",
            "source_label": "文件上传",
            "created_at": "2026-07-26T08:00:00+00:00",
            "result": {"receipt_id": "r-1", "kb_id": "my-kb"},
        }
        with patch("api.routers.kb.kb_service.get_latest_import_receipt", return_value=payload) as mock_get:
            resp = client.get("/api/kb/import-receipt/latest", params={"kb_id": "my-kb"})

        assert resp.status_code == 200
        assert resp.json()["data"]["receipt"] == payload
        mock_get.assert_called_once_with("my-kb")

    @pytest.mark.parametrize(
        ("exc", "expected_status"),
        [
            (KBNotFoundError("知识库不存在: missing"), 404),
            (KBValidationError("非法知识库 ID"), 400),
            (KBUnavailableError("知识库不可用: inactive-kb"), 400),
        ],
    )
    def test_latest_import_receipt_maps_kb_errors(self, exc, expected_status):
        with patch("api.routers.kb.kb_service.get_latest_import_receipt", side_effect=exc):
            resp = client.get("/api/kb/import-receipt/latest", params={"kb_id": "missing"})

        assert resp.status_code == expected_status
