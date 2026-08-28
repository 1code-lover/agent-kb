"""Chat 主链路范围控制契约测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.api._testclient import TestClient

from api.app import app
from server.kb_registry import KBRegistry

client = TestClient(app)


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """隔离 KB registry，并屏蔽会话落盘副作用。"""
    monkeypatch.chdir(tmp_path)

    import api.services.chat_service as chat_service
    import api.services.kb_service as kb_service

    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    kb_service._registry = registry
    monkeypatch.setattr(chat_service, "append_chat_message", lambda *args, **kwargs: None)
    yield registry
    kb_service._registry = None


def _stub_chat_runtime(monkeypatch, answer_text: str = "answer") -> MagicMock:
    """为 chat 路由注入可控的 runtime 与 query engine。"""
    import api.services.chat_service as chat_service

    mock_engine = MagicMock()
    mock_engine.query.return_value = SimpleNamespace(response=answer_text, source_nodes=[])

    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    mock_build = MagicMock(return_value=mock_engine)
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", mock_build)
    return mock_build


def test_single_kb_scope_succeeds(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    mock_build = _stub_chat_runtime(monkeypatch)

    resp = client.post(
        "/api/chat/query",
        json={"question": "What is in KB A?", "session_id": "scope-ok", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["answer"] == "answer"
    assert data["effective_scope_type"] == "single_kb"
    assert data["effective_kb_ids"] == ["kb-a"]
    assert data["is_default_deny_applied"] is False
    mock_build.assert_called_once_with(
        kb_ids=["kb-a"],
        top_k=None,
        response_mode=None,
        use_reranker=None,
        top_n=None,
        reranker_model=None,
    )


def test_response_echoes_effective_scope(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _stub_chat_runtime(monkeypatch)

    resp = client.post(
        "/api/chat/query",
        json={"question": "echo scope", "session_id": "scope-echo", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["requested_scope_type"] == "single_kb"
    assert data["requested_kb_ids"] == ["kb-a"]
    assert data["effective_scope_type"] == "single_kb"
    assert data["effective_kb_ids"] == ["kb-a"]
    assert data["isolation_level"] == "physical_isolated"

def test_request_level_rag_params_flow_from_http_payload_to_query_engine(monkeypatch, isolated_registry):
    """HTTP payload 中的 QueryRequest 检索参数应原样进入 build_query_engine。"""
    isolated_registry.create_kb("kb-a", "KB A")
    mock_build = _stub_chat_runtime(monkeypatch)

    resp = client.post(
        "/api/chat/query",
        json={
            "question": "custom params",
            "session_id": "scope-custom-rag",
            "kb_ids": ["kb-a"],
            "top_k": 9,
            "response_mode": "tree_summarize",
            "use_reranker": False,
            "top_n": 2,
            "reranker_model": "bge-reranker-v2-m3",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    mock_build.assert_called_once_with(
        kb_ids=["kb-a"],
        top_k=9,
        response_mode="tree_summarize",
        use_reranker=False,
        top_n=2,
        reranker_model="bge-reranker-v2-m3",
    )


def test_unspecified_scope_is_rejected(monkeypatch, isolated_registry):
    mock_build = _stub_chat_runtime(monkeypatch)

    resp = client.post("/api/chat/query", json={"question": "no scope", "session_id": "scope-none"})

    assert 400 <= resp.status_code <= 422
    assert "显式声明单库" in resp.json()["message"]
    mock_build.assert_not_called()


def test_empty_kb_ids_is_rejected(monkeypatch, isolated_registry):
    mock_build = _stub_chat_runtime(monkeypatch)

    resp = client.post(
        "/api/chat/query",
        json={"question": "empty scope", "session_id": "scope-empty", "kb_ids": []},
    )

    assert 400 <= resp.status_code <= 422
    assert "范围不能为空" in resp.json()["message"]
    mock_build.assert_not_called()


def test_multi_kb_scope_rejected_on_mainline(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    isolated_registry.create_kb("kb-b", "KB B")
    mock_build = _stub_chat_runtime(monkeypatch)

    resp = client.post(
        "/api/chat/query",
        json={"question": "multi", "session_id": "scope-multi", "kb_ids": ["kb-a", "kb-b"]},
    )

    assert 400 <= resp.status_code <= 422
    assert "不支持多知识库查询" in resp.json()["message"]
    mock_build.assert_not_called()


def test_nonexistent_kb_rejected(monkeypatch, isolated_registry):
    mock_build = _stub_chat_runtime(monkeypatch)

    resp = client.post(
        "/api/chat/query",
        json={"question": "missing", "session_id": "scope-missing", "kb_ids": ["kb-not-exist"]},
    )

    assert resp.status_code == 404
    assert "知识库不存在" in resp.json()["message"]
    mock_build.assert_not_called()


def test_inactive_kb_rejected(monkeypatch, isolated_registry):
    inactive = isolated_registry.create_kb("kb-c", "KB C")
    inactive["status"] = "disabled"
    isolated_registry.replace_all([inactive])
    mock_build = _stub_chat_runtime(monkeypatch)

    resp = client.post(
        "/api/chat/query",
        json={"question": "inactive", "session_id": "scope-inactive", "kb_ids": ["kb-c"]},
    )

    assert resp.status_code == 400
    assert "知识库不可用" in resp.json()["message"]
    mock_build.assert_not_called()
