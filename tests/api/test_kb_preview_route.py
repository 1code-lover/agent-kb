"""KB Preview Contract 路由测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.api._testclient import TestClient

from api.app import app
from api.services.evidence_service import build_evidence_id
from server.kb_registry import KBRegistry

client = TestClient(app)


class FakeDocStore:
    """提供 preview route 需要的最小 docstore 能力。"""

    def __init__(self, ref_docs, nodes):
        self._ref_docs = ref_docs
        self._nodes = nodes
        self.docs = nodes

    def get_all_ref_doc_info(self):
        return self._ref_docs

    def get_ref_doc_info(self, doc_id):
        return self._ref_docs.get(doc_id)

    def get_nodes(self, node_ids, raise_error=False):
        return [self._nodes[node_id] for node_id in node_ids if node_id in self._nodes]


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """隔离 KB registry，并替换为临时目录下的测试实例。"""
    monkeypatch.chdir(tmp_path)

    import api.services.kb_service as kb_service

    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    kb_service._registry = registry
    yield registry
    kb_service._registry = None


def _install_preview_runtime(monkeypatch, *, kb_id: str = "kb-a", doc_id: str = "doc-1", page: str = "7"):
    """给 kb preview 与 chat query 同时注入同一份假索引。"""
    import api.services.chat_service as chat_service
    import api.services.kb_service as kb_service

    metadata = {
        "kb_id": kb_id,
        "file_name": "manual.pdf",
        "title": "manual.pdf",
        "page_label": page,
        "doc_id": doc_id,
    }
    doc_node = SimpleNamespace(metadata=metadata, text="Preview excerpt for page " + page, node_id="node-1")
    ref_docs = {
        doc_id: SimpleNamespace(metadata={"kb_id": kb_id, "file_name": "manual.pdf", "title": "manual.pdf"}, node_ids=["node-1"])
    }
    manager = SimpleNamespace(storage_context=SimpleNamespace(docstore=FakeDocStore(ref_docs, {"node-1": doc_node})))

    monkeypatch.setattr(kb_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))

    mock_engine = MagicMock()
    source_node = SimpleNamespace(
        node=SimpleNamespace(metadata=metadata, text=doc_node.text, ref_doc_id=doc_id, node_id="node-1"),
        score=0.88,
    )
    mock_engine.query.return_value = SimpleNamespace(response="answer", source_nodes=[source_node])
    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", MagicMock(return_value=mock_engine))


def test_preview_by_doc_id_returns_text_excerpt(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _install_preview_runtime(monkeypatch)

    resp = client.post("/api/kb/preview", json={"kb_id": "kb-a", "doc_id": "doc-1"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "manual.pdf"
    assert data["kb_id"] == "kb-a"
    assert data["doc_id"] == "doc-1"
    assert data["preview_type"] == "text_excerpt"
    assert "Preview excerpt" in data["excerpt"]
    assert data["locator"]["page"] == "7"


def test_preview_by_evidence_id_returns_text_excerpt(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _install_preview_runtime(monkeypatch)

    query_resp = client.post(
        "/api/chat/query",
        json={"question": "preview", "session_id": "preview-1", "kb_ids": ["kb-a"]},
    )
    evidence_id = query_resp.json()["data"]["evidence"][0]["id"]

    resp = client.post("/api/kb/preview", json={"kb_id": "kb-a", "evidence_id": evidence_id})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["doc_id"] == "doc-1"
    assert data["locator"]["page"] == "7"
    assert data["preview_type"] == "text_excerpt"


def test_preview_by_evidence_id_prefers_encoded_excerpt(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _install_preview_runtime(monkeypatch)

    evidence_id = build_evidence_id(
        kb_id="kb-a",
        doc_id="doc-1",
        preview_locator={"page": "7", "node_id": "node-1"},
        fallback_index=1,
        excerpt="Sign deadline is 22:30 Beijing time.",
    )

    resp = client.post("/api/kb/preview", json={"kb_id": "kb-a", "evidence_id": evidence_id})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["excerpt"] == "Sign deadline is 22:30 Beijing time."
    assert data["doc_id"] == "doc-1"
    assert data["locator"]["page"] == "7"


def test_preview_requires_doc_id_or_evidence_id(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _install_preview_runtime(monkeypatch)

    resp = client.post("/api/kb/preview", json={"kb_id": "kb-a"})

    assert 400 <= resp.status_code <= 422


def test_preview_rejects_nonexistent_doc(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _install_preview_runtime(monkeypatch)

    resp = client.post("/api/kb/preview", json={"kb_id": "kb-a", "doc_id": "doc-missing"})

    assert resp.status_code == 404


def test_preview_locator_expresses_page_when_available(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _install_preview_runtime(monkeypatch, page="15")

    resp = client.post("/api/kb/preview", json={"kb_id": "kb-a", "doc_id": "doc-1"})

    assert resp.status_code == 200
    locator = resp.json()["data"]["locator"]
    assert locator["page"] == "15"
