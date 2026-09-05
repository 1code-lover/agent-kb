"""目录导入保留树结构测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tests.api._testclient import TestClient

from api.app import app
from api.schemas import DeleteDocsRequest
from api.services import kb_service
from server.kb_errors import KBValidationError
from server.kb_registry import KBRegistry

client = TestClient(app)


class FakeUploadFile:
    """简化版上传文件对象，用于目录导入服务测试。"""

    def __init__(self, filename: str = "a.md", content: bytes = b"hello", content_type: str = "text/markdown"):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


class MemoryDocStore:
    """最小化 docstore，供 preserve_tree 重导入回归测试复用。"""

    def __init__(self) -> None:
        self.docs: dict[str, SimpleNamespace] = {}
        self._ref_docs: dict[str, SimpleNamespace] = {}

    def get_all_ref_doc_info(self) -> dict[str, SimpleNamespace]:
        return dict(self._ref_docs)

    def add_ref_doc(self, ref_doc_id: str, metadata: dict[str, object]) -> None:
        node_id = f"{ref_doc_id}-node"
        self._ref_docs[ref_doc_id] = SimpleNamespace(metadata=dict(metadata), node_ids=[node_id])
        self.docs[node_id] = SimpleNamespace(metadata=dict(metadata), node_id=node_id, text="")

    def remove_ref_doc(self, ref_doc_id: str) -> None:
        ref_doc = self._ref_docs.pop(ref_doc_id, None)
        if ref_doc is None:
            return
        for node_id in getattr(ref_doc, "node_ids", []) or []:
            self.docs.pop(node_id, None)


class MemoryIndexManager:
    """内存索引管理器，直接验证 preserve_tree 场景下的 ref_doc 替换。"""

    def __init__(self) -> None:
        self.storage_context = SimpleNamespace(docstore=MemoryDocStore())
        self.deleted_ref_doc_ids: list[str] = []
        self.persist_storage = MagicMock(return_value=True)
        self.consume_last_ingestion_diagnostics = MagicMock(return_value=None)
        self.consume_last_persist_diagnostics = MagicMock(return_value=None)
        self._ref_counter = 0
        self._load_files_plan: list[object] = []

    def queue_load_files_plan(self, *items: object) -> None:
        self._load_files_plan.extend(items)

    def load_files(self, paths, chunk_size: int, chunk_overlap: int, kb_id: str | None = None, persist: bool = False):
        del chunk_size, chunk_overlap, persist
        if self._load_files_plan:
            planned = self._load_files_plan.pop(0)
            if isinstance(planned, Exception):
                raise planned
            if planned == "empty":
                return []

        nodes: list[SimpleNamespace] = []
        for raw_path in paths:
            path = Path(raw_path).resolve()
            self._ref_counter += 1
            ref_doc_id = f"tree-ref-{self._ref_counter}"
            metadata = {
                "kb_id": kb_id,
                "file_path": str(path),
                "file_name": path.name,
            }
            self.storage_context.docstore.add_ref_doc(ref_doc_id, metadata)
            nodes.append(SimpleNamespace(metadata=metadata))
        return nodes

    def delete_ref_doc(self, ref_doc_id: str) -> None:
        self.deleted_ref_doc_ids.append(ref_doc_id)
        self.storage_context.docstore.remove_ref_doc(ref_doc_id)


def _patch_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBRegistry:
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    monkeypatch.setattr(kb_service, "_registry", registry)
    return registry


def _patch_runtime(monkeypatch: pytest.MonkeyPatch, manager: MagicMock | None = None):
    manager = manager or MagicMock()
    member = getattr(manager, "load_files", None)
    if hasattr(member, "return_value"):
        member.return_value = [SimpleNamespace(metadata={})]
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


@pytest.fixture(autouse=True)
def _reset_registry_state():
    yield
    kb_service._registry = None


def test_import_files_preserve_tree_writes_nested_path_and_echoes_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """preserve_tree 模式应按 relative_path 落盘，并回显 folder 语义。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)

    result = kb_service.import_files(
        [FakeUploadFile("a.md", b"alpha")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )

    target = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"
    assert target.is_file()
    assert manager.load_files.call_args.args[0] == [target.resolve()]
    assert result["file_results"][0]["relative_path"] == "design/specs/a.md"
    assert result["file_results"][0]["folder_path"] == "design/specs"


def test_import_files_preserve_tree_rejects_relative_path_count_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """relative_paths 数量必须与 files 一一对应。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)

    with pytest.raises(KBValidationError):
        kb_service.import_files(
            [FakeUploadFile("a.md"), FakeUploadFile("b.md")],
            128,
            16,
            kb_id="kb-a",
            relative_paths=["design/a.md"],
            import_mode="preserve_tree",
        )


def test_import_files_preserve_tree_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """目录导入不得接受越界 relative_path。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)

    with pytest.raises(KBValidationError):
        kb_service.import_files(
            [FakeUploadFile("a.md")],
            128,
            16,
            kb_id="kb-a",
            relative_paths=["../escape.md"],
            import_mode="preserve_tree",
        )


def test_import_files_preserve_tree_reimport_nested_path_replaces_existing_doc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """同一 relative_path 重导入时，应替换旧 ref_doc 且保持 doc_count 稳定。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)

    first = kb_service.import_files(
        [FakeUploadFile("a.md", b"alpha")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )
    first_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())

    second = kb_service.import_files(
        [FakeUploadFile("a.md", b"beta")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )

    target = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"
    assert first["file_results"][0]["status"] == "indexed"
    assert second["file_results"][0]["status"] == "indexed"
    assert target.read_bytes() == b"beta"
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert manager.deleted_ref_doc_ids == list(first_ref_doc_ids)
    assert len(manager.storage_context.docstore.get_all_ref_doc_info()) == 1


def test_import_files_preserve_tree_failed_reimport_restores_previous_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """nested relative_path 的重导入失败时，应恢复旧文件并允许后续 retry。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)

    first = kb_service.import_files(
        [FakeUploadFile("a.md", b"alpha")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )
    target = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"
    stable_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())
    manager.queue_load_files_plan(RuntimeError("index failed"))

    failed = kb_service.import_files(
        [FakeUploadFile("a.md", b"beta")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )
    after_failed_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())
    after_failed_bytes = target.read_bytes()

    retry = kb_service.import_files(
        [FakeUploadFile("a.md", b"gamma")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )
    retry_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())

    assert first["file_results"][0]["status"] == "indexed"
    assert failed["file_results"][0]["status"] == "failed"
    assert "index failed" in failed["file_results"][0]["message"]
    assert after_failed_bytes == b"alpha"
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert after_failed_ref_doc_ids == stable_ref_doc_ids

    assert retry["file_results"][0]["status"] == "indexed"
    assert target.read_bytes() == b"gamma"
    assert len(stable_ref_doc_ids) == 1
    assert len(retry_ref_doc_ids) == 1
    assert retry_ref_doc_ids.isdisjoint(stable_ref_doc_ids)


def test_import_files_preserve_tree_batch_persist_failure_restores_new_and_reimport_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """batch persist 失败时应同时恢复 nested reimport 与 nested 新文件。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)

    first = kb_service.import_files(
        [FakeUploadFile("a.md", b"alpha")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )
    stable_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())
    original_target = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"
    manager.persist_storage.side_effect = RuntimeError("persist failed")

    failed = kb_service.import_files(
        [
            FakeUploadFile("a.md", b"beta"),
            FakeUploadFile("b.md", b"new-file"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md", "design/specs/b.md"],
        import_mode="preserve_tree",
    )

    current_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())
    new_target = tmp_path / "data" / "kb-a" / "design" / "specs" / "b.md"

    assert first["file_results"][0]["status"] == "indexed"
    assert [item["status"] for item in failed["file_results"]] == ["failed", "failed"]
    assert all("persist failed" in str(item.get("message") or "") for item in failed["file_results"])
    assert original_target.read_bytes() == b"alpha"
    assert not new_target.exists()
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert current_ref_doc_ids == stable_ref_doc_ids



def test_import_files_preserve_tree_persist_failure_rewrites_empty_file_to_failed_and_cleans_nested_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """nested 混合批次在 batch persist 失败时应将 empty 结果改写为 failed 并清理路径。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    manager.queue_load_files_plan("empty")
    _patch_runtime(monkeypatch, manager)
    manager.persist_storage.side_effect = RuntimeError("persist failed")

    failed = kb_service.import_files(
        [
            FakeUploadFile("empty.md", b"   "),
            FakeUploadFile("ready.md", b"ready content"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["drafts/empty.md", "design/specs/ready.md"],
        import_mode="preserve_tree",
    )

    empty_target = tmp_path / "data" / "kb-a" / "drafts" / "empty.md"
    ready_target = tmp_path / "data" / "kb-a" / "design" / "specs" / "ready.md"

    assert [item["status"] for item in failed["file_results"]] == ["failed", "failed"]
    assert all("persist failed" in str(item.get("message") or "") for item in failed["file_results"])
    assert failed["empty_count"] == 0
    assert failed["success_count"] == 0
    assert failed["failed_count"] == 2
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert not empty_target.exists()
    assert not ready_target.exists()
    assert manager.storage_context.docstore.get_all_ref_doc_info() == {}


def test_delete_docs_by_nested_path_allows_preserve_tree_reimport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """按 nested path 删除后，应允许 preserve_tree 重新导入同一路径。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))

    first = kb_service.import_files(
        [FakeUploadFile("a.md", b"alpha")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )
    target = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"

    deleted = kb_service.delete_docs(DeleteDocsRequest(kb_id="kb-a", doc_ids=[], paths=[str(target.resolve())]))
    second = kb_service.import_files(
        [FakeUploadFile("a.md", b"beta")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )

    assert first["file_results"][0]["status"] == "indexed"
    assert deleted == {"deleted": 1, "files_deleted": 1, "files_skipped": 0}
    assert second["file_results"][0]["status"] == "indexed"
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert target.read_bytes() == b"beta"


def test_kb_file_import_route_passes_relative_paths_and_import_mode() -> None:
    """路由层应把 relative_paths 与 import_mode 原样转给服务层。"""
    with patch("api.routers.kb.kb_service.import_files") as mock_import_files:
        mock_import_files.return_value = {"success_count": 1, "kb_id": "kb-a"}

        resp = client.post(
            "/api/kb/file/import",
            data={
                "chunk_size": "128",
                "chunk_overlap": "16",
                "kb_id": "kb-a",
                "relative_paths": "design/specs/a.md",
                "import_mode": "preserve_tree",
            },
            files={"files": ("a.md", b"alpha", "text/markdown")},
        )

    assert resp.status_code == 200
    mock_import_files.assert_called_once()
    args = mock_import_files.call_args.args
    kwargs = mock_import_files.call_args.kwargs
    assert len(args[0]) == 1
    assert args[1:] == (128, 16)
    assert kwargs == {
        "kb_id": "kb-a",
        "relative_paths": ["design/specs/a.md"],
        "import_mode": "preserve_tree",
    }
