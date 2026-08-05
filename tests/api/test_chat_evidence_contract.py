"""Chat 证据对象与 Preview Contract 测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import asset_service
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry

client = TestClient(app)


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """隔离 KB / Asset registry，并屏蔽会话落盘副作用。"""
    monkeypatch.chdir(tmp_path)

    import api.services.chat_service as chat_service
    import api.services.kb_service as kb_service

    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    asset_registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    kb_service._registry = registry
    monkeypatch.setattr(asset_service, "_registry", asset_registry)
    monkeypatch.setattr(chat_service, "append_chat_message", lambda *args, **kwargs: None)
    yield registry
    kb_service._registry = None
    asset_service._registry = None


def _write_file(path: Path, content: bytes = b"stub") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _build_asset(
    *,
    kb_id: str,
    asset_id: str,
    path: Path,
    relative_path: str,
    asset_role: str = "standalone",
    source_doc_path: Path | None = None,
    source_doc_relative_path: str | None = None,
) -> dict:
    source_path = source_doc_path or path
    source_relative = source_doc_relative_path or relative_path
    return {
        "asset_id": asset_id,
        "kb_id": kb_id,
        "asset_type": "image",
        "asset_role": asset_role,
        "title": path.name,
        "path": str(path),
        "relative_path": relative_path,
        "mime_type": "image/png",
        "source_doc_id": None,
        "source_doc_path": str(source_path),
        "source_doc_relative_path": source_relative,
        "locator": None,
        "status": "active",
    }


def _make_source_node(
    *,
    kb_id: str = "kb-a",
    doc_id: str = "doc-1",
    node_id: str = "node-1",
    title: str = "handbook.md",
    page: str = "12",
    text: str = "first paragraph for preview",
    score: float = 0.91,
    file_path: str | None = None,
    relative_path: str | None = None,
    asset_id: str | None = None,
):
    metadata = {
        "kb_id": kb_id,
        "file_name": title,
        "title": title,
        "page_label": page,
        "doc_id": doc_id,
    }
    if file_path is not None:
        metadata["file_path"] = file_path
    if relative_path is not None:
        metadata["relative_path"] = relative_path
    if asset_id is not None:
        metadata["asset_id"] = asset_id
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
        "asset_id",
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
    assert source["asset_id"] == evidence["asset_id"]


def test_chat_evidence_receipt_id_nullable(monkeypatch, isolated_registry):
    isolated_registry.create_kb("kb-a", "KB A")
    _stub_chat_runtime(monkeypatch, [_make_source_node()])

    resp = client.post(
        "/api/chat/query",
        json={"question": "nullable", "session_id": "chat-nullable", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["evidence"][0]["receipt_id"] is None


def test_chat_evidence_includes_asset_id_for_matching_standalone_asset(monkeypatch, isolated_registry, tmp_path):
    isolated_registry.create_kb("kb-a", "KB A")
    asset_path = _write_file(tmp_path / "data" / "kb-a" / "docs" / "flow.png", b"png")
    asset_service._registry.upsert_assets(
        "kb-a",
        [
            _build_asset(
                kb_id="kb-a",
                asset_id="asset-standalone-1",
                path=asset_path,
                relative_path="docs/flow.png",
            )
        ],
    )
    _stub_chat_runtime(
        monkeypatch,
        [
            _make_source_node(
                title="flow.png",
                doc_id="doc-flow",
                file_path=str(asset_path),
            )
        ],
    )

    resp = client.post(
        "/api/chat/query",
        json={"question": "flow", "session_id": "chat-asset-1", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    source = resp.json()["data"]["sources"][0]
    evidence = resp.json()["data"]["evidence"][0]
    assert source["asset_id"] == "asset-standalone-1"
    assert evidence["asset_id"] == "asset-standalone-1"


def test_chat_evidence_includes_asset_id_for_unique_embedded_asset(monkeypatch, isolated_registry, tmp_path):
    isolated_registry.create_kb("kb-a", "KB A")
    doc_path = _write_file(tmp_path / "data" / "kb-a" / "docs" / "readme.md", b"# md")
    embedded_path = _write_file(tmp_path / "data" / "kb-a" / "docs" / "images" / "flow.png", b"png")
    asset_service._registry.upsert_assets(
        "kb-a",
        [
            _build_asset(
                kb_id="kb-a",
                asset_id="asset-embedded-1",
                path=embedded_path,
                relative_path="docs/images/flow.png",
                asset_role="embedded",
                source_doc_path=doc_path,
                source_doc_relative_path="docs/readme.md",
            )
        ],
    )
    _stub_chat_runtime(
        monkeypatch,
        [
            _make_source_node(
                title="readme.md",
                doc_id="doc-readme",
                file_path=str(doc_path),
            )
        ],
    )

    resp = client.post(
        "/api/chat/query",
        json={"question": "readme", "session_id": "chat-asset-2", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    source = resp.json()["data"]["sources"][0]
    evidence = resp.json()["data"]["evidence"][0]
    assert source["asset_id"] == "asset-embedded-1"
    assert evidence["asset_id"] == "asset-embedded-1"


def test_chat_evidence_keeps_asset_id_none_when_relation_is_ambiguous(monkeypatch, isolated_registry, tmp_path):
    isolated_registry.create_kb("kb-a", "KB A")
    doc_path = _write_file(tmp_path / "data" / "kb-a" / "docs" / "readme.md", b"# md")
    embedded_path_a = _write_file(tmp_path / "data" / "kb-a" / "docs" / "images" / "flow-a.png", b"png")
    embedded_path_b = _write_file(tmp_path / "data" / "kb-a" / "docs" / "images" / "flow-b.png", b"png")
    asset_service._registry.upsert_assets(
        "kb-a",
        [
            _build_asset(
                kb_id="kb-a",
                asset_id="asset-embedded-a",
                path=embedded_path_a,
                relative_path="docs/images/flow-a.png",
                asset_role="embedded",
                source_doc_path=doc_path,
                source_doc_relative_path="docs/readme.md",
            ),
            _build_asset(
                kb_id="kb-a",
                asset_id="asset-embedded-b",
                path=embedded_path_b,
                relative_path="docs/images/flow-b.png",
                asset_role="embedded",
                source_doc_path=doc_path,
                source_doc_relative_path="docs/readme.md",
            ),
        ],
    )
    _stub_chat_runtime(
        monkeypatch,
        [
            _make_source_node(
                title="readme.md",
                doc_id="doc-readme",
                file_path=str(doc_path),
            )
        ],
    )

    resp = client.post(
        "/api/chat/query",
        json={"question": "ambiguous", "session_id": "chat-asset-3", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    source = resp.json()["data"]["sources"][0]
    evidence = resp.json()["data"]["evidence"][0]
    assert source["asset_id"] is None
    assert evidence["asset_id"] is None


def test_agent_evidence_receipt_id_required(monkeypatch, isolated_registry, tmp_path):
    isolated_registry.create_kb("kb-a", "KB A")
    asset_path = _write_file(tmp_path / "data" / "kb-a" / "docs" / "flow.png", b"png")
    asset_service._registry.upsert_assets(
        "kb-a",
        [
            _build_asset(
                kb_id="kb-a",
                asset_id="asset-standalone-2",
                path=asset_path,
                relative_path="docs/flow.png",
            )
        ],
    )
    _stub_chat_runtime(
        monkeypatch,
        [
            _make_source_node(
                title="flow.png",
                doc_id="doc-1",
                file_path=str(asset_path),
            )
        ],
    )

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
    assert result["evidence"][0]["asset_id"] == "asset-standalone-2"



def test_answer_is_refusal_like_accepts_chinese_markers():
    """中文拒答短语应被识别为无证据回答，避免误保留 sources。"""
    import api.services.chat_service as chat_service

    assert chat_service._answer_is_refusal_like("未找到可确认的信息。") is True
    assert chat_service._answer_is_refusal_like("当前知识库中没有关于 GPU 显存要求的可确认信息。") is True


def test_answer_is_refusal_like_accepts_english_markers_case_insensitive():
    """英文拒答短语应忽略大小写，保持中英文拒答契约一致。"""
    import api.services.chat_service as chat_service

    assert chat_service._answer_is_refusal_like("Insufficient Information to determine the answer.") is True
    assert chat_service._answer_is_refusal_like("This guide DOES NOT MENTION any GPU memory requirement.") is True
    assert chat_service._answer_is_refusal_like("The answer is 42 GB.") is False


def test_chat_refusal_like_answer_clears_ungrounded_sources(monkeypatch, isolated_registry):
    """拒答回答若与问题无关，应清空 chat 返回的伪相关证据。"""
    isolated_registry.create_kb("kb-a", "KB A")

    import api.services.chat_service as chat_service

    mock_engine = MagicMock()
    mock_engine.query.return_value = SimpleNamespace(
        response="The provided context does not mention any GPU memory requirement for the mobile build.",
        source_nodes=[
            _make_source_node(
                title="preview-board.png",
                doc_id="doc-preview",
                text="Evidence preview checklist. Every evidence preview must include doc_id and preview_locator.",
            ),
            _make_source_node(
                title="cutover.md",
                doc_id="doc-cutover",
                text="The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence.",
            ),
        ],
    )

    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", MagicMock(return_value=mock_engine))

    resp = client.post(
        "/api/chat/query",
        json={"question": "What is the GPU memory requirement for the mobile build?", "session_id": "chat-refusal-1", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "does not mention" in data["answer"].lower()
    assert data["sources"] == []
    assert data["evidence"] == []



def test_chat_refusal_like_answer_keeps_grounded_sources(monkeypatch, isolated_registry):
    """拒答回答若明确对应当前问题，应保留同主题来源作为证据。"""
    isolated_registry.create_kb("kb-a", "KB A")

    import api.services.chat_service as chat_service

    mock_engine = MagicMock()
    mock_engine.query.return_value = SimpleNamespace(
        response="The mobile build document does not mention any GPU memory requirement.",
        source_nodes=[
            _make_source_node(
                title="mobile-build-guide.md",
                doc_id="doc-mobile-build",
                text="The mobile build guide describes packaging, rollout order, and supported devices, but does not mention GPU memory requirement.",
            )
        ],
    )

    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", MagicMock(return_value=mock_engine))

    resp = client.post(
        "/api/chat/query",
        json={"question": "What is the GPU memory requirement for the mobile build?", "session_id": "chat-refusal-2", "kb_ids": ["kb-a"]},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["sources"]) == 1
    assert len(data["evidence"]) == 1
    assert data["sources"][0]["file"] == "mobile-build-guide.md"
    assert data["evidence"][0]["title"] == "mobile-build-guide.md"
