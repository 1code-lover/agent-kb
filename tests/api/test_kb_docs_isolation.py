"""文档列表与删除的 KB 隔离测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.schemas import DeleteDocsRequest
from api.services import kb_service
from server.kb_registry import KBRegistry


def _fake_ref(metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(metadata=metadata)


def _patch_docstore(monkeypatch: pytest.MonkeyPatch, doc_info: dict[str, SimpleNamespace]) -> MagicMock:
    manager = MagicMock()
    docstore = MagicMock()
    docstore.docs = doc_info
    docstore.get_all_ref_doc_info.return_value = doc_info
    manager.storage_context.docstore = docstore
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(kb_service.runtime_state, "ensure_index_loaded", MagicMock())
    return manager


def _patch_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBRegistry:
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    for kb_id in ["default", "kb-a", "kb-b"]:
        registry.create_kb(kb_id, kb_id)
    monkeypatch.setattr(kb_service, "_registry", registry)
    return registry


def test_list_docs_non_default_excludes_legacy_nodes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_docstore(
        monkeypatch,
        {
            "legacy": _fake_ref({"file_name": "legacy.txt"}),
            "a": _fake_ref({"file_name": "a.txt", "kb_id": "kb-a"}),
            "b": _fake_ref({"file_name": "b.txt", "kb_id": "kb-b"}),
        },
    )

    docs = kb_service.list_docs(kb_id="kb-a")

    assert [doc["id"] for doc in docs] == ["a"]
    assert docs[0]["kb_id"] == "kb-a"


def test_list_docs_default_includes_legacy_nodes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_docstore(
        monkeypatch,
        {
            "legacy": _fake_ref({"file_name": "legacy.txt"}),
            "default": _fake_ref({"file_name": "d.txt", "kb_id": "default"}),
            "a": _fake_ref({"file_name": "a.txt", "kb_id": "kb-a"}),
        },
    )

    docs = kb_service.list_docs(kb_id="default")

    assert [doc["id"] for doc in docs] == ["legacy", "default"]
    assert all(doc["kb_id"] == "default" for doc in docs)


def test_delete_non_default_does_not_delete_legacy_doc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_registry(monkeypatch, tmp_path)
    manager = _patch_docstore(monkeypatch, {"legacy": _fake_ref({"file_name": "legacy.txt"})})

    result = kb_service.delete_docs(DeleteDocsRequest(doc_ids=["legacy"], kb_id="kb-a"))

    assert result["deleted"] == 0
    manager.delete_ref_doc.assert_not_called()


def test_delete_default_can_delete_legacy_root_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    legacy = tmp_path / "data" / "legacy.txt"
    legacy.parent.mkdir()
    legacy.write_text("legacy", encoding="utf-8")
    manager = _patch_docstore(monkeypatch, {"legacy": _fake_ref({"file_name": "legacy.txt", "file_path": str(legacy)})})

    result = kb_service.delete_docs(DeleteDocsRequest(doc_ids=["legacy"], kb_id="default"))

    assert result["deleted"] == 1
    assert result["files_deleted"] == 1
    assert not legacy.exists()
    manager.delete_ref_doc.assert_called_once_with("legacy")
    assert registry.get_kb("default")["doc_count"] == 0


def test_delete_default_does_not_delete_legacy_subdir_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_registry(monkeypatch, tmp_path)
    nested = tmp_path / "data" / "manual" / "legacy.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("legacy", encoding="utf-8")
    manager = _patch_docstore(monkeypatch, {"legacy": _fake_ref({"file_name": "legacy.txt", "file_path": str(nested)})})

    result = kb_service.delete_docs(DeleteDocsRequest(doc_ids=["legacy"], kb_id="default"))

    assert result["deleted"] == 1
    assert result["files_deleted"] == 0
    assert result["files_skipped"] == 1
    assert nested.exists()
    manager.delete_ref_doc.assert_called_once_with("legacy")


def test_delete_non_default_only_deletes_own_directory_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_registry(monkeypatch, tmp_path)
    own = tmp_path / "data" / "kb-a" / "a.txt"
    other = tmp_path / "data" / "kb-b" / "b.txt"
    own.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    own.write_text("a", encoding="utf-8")
    other.write_text("b", encoding="utf-8")
    manager = _patch_docstore(
        monkeypatch,
        {
            "a": _fake_ref({"file_name": "a.txt", "file_path": str(own), "kb_id": "kb-a"}),
            "b": _fake_ref({"file_name": "b.txt", "file_path": str(other), "kb_id": "kb-b"}),
        },
    )

    result = kb_service.delete_docs(DeleteDocsRequest(paths=[str(own), str(other)], kb_id="kb-a"))

    assert result["deleted"] == 1
    assert not own.exists()
    assert other.exists()
    manager.delete_ref_doc.assert_called_once_with("a")


def test_delete_url_doc_does_not_attempt_file_delete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_registry(monkeypatch, tmp_path)
    manager = _patch_docstore(monkeypatch, {"url": _fake_ref({"title": "Example", "url_source": "https://example.com", "kb_id": "kb-a"})})

    result = kb_service.delete_docs(DeleteDocsRequest(doc_ids=["url"], kb_id="kb-a"))

    assert result["deleted"] == 1
    assert result["files_deleted"] == 0
    assert result["files_skipped"] == 0
    manager.delete_ref_doc.assert_called_once_with("url")
