"""Chat 证据对象与 Preview Contract 测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

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


def _make_source_node(
    *,
    kb_id: str = "kb-a",
    doc_id: str = "doc-1",
    node_id: str = "node-1",
    title: str = "handbook.md",
    page: str = "12",
    text: str = "first paragraph for preview",
    score: float = 0.91,
):
    metadata = {
        "kb_id": kb_id,
        "file_name": title,
        "title": title,
        "page_label": page,
        "doc_id": doc_id,
    }
    content_node = SimpleNamespace(
        metadata=metadata,
        text=text,
        ref_doc_id=doc_id,
        node_id=node_id,
    )
    return SimpleNamespace(node=content_node, score=score)


def _stub_chat_runtime(monkeypatch, source_nodes):
    """为 chat 路由注入带 source_nodes 的 runtime。"""
    import api.services.chat_service as chat_service

    mock_engine = MagicMock()
    mock_engine.query.return_value = SimpleNamespace(response="answer", source_nodes=source_nodes)

    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    mock_build = MagicMock(return_value=mock_engine)
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", mock_build)
    return mock_build


def test_query_response_contains_evidence_field(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _stub_chat_runtime(monkeypatch, [_make_source_node()])

    resp = client.post(
        "/api/chat/query",
        json={"question": "what", "session_id": "chat-evidence", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "sources" in data
    assert "evidence" in data
    assert len(data["sources"]) == 1
    assert len(data["evidence"]) == 1


def test_evidence_item_has_required_fields(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _stub_chat_runtime(monkeypatch, [_make_source_node()])

    resp = client.post(
        "/api/chat/query",
        json={"question": "fields", "session_id": "chat-fields", "kb_ids": ["kb-a"]},
    )

    evidence = resp.json()["data"]["evidence"][0]
    expected = {
        "id",
        "title",
        "source",
        "page",
        "score",
        "excerpt",
        "kb_id",
        "receipt_id",
        "doc_id",
        "preview_locator",
    }
    assert expected.issubset(evidence.keys())
    assert evidence["doc_id"] == "doc-1"
    assert evidence["preview_locator"] is not None


def test_sources_and_evidence_field_mapping_consistent(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _stub_chat_runtime(monkeypatch, [_make_source_node(text="excerpt text")])

    resp = client.post(
        "/api/chat/query",
        json={"question": "mapping", "session_id": "chat-mapping", "kb_ids": ["kb-a"]},
    )

    data = resp.json()["data"]
    source = data["sources"][0]
    evidence = data["evidence"][0]
    assert source["file"] == evidence["title"] == evidence["source"]
    assert source["text"] == evidence["excerpt"]
    assert source["page"] == evidence["page"]
    assert source["kb_id"] == evidence["kb_id"]


def test_chat_evidence_receipt_id_nullable(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _stub_chat_runtime(monkeypatch, [_make_source_node()])

    resp = client.post(
        "/api/chat/query",
        json={"question": "nullable", "session_id": "chat-nullable", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["evidence"][0]["receipt_id"] is None


def test_agent_evidence_receipt_id_required(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _stub_chat_runtime(monkeypatch, [_make_source_node()])

    import api.services.agent_tools as agent_tools

    monkeypatch.setattr(
        agent_tools,
        "append_receipt",
        lambda **kwargs: {"id": "receipt-1", "tool_name": kwargs.get("tool_name", "kb_search")},
    )

    result = agent_tools.run_kb_search(session_id="agent-1", question="what", kb_ids=["kb-a"])

    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["receipt_id"] == "receipt-1"
    assert result["evidence"][0]["doc_id"] == "doc-1"
