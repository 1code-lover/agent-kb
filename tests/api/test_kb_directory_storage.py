"""多知识库目录化存储服务测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from api.schemas import DeleteDocsRequest, PreviewRequest
from api.services import asset_service, kb_import_receipt_store, kb_service
from server.kb_errors import (
    KBConflictError,
    KBConsistencyError,
    KBNotFoundError,
    KBUnavailableError,
)
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry


class FakeUploadFile:
    """替换运行时状态，隔离测试文件系统。"""

    def __init__(self, filename: str = "a.txt", content: bytes = b"hello", content_type: str = "text/plain"):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)



def _create_png_bytes() -> bytes:
    """生成最小 PNG 字节流，供无扩展名图片导入测试复用。"""
    buffer = io.BytesIO()
    image = Image.new("RGB", (2, 2), color=(255, 255, 255))
    image.save(buffer, format="PNG")
    return buffer.getvalue()



class MemoryDocStore:
    """最小内存 docstore，覆盖 ref_doc 备份与回滚场景。"""

    def __init__(self) -> None:
        self.docs: dict[str, SimpleNamespace] = {}
        self._ref_docs: dict[str, SimpleNamespace] = {}

    def get_all_ref_doc_info(self) -> dict[str, SimpleNamespace]:
        return dict(self._ref_docs)

    def get_ref_doc_info(self, ref_doc_id: str) -> SimpleNamespace | None:
        return self._ref_docs.get(ref_doc_id)

    def get_document(self, node_id: str, raise_error: bool = True):
        node = self.docs.get(node_id)
        if node is None and raise_error:
            raise ValueError(f"node_id {node_id} not found")
        return node

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
    """最小内存索引管理器，覆盖导入替换与回滚测试。"""

    def __init__(self) -> None:
        self.storage_context = SimpleNamespace(docstore=MemoryDocStore())
        self.deleted_ref_doc_ids: list[str] = []
        self.persist_storage = MagicMock(return_value=True)
        self.consume_last_ingestion_diagnostics = MagicMock(return_value=None)
        self.consume_last_persist_diagnostics = MagicMock(return_value=None)
        self.load_documents = MagicMock(return_value=[SimpleNamespace(metadata={})])
        self.load_websites = MagicMock(return_value=[SimpleNamespace(metadata={})])
        self._load_files_plan: list[object] = []
        self._ref_counter = 0

    def queue_load_files_plan(self, *items: object) -> None:
        self._load_files_plan.extend(items)

    def load_files(
        self,
        paths: list[Path],
        chunk_size: int,
        chunk_overlap: int,
        *,
        kb_id: str | None = None,
        persist: bool = False,
    ) -> list[SimpleNamespace]:
        del chunk_size, chunk_overlap, persist
        if self._load_files_plan:
            planned = self._load_files_plan.pop(0)
            if isinstance(planned, Exception):
                raise planned
            if planned == "empty":
                return []

        created: list[SimpleNamespace] = []
        for raw_path in paths:
            resolved = Path(raw_path).resolve()
            self._ref_counter += 1
            ref_doc_id = f"ref-{self._ref_counter}"
            metadata = {
                "kb_id": kb_id,
                "file_path": str(resolved),
                "file_name": resolved.name,
            }
            self.storage_context.docstore.add_ref_doc(ref_doc_id, metadata)
            created.append(SimpleNamespace(metadata=metadata))
        return created

    def delete_ref_doc(self, ref_doc_id: str, *, persist: bool = True) -> None:
        del persist
        self.deleted_ref_doc_ids.append(ref_doc_id)
        self.storage_context.docstore.remove_ref_doc(ref_doc_id)
def _patch_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBRegistry:
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    monkeypatch.setattr(kb_service, "_registry", registry)
    return registry


def _patch_asset_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBAssetRegistry:
    registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    monkeypatch.setattr(asset_service, "_registry", registry)
    return registry


def _patch_runtime(monkeypatch: pytest.MonkeyPatch, manager: MagicMock | None = None):
    manager = manager or MagicMock()
    for attr, value in (
        ("load_files", [SimpleNamespace(metadata={})]),
        ("load_documents", [SimpleNamespace(metadata={})]),
        ("load_websites", [SimpleNamespace(metadata={})]),
        ("consume_last_ingestion_diagnostics", None),
        ("persist_storage", True),
    ):
        member = getattr(manager, attr, None)
        if hasattr(member, "return_value"):
            member.return_value = value
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


def _build_ingestion_diagnostics(
    *,
    document_count: int = 1,
    empty_document_count: int = 0,
    input_text_chars: int = 5,
    node_count: int = 1,
    nodes_with_embedding_count: int | None = None,
    nodes_without_embedding_count: int | None = None,
    stage_timings: dict[str, float] | None = None,
) -> dict:
    """汇总 ingestion diagnostics 的最小测试数据结构。"""
    with_embeddings = node_count if nodes_with_embedding_count is None else nodes_with_embedding_count
    without_embeddings = max(node_count - with_embeddings, 0) if nodes_without_embedding_count is None else nodes_without_embedding_count
    return {
        "document_count": document_count,
        "empty_document_count": empty_document_count,
        "input_text_chars": input_text_chars,
        "node_count": node_count,
        "nodes_with_embedding_count": with_embeddings,
        "nodes_without_embedding_count": without_embeddings,
        "stage_timings": {
            "document_load_ms": 1.0,
            "chunking_ms": 2.0,
            "embedding_ms": 3.0,
            "title_extract_ms": 4.0,
            "vector_store_ms": 5.0,
            "docstore_ms": 6.0,
            "index_insert_ms": 7.0,
            "total_ms": 28.0,
            **(stage_timings or {}),
        },
    }


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


def test_import_files_rejects_binary_upload_before_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """二进制上传应在落盘与入索引前被拒绝，避免把未知内容误判为成功导入。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("payload.bin", b"\x00\x01\x02\x03", content_type="application/octet-stream")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert result["indexed_chunks"] == 0
    assert file_result["status"] == "failed"
    assert file_result["path"] is None
    assert "暂不支持该文件类型导入" in file_result["message"]
    assert file_result["diagnostics"]["file_kind"] == "binary"
    assert file_result["diagnostics"]["failure_category"] == "unsupported_file_type"
    assert file_result["diagnostics"]["file_retained_on_disk"] is False
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert not any((tmp_path / "data" / "kb-a").rglob("payload.bin"))
    kb_service.runtime_state.ensure_models_ready.assert_not_called()
    kb_service.runtime_state.get_index_manager.assert_not_called()
    manager.load_files.assert_not_called()



def test_import_files_rejects_binary_suffix_without_content_type_before_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """带二进制后缀但缺失 MIME 的上传仍应被拒绝，不能漏过类型收紧。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("payload.bin", b"\x00\x01\x02\x03", content_type="")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert file_result["status"] == "failed"
    assert file_result["path"] is None
    assert file_result["diagnostics"]["file_kind"] == "binary"
    assert file_result["diagnostics"]["failure_category"] == "unsupported_file_type"
    assert file_result["diagnostics"]["file_retained_on_disk"] is False
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert not any((tmp_path / "data" / "kb-a").rglob("payload.bin"))
    kb_service.runtime_state.ensure_models_ready.assert_not_called()
    kb_service.runtime_state.get_index_manager.assert_not_called()
    manager.load_files.assert_not_called()



def test_import_files_rejects_extensionless_binary_without_content_type_before_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """无后缀且缺失 MIME 的二进制字节仍应在落盘前被拒绝。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("README", b"\x00\x01\x02\x03", content_type="")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert file_result["status"] == "failed"
    assert file_result["path"] is None
    assert file_result["diagnostics"]["file_kind"] == "binary"
    assert file_result["diagnostics"]["failure_category"] == "unsupported_file_type"
    assert file_result["diagnostics"]["file_retained_on_disk"] is False
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert not any((tmp_path / "data" / "kb-a").rglob("README"))
    kb_service.runtime_state.ensure_models_ready.assert_not_called()
    kb_service.runtime_state.get_index_manager.assert_not_called()
    manager.load_files.assert_not_called()


def test_import_files_allows_extensionless_utf8_text_without_content_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """无后缀且缺失 MIME 的 UTF-8 文本仍应保留导入能力。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("README", "这是说明文档".encode("utf-8"), content_type="")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert file_result["status"] == "indexed"
    assert file_result["diagnostics"]["file_kind"] == "text"
    assert file_result["diagnostics"]["file_retained_on_disk"] is True
    assert file_result["path"] is not None
    assert registry.get_kb("kb-a")["doc_count"] == 1
    kb_service.runtime_state.ensure_models_ready.assert_called_once_with(require_llm=False)
    kb_service.runtime_state.get_index_manager.assert_called_once_with("kb-a")
    manager.load_files.assert_called_once()


def test_import_files_rejects_extensionless_binary_with_octet_stream_before_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无后缀二进制文件在 octet-stream 下也应在运行时前被拒绝。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("README", b"\x00\x01\x02\x03", content_type="application/octet-stream")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert file_result["status"] == "failed"
    assert file_result["path"] is None
    assert file_result["diagnostics"]["file_kind"] == "binary"
    assert file_result["diagnostics"]["failure_category"] == "unsupported_file_type"
    assert file_result["diagnostics"]["file_retained_on_disk"] is False
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert not any((tmp_path / "data" / "kb-a").rglob("README"))
    kb_service.runtime_state.ensure_models_ready.assert_not_called()
    kb_service.runtime_state.get_index_manager.assert_not_called()
    manager.load_files.assert_not_called()



def test_import_files_allows_extensionless_utf8_text_with_octet_stream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无后缀 UTF-8 文本在 octet-stream 下也应被识别并导入。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("README", "This is a README file.".encode("utf-8"), content_type="application/octet-stream")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert file_result["status"] == "indexed"
    assert file_result["diagnostics"]["file_kind"] == "text"
    assert file_result["diagnostics"]["file_retained_on_disk"] is True
    assert file_result["path"] is not None
    assert registry.get_kb("kb-a")["doc_count"] == 1
    kb_service.runtime_state.ensure_models_ready.assert_called_once_with(require_llm=False)
    kb_service.runtime_state.get_index_manager.assert_called_once_with("kb-a")
    manager.load_files.assert_called_once()



def test_import_files_allows_extensionless_utf16_text_with_octet_stream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """??? UTF-16 ??? octet-stream ???????????????"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    raw_text = (
        "Extensionless UTF-16 diagnostic note.\n"
        "The authorization boundary remains the knowledge base.\n"
    )
    raw_bytes = raw_text.encode("utf-16")

    result = kb_service.import_files(
        [FakeUploadFile("README", raw_bytes, content_type="application/octet-stream")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    saved_path = Path(file_result["path"])
    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert file_result["status"] == "indexed"
    assert file_result["diagnostics"]["file_kind"] == "text"
    assert file_result["diagnostics"]["file_retained_on_disk"] is True
    assert saved_path.read_bytes() == raw_bytes
    assert saved_path.read_text(encoding="utf-16") == raw_text
    assert registry.get_kb("kb-a")["doc_count"] == 1
    kb_service.runtime_state.ensure_models_ready.assert_called_once_with(require_llm=False)
    kb_service.runtime_state.get_index_manager.assert_called_once_with("kb-a")
    manager.load_files.assert_called_once()


def test_import_files_detects_extensionless_pdf_with_octet_stream_as_pdf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无后缀 PDF 在 octet-stream 下也应被识别为 PDF。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.side_effect = ModuleNotFoundError("No module named 'fitz'")
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("manual", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", content_type="application/octet-stream")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert file_result["status"] == "failed"
    assert diagnostics["file_kind"] == "pdf"
    assert diagnostics["failure_category"] == "dependency_missing"
    assert diagnostics["missing_dependency"] == "fitz"
    assert diagnostics["dependency_status"] == "missing"
    assert not (tmp_path / "data" / "kb-a" / "manual").exists()
    manager.load_files.assert_called_once()
    manager.load_documents.assert_not_called()



def test_import_files_runs_ocr_for_extensionless_png_with_octet_stream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无后缀 PNG 在 octet-stream 下也应进入 OCR 链路。"""
    from server.readers import image_ocr

    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_documents.return_value = [SimpleNamespace(metadata={})]

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [SimpleNamespace(json={"res": {"rec_texts": ["octet stream extensionless diagram"]}})]

    def _fake_get_ocr(timing_metrics: dict[str, object] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 5.0
            timing_metrics["ocr_instance_reused"] = False
        return FakeOCR()

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("diagram", _create_png_bytes(), content_type="application/octet-stream")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert file_result["status"] == "indexed"
    assert diagnostics["file_kind"] == "image"
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "success"
    assert diagnostics["empty_reason"] is None
    assert diagnostics["ocr_text_length"] == len("octet stream extensionless diagram")
    assert diagnostics["indexed_from_ocr"] is True
    assert diagnostics["asset_registered"] is True
    manager.load_files.assert_not_called()
    manager.load_documents.assert_called_once()



def test_import_files_detects_extensionless_pdf_without_content_type_as_pdf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无后缀且缺失 MIME 的 PDF 文件应被识别为 PDF 并走对应失败文案。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.side_effect = ModuleNotFoundError("No module named 'fitz'")
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("manual", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", content_type="")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert file_result["status"] == "failed"
    assert file_result["message"] == "缺少 PyMuPDF（fitz）依赖，暂时无法解析 PDF 文件"
    assert diagnostics["file_kind"] == "pdf"
    assert diagnostics["failure_category"] == "dependency_missing"
    assert diagnostics["missing_dependency"] == "fitz"
    assert diagnostics["dependency_status"] == "missing"
    assert not (tmp_path / "data" / "kb-a" / "manual").exists()
    manager.load_files.assert_called_once()
    manager.load_documents.assert_not_called()


def test_import_files_runs_ocr_for_extensionless_png_without_content_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无扩展名且无 MIME 的 PNG 导入时应实际进入 OCR 而非被跳过。"""
    from server.readers import image_ocr

    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_documents.return_value = [SimpleNamespace(metadata={})]

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [SimpleNamespace(json={"res": {"rec_texts": ["standalone extensionless diagram"]}})]

    def _fake_get_ocr(timing_metrics: dict[str, object] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 6.0
            timing_metrics["ocr_instance_reused"] = False
        return FakeOCR()

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("diagram", _create_png_bytes(), content_type="")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert file_result["status"] == "indexed"
    assert diagnostics["file_kind"] == "image"
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "success"
    assert diagnostics["empty_reason"] is None
    assert diagnostics["ocr_text_length"] == len("standalone extensionless diagram")
    assert diagnostics["indexed_from_ocr"] is True
    assert diagnostics["asset_registered"] is True
    manager.load_files.assert_not_called()
    manager.load_documents.assert_called_once()


def test_import_files_detects_extensionless_png_without_content_type_as_image(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无后缀且缺失 MIME 的 PNG 文件应走图片 OCR 导入分支。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_documents.return_value = [SimpleNamespace(metadata={})]
    monkeypatch.setattr(
        kb_service,
        "_extract_image_ocr_result",
        MagicMock(
            return_value={
                "attempted": True,
                "status": "success",
                "text": "流程图文字",
                "error": None,
                "engine": "mock-paddleocr",
            }
        ),
    )
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("diagram", b"\x89PNG\r\n\x1a\nrest", content_type="")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert file_result["status"] == "indexed"
    assert diagnostics["file_kind"] == "image"
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "success"
    assert diagnostics["ocr_text_length"] == len("流程图文字")
    assert diagnostics["indexed_from_ocr"] is True
    assert diagnostics["asset_registered"] is True
    manager.load_files.assert_not_called()
    manager.load_documents.assert_called_once()

def test_import_files_mixed_binary_rejection_and_text_import_counts_correctly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """混合批次中二进制拒绝不应阻断后续可支持文本导入。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [
            FakeUploadFile("payload.bin", b"\x00\x01\x02\x03", content_type="application/octet-stream"),
            FakeUploadFile("note.txt", b"hello", content_type="text/plain"),
        ],
        128,
        16,
        kb_id="kb-a",
    )

    binary_result, text_result = result["file_results"]
    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert result["indexed_chunks"] == 1
    assert binary_result["status"] == "failed"
    assert binary_result["diagnostics"]["failure_category"] == "unsupported_file_type"
    assert text_result["status"] == "indexed"
    assert text_result["path"] == str((tmp_path / "data" / "kb-a" / "note.txt").resolve())
    assert result["diagnostics"]["failed_files"] == 1
    assert result["diagnostics"]["indexed_files"] == 1
    assert result["diagnostics"]["failure_category_counts"]["unsupported_file_type"] == 1
    assert registry.get_kb("kb-a")["doc_count"] == 1
    manager.load_files.assert_called_once()
    assert manager.load_files.call_args.args[0] == [(tmp_path / "data" / "kb-a" / "note.txt").resolve()]
    assert not any((tmp_path / "data" / "kb-a").rglob("payload.bin"))



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
    assert result["file_results"][0]["diagnostics"]["file_retained_on_disk"] is True
    file_paths = manager.load_files.call_args.args[0]
    assert file_paths == [expected.resolve()]
    assert registry.get_kb("kb-a")["doc_count"] == 1


def test_import_files_preserves_utf8_markdown_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Markdown 中文 UTF-8 导入后应保持原始字节与文本内容。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")

    observed: dict[str, object] = {}
    manager = MagicMock()

    def _fake_load_files(paths, chunk_size: int, chunk_overlap: int, kb_id: str | None = None, persist: bool = False):
        path = Path(paths[0])
        observed["path"] = path
        observed["text"] = path.read_text(encoding="utf-8")
        observed["bytes"] = path.read_bytes()
        return [SimpleNamespace(metadata={"kb_id": kb_id or "kb-a", "file_name": path.name})]

    manager.load_files.side_effect = _fake_load_files
    manager.load_documents.return_value = [SimpleNamespace(metadata={})]
    manager.load_websites.return_value = [SimpleNamespace(metadata={})]
    raw_text = (
        "# 标题\n\n"
        "这是一段中文内容，用于验证 UTF-8 导入不会被写成问号。\n"
    )
    manager.consume_last_ingestion_diagnostics.return_value = _build_ingestion_diagnostics(
        input_text_chars=len(raw_text)
    )
    manager.persist_storage.return_value = True
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    raw_bytes = raw_text.encode("utf-8")

    result = kb_service.import_files(
        [FakeUploadFile("utf8-check.md", raw_bytes, content_type="text/markdown")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/utf8-check.md"],
        import_mode="preserve_tree",
    )

    expected = tmp_path / "data" / "kb-a" / "docs" / "utf8-check.md"
    assert expected.read_bytes() == raw_bytes
    assert expected.read_text(encoding="utf-8") == raw_text
    assert observed["path"] == expected.resolve()
    assert observed["bytes"] == raw_bytes
    assert observed["text"] == raw_text
    assert result["file_results"][0]["status"] == "indexed"
    assert result["file_results"][0]["relative_path"] == "docs/utf8-check.md"
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


def test_import_files_defers_index_persist_until_batch_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)

    result = kb_service.import_files(
        [
            FakeUploadFile("a.txt", b"alpha"),
            FakeUploadFile("b.txt", b"beta"),
        ],
        128,
        16,
        kb_id="kb-a",
    )

    assert result["success_count"] == 2
    assert manager.load_files.call_count == 2
    for call in manager.load_files.call_args_list:
        assert call.kwargs["persist"] is False
    manager.persist_storage.assert_called_once_with()


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


def test_import_files_returns_failed_result_when_index_storage_persist_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """首次导入在批量 persist 失败时，应清理磁盘与索引并返回失败结果。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))
    manager.persist_storage.side_effect = RuntimeError("persist failed")

    result = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    file_result = result["file_results"][0]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert result["empty_count"] == 0
    assert result["indexed_chunks"] == 0
    assert file_result["status"] == "failed"
    assert "persist failed" in file_result["message"]
    assert file_result["path"] is None
    assert file_result["diagnostics"]["file_retained_on_disk"] is False
    assert file_result["diagnostics"]["failure_category"] == "storage_persist_error"
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert not (tmp_path / "data" / "kb-a" / "a.txt").exists()
    assert manager.storage_context.docstore.get_all_ref_doc_info() == {}



def test_import_files_reimport_restores_old_state_when_index_storage_persist_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """重导入在批量 persist 失败时，应恢复旧文件、旧 ref_doc 与 doc_count。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    first = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")
    stable_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())
    manager.persist_storage.reset_mock()
    manager.persist_storage.side_effect = RuntimeError("persist failed")

    failed = kb_service.import_files([FakeUploadFile("a.txt", b"beta")], 128, 16, kb_id="kb-a")

    file_result = failed["file_results"][0]
    assert first["file_results"][0]["status"] == "indexed"
    assert file_result["status"] == "failed"
    assert "persist failed" in file_result["message"]
    assert file_result["diagnostics"]["failure_category"] == "storage_persist_error"
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert (tmp_path / "data" / "kb-a" / "a.txt").read_bytes() == b"alpha"
    assert set(manager.storage_context.docstore.get_all_ref_doc_info()) == stable_ref_doc_ids
    assert len(manager.storage_context.docstore.get_all_ref_doc_info()) == 1



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
    assert result["file_results"][0]["path"] is None
    assert result["file_results"][0]["diagnostics"]["file_retained_on_disk"] is False
    assert "index failed" in result["file_results"][0]["message"]
    assert not (tmp_path / "data" / "kb-a" / "a.txt").exists()
    assert registry.get_kb("kb-a")["doc_count"] == 0




def test_import_files_reimport_same_path_replaces_existing_doc_without_doc_count_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    first = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")
    first_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())

    second = kb_service.import_files([FakeUploadFile("a.txt", b"beta")], 128, 16, kb_id="kb-a")
    second_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())

    assert first["file_results"][0]["status"] == "indexed"
    assert second["file_results"][0]["status"] == "indexed"
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert (tmp_path / "data" / "kb-a" / "a.txt").read_bytes() == b"beta"
    assert len(first_ref_doc_ids) == 1
    assert len(second_ref_doc_ids) == 1
    assert first_ref_doc_ids.isdisjoint(second_ref_doc_ids)
    assert manager.deleted_ref_doc_ids == list(first_ref_doc_ids)


def test_delete_docs_allows_reimport_after_removing_same_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    first = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")
    doc_id = next(iter(manager.storage_context.docstore.get_all_ref_doc_info()))

    deleted = kb_service.delete_docs(DeleteDocsRequest(kb_id="kb-a", doc_ids=[doc_id], paths=[]))
    second = kb_service.import_files([FakeUploadFile("a.txt", b"beta")], 128, 16, kb_id="kb-a")

    assert first["file_results"][0]["status"] == "indexed"
    assert deleted == {"deleted": 1, "files_deleted": 1, "files_skipped": 0}
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert second["file_results"][0]["status"] == "indexed"
    assert (tmp_path / "data" / "kb-a" / "a.txt").read_bytes() == b"beta"
    assert len(manager.storage_context.docstore.get_all_ref_doc_info()) == 1


def test_import_files_failed_reimport_restores_old_file_and_retry_can_succeed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    first = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")
    stable_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())
    manager.queue_load_files_plan(RuntimeError("index failed"))

    failed = kb_service.import_files([FakeUploadFile("a.txt", b"beta")], 128, 16, kb_id="kb-a")
    after_failed_ref_doc_ids = set(manager.storage_context.docstore.get_all_ref_doc_info())

    retry = kb_service.import_files([FakeUploadFile("a.txt", b"gamma")], 128, 16, kb_id="kb-a")

    assert first["file_results"][0]["status"] == "indexed"
    assert failed["file_results"][0]["status"] == "failed"
    assert "index failed" in failed["file_results"][0]["message"]
    assert after_failed_ref_doc_ids == stable_ref_doc_ids
    assert retry["file_results"][0]["status"] == "indexed"
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert (tmp_path / "data" / "kb-a" / "a.txt").read_bytes() == b"gamma"
    assert len(manager.storage_context.docstore.get_all_ref_doc_info()) == 1


def test_import_files_failed_write_reimport_restores_old_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """写入失败时应回滚本次文件替换，避免磁盘内容被半写覆盖。"""
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

    original_open = Path.open
    failure_state = {"triggered": False}

    class ExplodingWriter:
        def __init__(self, inner) -> None:
            self._inner = inner

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._inner.__exit__(exc_type, exc, tb)

        def write(self, data):
            self._inner.write(data[:1])
            self._inner.flush()
            raise RuntimeError("simulated write failure")

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def flaky_open(self: Path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        handle = original_open(self, *args, **kwargs)
        if (
            not failure_state["triggered"]
            and mode == "wb"
            and self.resolve() == target.resolve()
        ):
            failure_state["triggered"] = True
            return ExplodingWriter(handle)
        return handle

    monkeypatch.setattr(Path, "open", flaky_open)

    failed = kb_service.import_files(
        [FakeUploadFile("a.md", b"beta")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )

    assert first["file_results"][0]["status"] == "indexed"
    assert failure_state["triggered"] is True
    assert failed["file_results"][0]["status"] == "failed"
    assert "simulated write failure" in failed["file_results"][0]["message"]
    assert target.is_file()
    assert target.read_bytes() == b"alpha"
    assert registry.get_kb("kb-a")["doc_count"] == 1
    assert set(manager.storage_context.docstore.get_all_ref_doc_info()) == stable_ref_doc_ids


def test_import_files_marks_pdf_dependency_missing_in_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PDF 缺依赖时应在文件与批次 diagnostics 中保留依赖缺失信号。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.side_effect = ModuleNotFoundError("No module named 'fitz'")
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: "manual.pdf"))

    result = kb_service.import_files(
        [FakeUploadFile("manual.pdf", b"%PDF-1.4", content_type="application/pdf")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert result["failed_count"] == 1
    assert file_result["status"] == "failed"
    assert file_result["message"] == "\u7f3a\u5c11 PyMuPDF\uff08fitz\uff09\u4f9d\u8d56\uff0c\u6682\u65f6\u65e0\u6cd5\u89e3\u6790 PDF \u6587\u4ef6"
    assert diagnostics["file_kind"] == "pdf"
    assert diagnostics["failure_category"] == "dependency_missing"
    assert diagnostics["missing_dependency"] == "fitz"
    assert diagnostics["dependency_status"] == "missing"
    assert diagnostics["empty_reason"] is None
    assert result["diagnostics"]["dependency_missing_count"] == 1
    assert result["diagnostics"]["failure_category_counts"]["dependency_missing"] == 1
    assert result["diagnostics"]["missing_dependency_counts"]["fitz"] == 1
    assert result["diagnostics"]["dependency_status_counts"]["missing"] == 1

    display_summary = result["display_summary"]
    assert display_summary["source_kind"] == "file_import"
    assert display_summary["has_blockers"] is True
    assert display_summary["has_dependency_issues"] is True
    assert display_summary["total_items"] == 1
    assert display_summary["indexed_items"] == 0
    assert display_summary["empty_items"] == 0
    assert display_summary["failed_items"] == 1
    assert display_summary["asset_registered_but_not_indexed_count"] == 0
    assert display_summary["item_label"] == "\u6587\u4ef6"
    assert display_summary["headline"] == "1 \u4e2a\u6587\u4ef6\u56e0\u4f9d\u8d56\u7f3a\u5931\u672a\u5b8c\u6210\u5bfc\u5165"
    assert display_summary["top_missing_dependencies"] == [{"dependency": "fitz", "count": 1}]
    assert any(
        item["action"] == "install_dependency"
        and item.get("dependency") == "fitz"
        and item["label"] == "\u5b89\u88c5\u7f3a\u5931\u4f9d\u8d56\uff1afitz"
        for item in display_summary["next_actions"]
    )

    receipt = kb_service.get_latest_import_receipt("kb-a")
    assert receipt is not None
    assert receipt["result"]["display_summary"]["top_missing_dependencies"] == [{"dependency": "fitz", "count": 1}]
    assert not (tmp_path / "data" / "kb-a" / "manual.pdf").exists()
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


def test_import_files_emits_stage_timings_for_batch_and_file_diagnostics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.consume_last_persist_diagnostics.return_value = {
        "docstore_persist_ms": 0.25,
        "index_store_persist_ms": 0.25,
        "graph_store_persist_ms": 0.25,
        "property_graph_store_persist_ms": 0.0,
        "vector_store_persist_ms": 0.5,
        "vector_store_namespaces_ms": {"default": 0.5},
        "fallback_persist_ms": 0.0,
        "total_ms": 1.25,
    }
    monkeypatch.setattr(kb_service, "_elapsed_ms", lambda _started_at: 1.25)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    batch_timings = result["diagnostics"]["stage_timings"]
    assert set(batch_timings) == {
        "ensure_models_ready_ms",
        "get_index_manager_ms",
        "file_save_ms",
        "persist_ms",
        "standalone_ocr_ms",
        "primary_index_ms",
        "embedded_asset_extract_ms",
        "embedded_asset_ocr_ms",
        "embedded_asset_index_ms",
        "index_storage_persist_ms",
        "doc_count_update_ms",
        "register_assets_ms",
        "receipt_store_ms",
        "result_build_ms",
        "total_ms",
    }
    assert all(value >= 0 for value in batch_timings.values())
    assert batch_timings["file_save_ms"] == 1.25
    assert batch_timings["persist_ms"] == batch_timings["file_save_ms"]
    assert batch_timings["primary_index_ms"] == 1.25
    assert batch_timings["index_storage_persist_ms"] == 1.25
    assert batch_timings["doc_count_update_ms"] == 1.25
    assert batch_timings["register_assets_ms"] == 1.25
    assert batch_timings["receipt_store_ms"] == 1.25
    assert batch_timings["result_build_ms"] == 1.25

    receipt = kb_service.get_latest_import_receipt("kb-a")
    assert receipt is not None
    receipt_batch_timings = receipt["result"]["diagnostics"]["stage_timings"]
    assert receipt_batch_timings["receipt_store_ms"] == batch_timings["receipt_store_ms"]
    assert receipt_batch_timings["total_ms"] == batch_timings["total_ms"]

    storage_persist_timings = result["diagnostics"]["storage_persist_stage_timings"]
    assert storage_persist_timings == {
        "docstore_persist_ms": 0.25,
        "index_store_persist_ms": 0.25,
        "graph_store_persist_ms": 0.25,
        "property_graph_store_persist_ms": 0.0,
        "vector_store_persist_ms": 0.5,
        "vector_store_namespaces_ms": {"default": 0.5},
        "fallback_persist_ms": 0.0,
        "total_ms": 1.25,
    }
    assert receipt["result"]["diagnostics"]["storage_persist_stage_timings"] == storage_persist_timings

    file_timings = result["file_results"][0]["diagnostics"]["stage_timings"]
    assert set(file_timings) == {
        "file_save_ms",
        "persist_ms",
        "standalone_ocr_ms",
        "primary_index_ms",
        "embedded_asset_extract_ms",
        "embedded_asset_ocr_ms",
        "embedded_asset_index_ms",
        "total_ms",
    }
    assert all(value >= 0 for value in file_timings.values())
    assert file_timings["file_save_ms"] == 1.25
    assert file_timings["persist_ms"] == file_timings["file_save_ms"]
    assert file_timings["standalone_ocr_ms"] == 0
    assert file_timings["embedded_asset_ocr_ms"] == 0
    assert file_timings["embedded_asset_index_ms"] == 0


def test_import_files_merges_primary_ingestion_breakdown_into_file_and_batch_diagnostics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.return_value = [SimpleNamespace(metadata={}), SimpleNamespace(metadata={})]
    manager.consume_last_ingestion_diagnostics.return_value = _build_ingestion_diagnostics(
        document_count=1,
        empty_document_count=0,
        input_text_chars=128,
        node_count=2,
        nodes_with_embedding_count=2,
        nodes_without_embedding_count=0,
    )
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    file_diagnostics = result["file_results"][0]["diagnostics"]
    batch_diagnostics = result["diagnostics"]

    assert file_diagnostics["document_count"] == 1
    assert file_diagnostics["empty_document_count"] == 0
    assert file_diagnostics["input_text_chars"] == 128
    assert file_diagnostics["node_count"] == 2
    assert file_diagnostics["nodes_with_embedding_count"] == 2
    assert file_diagnostics["nodes_without_embedding_count"] == 0
    assert file_diagnostics["index_stage_timings"] == {
        "document_load_ms": 1.0,
        "chunking_ms": 2.0,
        "embedding_ms": 3.0,
        "title_extract_ms": 4.0,
        "vector_store_ms": 5.0,
        "docstore_ms": 6.0,
        "index_insert_ms": 7.0,
        "total_ms": 28.0,
    }

    assert batch_diagnostics["document_count"] == 1
    assert batch_diagnostics["empty_document_count"] == 0
    assert batch_diagnostics["input_text_chars"] == 128
    assert batch_diagnostics["node_count"] == 2
    assert batch_diagnostics["nodes_with_embedding_count"] == 2
    assert batch_diagnostics["nodes_without_embedding_count"] == 0
    assert batch_diagnostics["index_stage_timings"]["embedding_ms"] == 3.0
    assert batch_diagnostics["index_stage_timings"]["index_insert_ms"] == 7.0



def test_import_files_maps_pdf_source_diagnostics_into_file_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.return_value = [SimpleNamespace(metadata={})]
    pdf_path = (tmp_path / "data" / "kb-a" / "scan.pdf").resolve()
    manager.consume_last_ingestion_diagnostics.return_value = {
        **_build_ingestion_diagnostics(
            document_count=1,
            empty_document_count=0,
            input_text_chars=88,
            node_count=1,
            nodes_with_embedding_count=1,
            nodes_without_embedding_count=0,
        ),
        "source_file_diagnostics": [
            {
                "file_path": str(pdf_path),
                "file_name": "scan.pdf",
                "source_type": "pdf_ocr_fallback",
                "ocr_attempted": True,
                "ocr_status": "success",
                "ocr_text_length": 88,
                "ocr_error": None,
                "indexed_from_ocr": True,
                "ocr_engine": "mock-paddleocr",
            }
        ],
    }
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("scan.pdf", b"%PDF-1.4", content_type="application/pdf")],
        128,
        16,
        kb_id="kb-a",
    )

    diagnostics = result["file_results"][0]["diagnostics"]
    assert diagnostics["file_kind"] == "pdf"
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "success"
    assert diagnostics["ocr_text_length"] == 88
    assert diagnostics["indexed_from_ocr"] is True
    assert diagnostics["ocr_engine"] == "mock-paddleocr"


def test_import_files_keeps_pdf_ocr_diagnostics_when_indexing_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    pdf_path = (tmp_path / "data" / "kb-a" / "scan.pdf").resolve()
    manager.load_files.side_effect = ValueError(
        "Metadata length (155) is longer than chunk size (128). Consider increasing the chunk size or decreasing the size of your metadata to avoid this."
    )
    manager.consume_last_ingestion_diagnostics.return_value = {
        **_build_ingestion_diagnostics(
            document_count=1,
            empty_document_count=0,
            input_text_chars=88,
            node_count=0,
            nodes_with_embedding_count=0,
            nodes_without_embedding_count=0,
        ),
        "source_file_diagnostics": [
            {
                "file_path": str(pdf_path),
                "file_name": "scan.pdf",
                "source_type": "pdf_ocr_fallback",
                "ocr_attempted": True,
                "ocr_status": "success",
                "ocr_text_length": 88,
                "ocr_error": None,
                "indexed_from_ocr": True,
                "ocr_engine": "mock-paddleocr",
                "ocr_predict_ms": 310000.0,
                "ocr_total_ms": 320000.0,
                "ocr_instance_reused": True,
            }
        ],
    }
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    result = kb_service.import_files(
        [FakeUploadFile("scan.pdf", b"%PDF-1.4", content_type="application/pdf")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]

    assert result["failed_count"] == 1
    assert file_result["status"] == "failed"
    assert "Metadata length" in file_result["message"]
    assert diagnostics["file_kind"] == "pdf"
    assert diagnostics["failure_category"] == "indexing_error"
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "success"
    assert diagnostics["ocr_text_length"] == 88
    assert diagnostics["ocr_engine"] == "mock-paddleocr"
    assert diagnostics["ocr_predict_ms"] == pytest.approx(310000.0)
    assert diagnostics["ocr_total_ms"] == pytest.approx(320000.0)
    assert diagnostics["ocr_instance_reused"] is True

    receipt = kb_service.get_latest_import_receipt("kb-a")
    assert receipt is not None
    latest = receipt["result"]["file_results"][0]["diagnostics"]
    assert latest["failure_category"] == "indexing_error"
    assert latest["ocr_total_ms"] == pytest.approx(320000.0)
    assert latest["ocr_predict_ms"] == pytest.approx(310000.0)


def test_import_files_aggregates_embedded_asset_ingestion_breakdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.return_value = [SimpleNamespace(metadata={})]
    manager.load_documents.return_value = [SimpleNamespace(metadata={}), SimpleNamespace(metadata={})]
    manager.consume_last_ingestion_diagnostics.side_effect = [
        _build_ingestion_diagnostics(
            document_count=1,
            empty_document_count=0,
            input_text_chars=32,
            node_count=1,
            nodes_with_embedding_count=1,
            nodes_without_embedding_count=0,
            stage_timings={"embedding_ms": 11.0, "total_ms": 21.0},
        ),
        _build_ingestion_diagnostics(
            document_count=1,
            empty_document_count=0,
            input_text_chars=18,
            node_count=2,
            nodes_with_embedding_count=2,
            nodes_without_embedding_count=0,
            stage_timings={"embedding_ms": 13.0, "total_ms": 23.0},
        ),
    ]
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))
    monkeypatch.setattr(
        kb_service,
        "extract_markdown_embedded_assets_from_file",
        lambda **_: [
            {
                "asset_id": "asset-1",
                "asset_type": "image",
                "status": "ready",
                "path": str((tmp_path / "data" / "kb-a" / "diagram.png").resolve()),
                "mime_type": "image/png",
                "resolved_relative_path": "diagram.png",
                "source_doc_relative_path": "note.md",
            }
        ],
    )
    monkeypatch.setattr(
        kb_service,
        "_extract_image_ocr_result",
        lambda path, content_type: {
            "attempted": True,
            "status": "success",
            "text": "diagram text",
            "error": None,
            "engine": "mock-ocr",
        },
    )

    result = kb_service.import_files(
        [FakeUploadFile("note.md", b"![diagram](diagram.png)", content_type="text/markdown")],
        128,
        16,
        kb_id="kb-a",
    )

    file_diagnostics = result["file_results"][0]["diagnostics"]
    batch_diagnostics = result["diagnostics"]

    assert file_diagnostics["document_count"] == 2
    assert file_diagnostics["input_text_chars"] == 50
    assert file_diagnostics["node_count"] == 3
    assert file_diagnostics["nodes_with_embedding_count"] == 3
    assert file_diagnostics["nodes_without_embedding_count"] == 0
    assert file_diagnostics["index_stage_timings"]["embedding_ms"] == 24.0
    assert file_diagnostics["index_stage_timings"]["total_ms"] == 44.0

    assert batch_diagnostics["document_count"] == 2
    assert batch_diagnostics["input_text_chars"] == 50
    assert batch_diagnostics["node_count"] == 3
    assert batch_diagnostics["index_stage_timings"]["embedding_ms"] == 24.0
    assert batch_diagnostics["index_stage_timings"]["total_ms"] == 44.0


def test_import_files_records_embedded_asset_stage_timings_for_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_files.return_value = [SimpleNamespace(metadata={})]
    manager.load_documents.return_value = [SimpleNamespace(metadata={})]
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))
    monkeypatch.setattr(
        kb_service,
        "extract_markdown_embedded_assets_from_file",
        lambda **_: [
            {
                "asset_id": "asset-1",
                "asset_type": "image",
                "status": "ready",
                "path": str((tmp_path / "data" / "kb-a" / "diagram.png").resolve()),
                "mime_type": "image/png",
                "resolved_relative_path": "diagram.png",
                "source_doc_relative_path": "note.md",
            }
        ],
    )
    monkeypatch.setattr(
        kb_service,
        "_extract_image_ocr_result",
        lambda path, content_type: {
            "attempted": True,
            "status": "success",
            "text": "diagram text",
            "error": None,
            "engine": "mock-ocr",
        },
    )

    result = kb_service.import_files(
        [FakeUploadFile("note.md", b"![diagram](diagram.png)", content_type="text/markdown")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    file_timings = file_result["diagnostics"]["stage_timings"]
    batch_timings = result["diagnostics"]["stage_timings"]

    assert file_result["status"] == "indexed"
    assert file_result["indexed_chunks"] == 2
    assert file_timings["embedded_asset_extract_ms"] >= 0
    assert file_timings["embedded_asset_ocr_ms"] >= 0
    assert file_timings["embedded_asset_index_ms"] >= 0
    assert batch_timings["embedded_asset_extract_ms"] >= file_timings["embedded_asset_extract_ms"]
    assert batch_timings["embedded_asset_ocr_ms"] >= file_timings["embedded_asset_ocr_ms"]
    assert batch_timings["embedded_asset_index_ms"] >= file_timings["embedded_asset_index_ms"]


def test_import_files_persist_failure_rolls_back_embedded_asset_ref_docs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    embedded_path = tmp_path / "data" / "kb-a" / "diagram.png"
    embedded_path.parent.mkdir(parents=True, exist_ok=True)
    embedded_path.write_bytes(b"fake-png")

    def _load_documents(documents, chunk_size, chunk_overlap, *, kb_id=None, persist=False):
        del chunk_size, chunk_overlap, persist
        created = []
        for document in documents:
            manager._ref_counter += 1
            ref_doc_id = f"ref-{manager._ref_counter}"
            metadata = dict(getattr(document, "metadata", {}) or {})
            if kb_id is not None:
                metadata["kb_id"] = kb_id
            manager.storage_context.docstore.add_ref_doc(ref_doc_id, metadata)
            created.append(SimpleNamespace(metadata=metadata, text=getattr(document, "text", "")))
        return created

    manager.load_documents.side_effect = _load_documents
    manager.persist_storage.side_effect = RuntimeError("persist failed")

    monkeypatch.setattr(
        kb_service,
        "extract_markdown_embedded_assets_from_file",
        lambda **_: [
            {
                "asset_id": "asset-1",
                "asset_type": "image",
                "status": "ready",
                "path": str(embedded_path.resolve()),
                "mime_type": "image/png",
                "resolved_relative_path": "diagram.png",
                "source_doc_relative_path": "note.md",
            }
        ],
    )
    monkeypatch.setattr(
        kb_service,
        "_extract_image_ocr_result",
        lambda path, content_type: {
            "attempted": True,
            "status": "success",
            "text": "diagram text",
            "error": None,
            "engine": "mock-ocr",
        },
    )

    result = kb_service.import_files(
        [FakeUploadFile("note.md", b"![diagram](diagram.png)", content_type="text/markdown")],
        128,
        16,
        kb_id="kb-a",
    )

    file_result = result["file_results"][0]
    assert result["success_count"] == 0
    assert result["failed_count"] == 1
    assert result["indexed_chunks"] == 0
    assert file_result["status"] == "failed"
    assert "persist failed" in file_result["message"]
    assert file_result["diagnostics"]["failure_category"] == "storage_persist_error"
    assert file_result["diagnostics"]["asset_registered"] is False
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert manager.storage_context.docstore.get_all_ref_doc_info() == {}
    assert not (tmp_path / "data" / "kb-a" / "note.md").exists()
    assert embedded_path.exists()
    assert asset_service.list_assets("kb-a") == []


def test_import_files_persist_failure_rolls_back_mixed_batch_with_empty_image_asset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = MemoryIndexManager()
    _patch_runtime(monkeypatch, manager)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))
    monkeypatch.setattr(
        kb_service,
        "_extract_image_ocr_result",
        lambda path, content_type: {
            "attempted": True,
            "status": "no_text",
            "text": "",
            "error": None,
            "engine": "mock-ocr",
        },
    )
    manager.persist_storage.side_effect = RuntimeError("persist failed")

    result = kb_service.import_files(
        [
            FakeUploadFile("guide.txt", b"alpha", content_type="text/plain"),
            FakeUploadFile("diagram.png", b"fake-png", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/guide.txt", "images/diagram.png"],
        import_mode="preserve_tree",
    )

    guide_result, image_result = result["file_results"]
    assert result["success_count"] == 0
    assert result["failed_count"] == 2
    assert result["empty_count"] == 0
    assert result["indexed_chunks"] == 0
    assert guide_result["status"] == "failed"
    assert image_result["status"] == "failed"
    assert "persist failed" in guide_result["message"]
    assert "persist failed" in image_result["message"]
    assert guide_result["diagnostics"]["failure_category"] == "storage_persist_error"
    assert image_result["diagnostics"]["failure_category"] == "storage_persist_error"
    assert image_result["diagnostics"]["asset_registered"] is False
    assert registry.get_kb("kb-a")["doc_count"] == 0
    assert manager.storage_context.docstore.get_all_ref_doc_info() == {}
    assert not (tmp_path / "data" / "kb-a" / "docs" / "guide.txt").exists()
    assert not (tmp_path / "data" / "kb-a" / "images" / "diagram.png").exists()
    assert asset_service.list_assets("kb-a") == []


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


def test_import_files_persists_latest_receipt_per_kb(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    registry.create_kb("kb-b", "KB B")
    _patch_runtime(monkeypatch)

    result_a = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")
    result_b = kb_service.import_files([FakeUploadFile("b.txt", b"beta")], 128, 16, kb_id="kb-b")

    receipt_a = kb_service.get_latest_import_receipt("kb-a")
    receipt_b = kb_service.get_latest_import_receipt("kb-b")

    assert receipt_a is not None
    assert receipt_b is not None
    assert receipt_a["kb_id"] == "kb-a"
    assert receipt_b["kb_id"] == "kb-b"
    assert receipt_a["source_label"] == "文件上传"
    assert receipt_b["source_label"] == "文件上传"
    assert receipt_a["result"]["receipt_id"] == result_a["receipt_id"]
    assert receipt_b["result"]["receipt_id"] == result_b["receipt_id"]
    assert receipt_a["result"]["file_results"][0]["name"] == result_a["file_results"][0]["name"]
    assert receipt_b["result"]["file_results"][0]["name"] == result_b["file_results"][0]["name"]


def test_import_urls_persists_latest_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    manager.load_websites.return_value = [SimpleNamespace(metadata={})]

    result = kb_service.import_urls(["https://example.com/a"], 128, 16, kb_id="kb-a")
    receipt = kb_service.get_latest_import_receipt("kb-a")

    assert receipt is not None
    assert receipt["kb_id"] == "kb-a"
    assert receipt["source_label"] == "网页导入"
    assert receipt["result"]["receipt_id"] == result["receipt_id"]
    assert receipt["result"]["url_results"][0]["url"] == "https://example.com/a"
    assert receipt["result"]["display_summary"]["source_kind"] == "url_import"
    assert receipt["result"]["display_summary"]["indexed_items"] == 1
    assert receipt["result"]["display_summary"]["has_blockers"] is False



def test_get_latest_import_receipt_backfills_display_summary_for_legacy_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")

    legacy_result = {
        "receipt_id": "legacy-1",
        "kb_id": "kb-a",
        "files": [],
        "file_results": [
            {
                "name": "flow.png",
                "type": "image/png",
                "size": 3,
                "path": None,
                "kb_id": "kb-a",
                "status": "empty",
                "indexed_chunks": 0,
                "relative_path": "docs/flow.png",
                "folder_path": "docs",
                "embedded_assets": [],
                "asset_warning_count": 0,
                "diagnostics": {
                    "file_kind": "image",
                    "empty_reason": "no_extractable_text",
                    "asset_registered": True,
                    "failure_category": None,
                    "missing_dependency": None,
                    "dependency_status": "unknown",
                },
            }
        ],
        "indexed_chunks": 0,
        "success_count": 0,
        "failed_count": 0,
        "empty_count": 1,
        "diagnostics": {
            "total_files": 1,
            "indexed_files": 0,
            "empty_files": 1,
            "failed_files": 0,
            "asset_registered_count": 1,
            "asset_warning_count": 0,
            "empty_reason_counts": {"no_extractable_text": 1},
            "failure_category_counts": {},
            "dependency_status_counts": {"unknown": 1},
            "dependency_missing_count": 0,
            "missing_dependency_counts": {},
        },
    }
    kb_import_receipt_store.save_latest_import_receipt("kb-a", source_label="兼容来源", result=legacy_result)

    receipt = kb_service.get_latest_import_receipt("kb-a")

    assert receipt is not None
    summary = receipt["result"]["display_summary"]
    assert summary["source_kind"] == "file_import"
    assert summary["asset_registered_but_not_indexed_count"] == 1
    assert summary["has_blockers"] is False
    assert summary["has_warnings"] is True
    assert any(item["action"] == "review_empty_assets" for item in summary["next_actions"])


def test_delete_kb_cleans_latest_import_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)

    result = kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    receipt_path = tmp_path / "storage" / "kb_import_receipts" / "kb-a.json"
    assert receipt_path.exists()

    file_path = Path(result["files"][0]["path"])
    file_path.unlink()

    registry_items = registry.list_kbs()
    registry_items[0]["doc_count"] = 0
    registry.replace_all(registry_items)
    monkeypatch.setattr(kb_service, "list_docs", MagicMock(return_value=[]))

    assert kb_service.delete_kb("kb-a") is True
    assert not receipt_path.exists()


def test_import_files_requests_manager_for_target_kb(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")

    manager = MagicMock()
    manager.load_files.return_value = [SimpleNamespace(metadata={})]
    manager.consume_last_ingestion_diagnostics.return_value = None
    manager.consume_last_persist_diagnostics.return_value = None
    manager.persist_storage.return_value = True

    get_manager = MagicMock(return_value=manager)
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", get_manager)
    monkeypatch.setattr(kb_service.FilenameSanitizer, "generate_unique_filename", staticmethod(lambda name: name))

    kb_service.import_files([FakeUploadFile("a.txt", b"alpha")], 128, 16, kb_id="kb-a")

    get_manager.assert_called_once_with("kb-a")


def test_list_docs_without_kb_id_aggregates_registered_kb_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("default", "Default")
    registry.create_kb("kb-a", "KB A")
    registry.create_kb("kb-b", "KB B")

    def build_manager(doc_info: dict[str, SimpleNamespace]) -> SimpleNamespace:
        docstore = SimpleNamespace(docs=doc_info, get_all_ref_doc_info=lambda: doc_info)
        return SimpleNamespace(storage_context=SimpleNamespace(docstore=docstore))

    managers = {
        "default": build_manager({
            "legacy": SimpleNamespace(metadata={"file_name": "legacy.txt"}),
        }),
        "kb-a": build_manager({
            "doc-a": SimpleNamespace(metadata={"file_name": "a.txt", "kb_id": "kb-a"}),
        }),
        "kb-b": build_manager({
            "doc-b": SimpleNamespace(metadata={"file_name": "b.txt", "kb_id": "kb-b"}),
        }),
    }

    get_manager = MagicMock(side_effect=lambda kb_id="default": managers[kb_id])
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", get_manager)

    docs = kb_service.list_docs()

    assert {doc["id"] for doc in docs} == {"legacy", "doc-a", "doc-b"}
    assert {doc["kb_id"] for doc in docs} == {"default", "kb-a", "kb-b"}
    assert [call.args[0] for call in get_manager.call_args_list] == ["default", "kb-a", "kb-b"]


def test_preview_document_uses_requested_kb_manager(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")

    preview_node = SimpleNamespace(
        text="Preview excerpt",
        metadata={"kb_id": "kb-a", "file_name": "manual.pdf", "page_label": "7"},
        node_id="node-1",
    )
    ref_doc = SimpleNamespace(
        metadata={"kb_id": "kb-a", "file_name": "manual.pdf", "title": "manual.pdf"},
        node_ids=["node-1"],
    )
    docstore = MagicMock()
    docstore.get_ref_doc_info.return_value = ref_doc
    docstore.get_nodes.return_value = [preview_node]
    docstore.docs = {"node-1": preview_node}
    manager = SimpleNamespace(storage_context=SimpleNamespace(docstore=docstore))

    get_manager = MagicMock(return_value=manager)
    ensure_index_loaded = MagicMock(return_value=True)
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", get_manager)
    monkeypatch.setattr(kb_service.runtime_state, "ensure_index_loaded", ensure_index_loaded)

    result = kb_service.preview_document(PreviewRequest(kb_id="kb-a", doc_id="doc-1"))

    assert result["kb_id"] == "kb-a"
    assert result["doc_id"] == "doc-1"
    assert result["locator"]["page"] == "7"
    ensure_index_loaded.assert_called_once_with("kb-a")
    get_manager.assert_called_once_with("kb-a")
