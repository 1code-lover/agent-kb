"""KB folder 列表与文档路径语义测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import folder_service, kb_service
from server.folder_registry import KBFolderRegistry
from server.kb_registry import KBRegistry

client = TestClient(app)


def _fake_ref(metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(metadata=metadata)


def _patch_docstore(monkeypatch: pytest.MonkeyPatch, doc_info: dict[str, SimpleNamespace]) -> MagicMock:
    manager = MagicMock()
    docstore = MagicMock()
    docstore.docs = doc_info
    docstore.get_all_ref_doc_info.return_value = doc_info
    manager.storage_context.docstore = docstore
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(folder_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


@pytest.fixture(autouse=True)
def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """隔离 KB registry、folder registry 与 data 目录。"""
    monkeypatch.chdir(tmp_path)
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    registry.create_kb("default", "default")
    registry.create_kb("kb-a", "KB A")
    registry.create_kb("kb-b", "KB B")
    monkeypatch.setattr(kb_service, "_registry", registry)
    monkeypatch.setattr(folder_service, "_folder_registry", KBFolderRegistry(base_dir=tmp_path / "storage" / "kb_folders"))
    yield
    kb_service._registry = None
    folder_service._folder_registry = None


def test_list_docs_exposes_relative_path_and_folder_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """list_docs 应补出 knowledge-base 内的相对路径与 folder_path。"""
    doc_path = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text("alpha", encoding="utf-8")
    _patch_docstore(
        monkeypatch,
        {
            "doc-a": _fake_ref({"file_name": "a.md", "file_path": str(doc_path), "kb_id": "kb-a"}),
        },
    )

    docs = kb_service.list_docs(kb_id="kb-a")

    assert docs[0]["relative_path"] == "design/specs/a.md"
    assert docs[0]["folder_path"] == "design/specs"


def test_list_kb_folders_route_returns_only_requested_kb(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """/api/kb/folders 应只返回目标知识库的目录节点。"""
    kb_a_doc = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"
    kb_b_doc = tmp_path / "data" / "kb-b" / "ops" / "runbook.md"
    kb_a_doc.parent.mkdir(parents=True, exist_ok=True)
    kb_b_doc.parent.mkdir(parents=True, exist_ok=True)
    kb_a_doc.write_text("a", encoding="utf-8")
    kb_b_doc.write_text("b", encoding="utf-8")
    _patch_docstore(
        monkeypatch,
        {
            "doc-a": _fake_ref({"file_name": "a.md", "file_path": str(kb_a_doc), "kb_id": "kb-a"}),
            "doc-b": _fake_ref({"file_name": "runbook.md", "file_path": str(kb_b_doc), "kb_id": "kb-b"}),
        },
    )

    resp = client.get("/api/kb/folders", params={"kb_id": "kb-a"})

    assert resp.status_code == 200
    payload = resp.json()["data"]["folders"]
    assert [item["path"] for item in payload] == ["design", "design/specs"]
    assert all(item["kb_id"] == "kb-a" for item in payload)
    folder_service.runtime_state.get_index_manager.assert_called_once_with("kb-a")
