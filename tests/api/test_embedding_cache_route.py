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


def test_embedding_cache_preflight(monkeypatch) -> None:
    """预检接口应返回结构化磁盘空间结果。"""
    preflight = MagicMock(return_value={"state": "idle", "phase": "checking_space", "enough_space": True})
    monkeypatch.setattr(embedding_cache_router.embedding_cache_service, "preflight", preflight)

    response = client.post("/api/embedding/cache/preflight", json={"provider": "modelscope"})

    assert response.status_code == 200
    assert response.json()["data"]["enough_space"] is True
    preflight.assert_called_once_with(provider="modelscope")


def test_prepare_embedding_cache_maps_insufficient_space_to_507(monkeypatch) -> None:
    """空间不足必须返回 507，而不是启动后台线程。"""
    from api.services.embedding_cache_service import InsufficientDiskSpaceError

    monkeypatch.setattr(
        embedding_cache_router.embedding_cache_service,
        "start_prepare",
        MagicMock(side_effect=InsufficientDiskSpaceError({"shortfall_bytes": 10})),
    )

    response = client.post("/api/embedding/cache/prepare", json={"provider": "modelscope"})

    assert response.status_code == 507
    assert response.json()["data"] == {}
    assert "Insufficient" in response.json()["message"]


def test_cancel_embedding_cache(monkeypatch) -> None:
    """取消接口应返回最新状态。"""
    request_cancel = MagicMock(return_value={"state": "cancelling", "cancel_requested": True})
    monkeypatch.setattr(embedding_cache_router.embedding_cache_service, "request_cancel", request_cancel)

    response = client.post("/api/embedding/cache/cancel")

    assert response.status_code == 200
    assert response.json()["data"]["state"] == "cancelling"
    request_cancel.assert_called_once_with()


def test_embedding_cache_conflict_maps_to_409(monkeypatch) -> None:
    """服务检测到任务冲突时应映射为 409。"""
    from api.services.embedding_cache_service import EmbeddingDownloadConflictError

    monkeypatch.setattr(
        embedding_cache_router.embedding_cache_service,
        "preflight",
        MagicMock(side_effect=EmbeddingDownloadConflictError("task is running")),
    )

    response = client.post("/api/embedding/cache/preflight", json={"provider": "modelscope"})

    assert response.status_code == 409
