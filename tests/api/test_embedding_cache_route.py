"""Embedding 本地缓存恢复接口测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.app import app
from api.routers import embedding_cache as embedding_cache_router

client = TestClient(app)


def test_get_embedding_cache_status(monkeypatch) -> None:
    """GET 应返回缓存恢复状态快照。"""
    expected = {"state": "idle", "provider": "modelscope", "thread_alive": False}
    monkeypatch.setattr(embedding_cache_router.embedding_cache_service, "get_status", lambda: expected)

    response = client.get("/api/embedding/cache")

    assert response.status_code == 200
    assert response.json()["data"] == expected


def test_prepare_embedding_cache_uses_modelscope_and_is_idempotent(monkeypatch) -> None:
    """POST 仅触发白名单 ModelScope 恢复动作，并回传是否实际启动。"""
    start_prepare = MagicMock(return_value=({"state": "downloading", "provider": "modelscope"}, True))
    monkeypatch.setattr(embedding_cache_router.embedding_cache_service, "start_prepare", start_prepare)

    response = client.post("/api/embedding/cache/prepare", json={"provider": "modelscope"})

    assert response.status_code == 200
    assert response.json()["data"]["started"] is True
    assert response.json()["data"]["status"]["state"] == "downloading"
    start_prepare.assert_called_once_with(provider="modelscope")


def test_prepare_embedding_cache_rejects_non_whitelisted_provider() -> None:
    """前端恢复接口不得开放任意下载源。"""
    response = client.post("/api/embedding/cache/prepare", json={"provider": "huggingface"})

    assert response.status_code == 422
