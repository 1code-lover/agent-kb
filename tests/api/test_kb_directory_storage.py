"""多知识库目录化存储服务测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.schemas import DeleteDocsRequest
from api.services import kb_service
from server.kb_errors import (
    KBConflictError,
    KBConsistencyError,
    KBNotFoundError,
    KBUnavailableError,
)
from server.kb_registry import KBRegistry


class FakeUploadFile:
    """替换运行时状态，隔离测试文件系统。"""

    def __init__(self, filename: str = "a.txt", content: bytes = b"hello", content_type: str = "text/plain"):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


def _patch_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBRegistry:
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    monkeypatch.setattr(kb_service, "_registry", registry)
    return registry


def _patch_runtime(monkeypatch: pytest.MonkeyPatch, manager: MagicMock | None = None) -> MagicMock:
    manager = manager or MagicMock()
    manager.load_files.return_value = [SimpleNamespace(metadata={})]
    manager.load_websites.return_value = [SimpleNamespace(metadata={})]
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


def test_create_kb_creates_data_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)

    result = kb_service.create_kb("kb-a", "KB A")

    assert result["kb_id"] == "kb-a"
    assert registry.get_kb("kb-a") is not None
    assert (tmp_path / "data" / "kb-a").is_dir()


def test_create_duplicate_kb_raises_conflict_and_keeps_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_registry(monkeypatch, tmp_path)
    kb_service.create_kb("kb-a", "KB A")
    marker = tmp_path / "data" / "kb-a" / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(KBConflictError):
        kb_service.create_kb("kb-a", "KB A duplicate")

    assert marker.read_text(encoding="utf-8") == "keep"


def test_create_kb_rolls_back_registry_when_directory_creation_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)

    def fail_create(_kb_id: str, create: bool = False):
        raise OSError("disk is readonly")

    monkeypatch.setattr(kb_service, "get_kb_data_dir", fail_create)

    with pytest.raises(KBConsistencyError):
        kb_service.create_kb("kb-a", "KB A")

    assert registry.get_kb("kb-a") is None


def test_import_missing_kb_fails_before_reading_or_writing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_registry(monkeypatch, tmp_path)
    upload = FakeUploadFile()
    read_spy = MagicMock(side_effect=upload.file.read)
    upload.file.read = read_spy

    with pytest.raises(KBNotFoundError):
        kb_service.import_files([upload], 128, 16, kb_id="missing")

    read_spy.assert_not_called()
    assert not (tmp_path / "data" / "missing").exists()


def test_import_inactive_kb_fails_before_writing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    data = registry.list_kbs()
    data[0]["status"] = "disabled"
    registry.replace_all(data)

    with pytest.raises(KBUnavailableError):
        kb_service.import_files([FakeUploadFile()], 128, 16, kb_id="kb-a")

    assert not (tmp_path / "data" / "kb-a").exists()


def test_legacy_registry_item_without_status_is_active(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.replace_all([{"kb_id": "kb-a", "kb_name": "KB A", "doc_count": 0}])
    manager = _patch_runtime(monkeypatch)

    result = kb_service.import_files([FakeUploadFile("a.txt", b"content")], 128, 16, kb_id="kb-a")

    assert result["kb_id"] == "kb-a"
    assert manager.load_files.call_args.args[0][0].parent == tmp_path / "data" / "kb-a"


def test_import_files_writes_to_kb_directory_and_passes_file_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: f"unique-{name}"))

    result = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    expected = tmp_path / "data" / "kb-a" / "unique-a.txt"
    assert expected.read_bytes() == b"alpha"
    assert result["files"][0]["path"] == str(expected.resolve())
    file_paths = manager.load_files.call_args.args[0]
    assert file_paths == [expected.resolve()]
    assert registry.get_kb("kb-a")["doc_count"] == 1


def test_same_filename_in_different_kbs_does_not_conflict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    registry.create_kb("kb-b", "KB B")
    _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: "same.txt"))

    kb_service.import_files([FakeUploadFile("same.txt", b"a")], 128, 16, kb_id="kb-a")
    kb_service.import_files([FakeUploadFile("same.txt", b"b")], 128, 16, kb_id="kb-b")

    assert (tmp_path / "data" / "kb-a" / "same.txt").read_bytes() == b"a"
    assert (tmp_path / "data" / "kb-b" / "same.txt").read_bytes() == b"b"


def test_import_files_marks_empty_results_without_incrementing_doc_count(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.return_value = []
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: "a.txt"))

    result = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    assert result["indexed_chunks"] == 0
    assert result["success_count"] == 0
    assert result["failed_count"] == 0
    assert result["empty_count"] == 1
    assert result["file_results"][0]["status"] == "empty"
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert (tmp_path / "data" / "kb-a" / "a.txt").read_bytes() == b"alpha"


def test_import_files_partial_failure_only_counts_indexed_items(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.side_effect = [[SimpleNamespace(metadata={})], RuntimeError("index failed")]
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("ok.txt", b"alpha"), FakeUploadFile("bad.txt", b"bravo")],
        128,
        16,
        kb_id="kb-a",
    )

    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert result["indexed_chunks"] == 1
    assert [item["status"] for item in result["file_results"]] == ["indexed", "failed"]
    assert "index failed" in result["file_results"][1]["message"]
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert (tmp_path / "data" / "kb-a" / "ok.txt").read_bytes() == b"alpha"
    assert not (tmp_path / "data" / "kb-a" / "bad.txt").exists()


def test_import_files_cleans_up_when_indexing_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.side_effect = RuntimeError("index failed")
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: "a.txt"))

    result = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert result["file_results"][0]["status"] == "failed"
    assert "index failed" in result["file_results"][0]["message"]
    assert not (tmp_path / "data" / "kb-a" / "a.txt").exists()
    assert registry.get_kb("kb-a")["doc_count"] == 0


def test_import_urls_validates_kb_before_counting(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    _patch_runtime(monkeypatch)

    with pytest.raises(KBNotFoundError):
        kb_service.import_urls(["https://example.com"], 128, 16, kb_id="missing")

    inactive = registry.create_kb("inactive-kb", "Inactive KB")
    inactive["status"] = "disabled"
    registry.replace_all([inactive])
    with pytest.raises(KBUnavailableError):
        kb_service.import_urls(["https://example.com"], 128, 16, kb_id="inactive-kb")
    assert registry.get_kb("inactive-kb")["doc_count"] == 0

    registry.create_kb("kb-a", "KB A")
    result = kb_service.import_urls(["https://example.com"], 128, 16, kb_id="kb-a")
    assert result["indexed_chunks"] == 1
    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert result["url_results"][0]["status"] == "indexed"
    assert registry.get_kb("kb-a")["doc_count"] == 1


def test_import_urls_marks_empty_without_incrementing_doc_count(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_websites.return_value = []

    result = kb_service.import_urls(["https://example.com"], 128, 16, kb_id="kb-a")

    assert result["indexed_chunks"] == 0
    assert result["success_count"] == 0
    assert result["failed_count"] == 0
    assert result["empty_count"] == 1
    assert result["url_results"][0]["status"] == "empty"
    assert registry.get_kb("kb-a")["doc_count"] == 0


def test_import_urls_partial_failure_only_counts_indexed_items(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_websites.side_effect = [[SimpleNamespace(metadata={})], RuntimeError("fetch failed")]

    result = kb_service.import_urls(["https://ok.example.com", "https://bad.example.com"], 128, 16, kb_id="kb-a")

    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert result["indexed_chunks"] == 1
    assert [item["status"] for item in result["url_results"]] == ["indexed", "failed"]
    assert "fetch failed" in result["url_results"][1]["message"]
    assert registry.get_kb("kb-a")["doc_count"] == 1


def test_delete_non_empty_kb_raises_conflict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    (tmp_path / "data" / "kb-a").mkdir(parents=True)
    (tmp_path / "data" / "kb-a" / "a.txt").write_text("a", encoding="utf-8")
    monkeypatch.setattr(kb_service, "list_docs", MagicMock(return_value=[]))

    with pytest.raises(KBConflictError):
        kb_service.delete_kb("kb-a")

    assert registry.get_kb("kb-a") is not None
    assert (tmp_path / "data" / "kb-a" / "a.txt").exists()


def test_delete_empty_kb_removes_registry_and_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    (tmp_path / "data" / "kb-a").mkdir(parents=True)
    monkeypatch.setattr(kb_service, "list_docs", MagicMock(return_value=[]))

    assert kb_service.delete_kb("kb-a") is True

    assert registry.get_kb("kb-a") is None
    assert not (tmp_path / "data" / "kb-a").exists()


def test_delete_default_kb_is_forbidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("default", "Default")

    with pytest.raises(KBConflictError):
        kb_service.delete_kb("default")



def test_index_manager_load_files_uses_explicit_paths_and_writes_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from server import index as index_module

    source = tmp_path / "data" / "kb-a" / "a.txt"
    source.parent.mkdir(parents=True)
    source.write_text("alpha", encoding="utf-8")

    manager = index_module.IndexManager("test-index")
    monkeypatch.setattr(manager, "_load_documents", MagicMock(return_value=[SimpleNamespace(metadata={})]))
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents):
            return [SimpleNamespace(metadata=dict(documents[0].metadata))]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_files([source], 128, 16, kb_id="kb-a")

    assert nodes[0].metadata["kb_id"] == "kb-a"
    assert nodes[0].metadata["file_path"] == str(source.resolve())
    assert nodes[0].metadata["file_name"] == "a.txt"
    manager._load_documents.assert_called_once_with([str(source.resolve())])
