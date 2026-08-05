"""图片资产导入与接口测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from llama_index.core import Document

from server.text_splitter import create_text_splitter

from api.app import app
from api.services import asset_service, kb_service
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry

client = TestClient(app)


_OCR_TIMING_FIELDS = (
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
)
_DEFAULT_OCR_TIMING_VALUES = {
    "ocr_init_ms": 0.0,
    "ocr_load_image_ms": 0.0,
    "ocr_predict_ms": 0.0,
    "ocr_postprocess_ms": 0.0,
    "ocr_total_ms": 0.0,
    "ocr_instance_reused": False,
}


def _assert_ocr_timing_payload(payload: dict[str, object], expected: dict[str, object] | None = None) -> None:
    expected_values = dict(_DEFAULT_OCR_TIMING_VALUES)
    if expected:
        expected_values.update(expected)
    for key in _OCR_TIMING_FIELDS:
        assert key in payload
        assert payload[key] == pytest.approx(float(expected_values[key]))
    assert payload["ocr_instance_reused"] is bool(expected_values["ocr_instance_reused"])


class FakeUploadFile:
    """简化版上传文件对象，用于导入链路测试。"""

    def __init__(self, filename: str, content: bytes, content_type: str) -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


@pytest.fixture(autouse=True)
def _reset_registry_state() -> None:
    yield
    kb_service._registry = None
    asset_service._registry = None


def _patch_kb_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBRegistry:
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    monkeypatch.setattr(kb_service, "_registry", registry)
    return registry


def _patch_asset_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBAssetRegistry:
    registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    monkeypatch.setattr(asset_service, "_registry", registry)
    return registry


def _patch_runtime(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    manager = MagicMock()

    def _load_files(paths, chunk_size, chunk_overlap, kb_id=None, persist=True):
        path = Path(paths[0])
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}:
            return []
        return [SimpleNamespace(metadata={"file_path": str(path), "file_name": path.name}, text="plain text")]

    def _load_documents(documents, chunk_size, chunk_overlap, kb_id=None, persist=True):
        nodes = []
        for document in documents:
            metadata = dict(getattr(document, "metadata", {}) or {})
            if kb_id is not None:
                metadata["kb_id"] = kb_id
            nodes.append(SimpleNamespace(metadata=metadata, text=getattr(document, "text", "")))
        return nodes

    manager.load_files.side_effect = _load_files
    manager.load_documents.side_effect = _load_documents
    manager.persist_storage.return_value = True
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


def _patch_image_ocr(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: str,
    text: str = "",
    error: str | None = None,
    attempted: bool | None = None,
    engine: str = "mock-paddleocr",
    ocr_init_ms: float = 0.0,
    ocr_load_image_ms: float = 0.0,
    ocr_predict_ms: float = 0.0,
    ocr_postprocess_ms: float = 0.0,
    ocr_total_ms: float = 0.0,
    ocr_instance_reused: bool = False,
    failure_category: str | None = None,
    missing_dependency: str | None = None,
    dependency_status: str | None = None,
) -> None:
    """????????? OCR ???"""

    def _fake_extract_image_ocr_result(path: Path, content_type: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": status,
            "text": text,
            "error": error,
            "attempted": attempted if attempted is not None else status != "skipped",
            "engine": engine,
            "ocr_init_ms": ocr_init_ms,
            "ocr_load_image_ms": ocr_load_image_ms,
            "ocr_predict_ms": ocr_predict_ms,
            "ocr_postprocess_ms": ocr_postprocess_ms,
            "ocr_total_ms": ocr_total_ms,
            "ocr_instance_reused": ocr_instance_reused,
        }
        if failure_category is not None:
            payload["failure_category"] = failure_category
        if missing_dependency is not None:
            payload["missing_dependency"] = missing_dependency
        if dependency_status is not None:
            payload["dependency_status"] = dependency_status
        return payload

    monkeypatch.setattr(kb_service, "_extract_image_ocr_result", _fake_extract_image_ocr_result)


def test_image_import_registers_standalone_asset_even_when_ocr_returns_no_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """纯图片文件即使 OCR 无文本，也应登记为 standalone asset。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    expected_timing = {
        "ocr_init_ms": 12.5,
        "ocr_load_image_ms": 3.25,
        "ocr_predict_ms": 18.75,
        "ocr_postprocess_ms": 1.5,
        "ocr_total_ms": 36.0,
        "ocr_instance_reused": False,
    }
    _patch_image_ocr(monkeypatch, status="no_text", **expected_timing)

    result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/flow.png"],
        import_mode="preserve_tree",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert file_result["status"] == "empty"
    assert file_result["indexed_chunks"] == 0
    assert diagnostics["file_kind"] == "image"
    assert diagnostics["empty_reason"] == "no_extractable_text"
    assert diagnostics["standalone_asset_candidate"] is True
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "no_text"
    assert diagnostics["ocr_text_length"] == 0
    assert diagnostics["ocr_error"] is None
    assert diagnostics["indexed_from_ocr"] is False
    assert diagnostics["asset_registered"] is True
    _assert_ocr_timing_payload(diagnostics, expected_timing)
    assert result["diagnostics"]["total_files"] == 1
    assert result["diagnostics"]["empty_files"] == 1
    assert result["diagnostics"]["standalone_asset_candidate_count"] == 1
    assert result["diagnostics"]["embedded_asset_count"] == 0
    assert result["diagnostics"]["ocr_no_text_count"] == 1

    display_summary = result["display_summary"]
    assert display_summary["source_kind"] == "file_import"
    assert display_summary["item_label"] == "\u6587\u4ef6"
    assert display_summary["total_items"] == 1
    assert display_summary["indexed_items"] == 0
    assert display_summary["empty_items"] == 1
    assert display_summary["failed_items"] == 0
    assert display_summary["asset_registered_count"] == 1
    assert display_summary["asset_registered_but_not_indexed_count"] == 1
    assert display_summary["has_blockers"] is False
    assert display_summary["has_dependency_issues"] is False
    assert display_summary["has_warnings"] is True
    assert display_summary["top_missing_dependencies"] == []
    assert display_summary["headline"] == "1 \u4e2a\u56fe\u7247\u8d44\u4ea7\u5df2\u5165\u5e93\u4f46\u672a\u7d22\u5f15"
    assert "OCR" in display_summary["user_message"]
    assert any(
        item["action"] == "review_empty_assets" and item["label"] == "\u67e5\u770b 1 \u4e2a\u672a\u7d22\u5f15\u56fe\u7247\u8d44\u4ea7"
        for item in display_summary["next_actions"]
    )

    receipt = kb_service.get_latest_import_receipt("kb-a")
    assert receipt is not None
    assert receipt["result"]["display_summary"]["asset_registered_but_not_indexed_count"] == 1
    manager.load_documents.assert_not_called()

    assets = asset_service.list_assets("kb-a")
    assert len(assets) == 1
    assert assets[0]["asset_role"] == "standalone"
    assert assets[0]["status"] == "active"
    assert assets[0]["relative_path"] == "docs/flow.png"
    assert assets[0]["mime_type"] == "image/png"
    assert assets[0]["ocr_attempted"] is True
    assert assets[0]["ocr_status"] == "no_text"
    assert assets[0]["ocr_text_length"] == 0
    assert assets[0]["ocr_error"] is None
    assert assets[0]["indexed_from_ocr"] is False
    assert assets[0]["asset_registered"] is True
    _assert_ocr_timing_payload(assets[0], expected_timing)
    assert assets[0]["ocr_diagnostics"]["ocr_status"] == "no_text"
    _assert_ocr_timing_payload(assets[0]["ocr_diagnostics"], expected_timing)


def test_image_import_without_extractable_text_does_not_warm_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """纯图片 OCR 无可提取文本时，不应预热 embedding 模型或索引管理器。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    ensure_models_ready = MagicMock(side_effect=AssertionError("unexpected ensure_models_ready call"))
    get_index_manager = MagicMock(side_effect=AssertionError("unexpected get_index_manager call"))
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", ensure_models_ready)
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", get_index_manager)
    _patch_image_ocr(monkeypatch, status="no_text")

    result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/flow.png"],
        import_mode="preserve_tree",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert file_result["status"] == "empty"
    assert diagnostics["empty_reason"] == "no_extractable_text"
    assert diagnostics["asset_registered"] is True
    batch_stage_timings = result["diagnostics"]["stage_timings"]
    assert batch_stage_timings["ensure_models_ready_ms"] == 0.0
    assert batch_stage_timings["get_index_manager_ms"] == 0.0
    ensure_models_ready.assert_not_called()
    get_index_manager.assert_not_called()

    assets = asset_service.list_assets("kb-a")
    assert len(assets) == 1
    assert assets[0]["asset_role"] == "standalone"
    assert assets[0]["ocr_status"] == "no_text"


def test_image_import_indexes_ocr_text_and_links_document_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """图片 OCR 成功时，应生成派生文本并把资产关联写入节点 metadata。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    ocr_text = "系统架构图\n订单服务 -> 支付服务"
    expected_timing = {
        "ocr_init_ms": 24.0,
        "ocr_load_image_ms": 4.0,
        "ocr_predict_ms": 30.5,
        "ocr_postprocess_ms": 2.25,
        "ocr_total_ms": 60.75,
        "ocr_instance_reused": True,
    }
    _patch_image_ocr(monkeypatch, status="success", text=ocr_text, **expected_timing)

    result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/arch/flow.png"],
        import_mode="preserve_tree",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert file_result["status"] == "indexed"
    assert file_result["indexed_chunks"] == 1
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "success"
    assert diagnostics["ocr_text_length"] == len(ocr_text)
    assert diagnostics["indexed_from_ocr"] is True
    assert diagnostics["asset_registered"] is True
    assert diagnostics["ocr_engine"] == "mock-paddleocr"
    _assert_ocr_timing_payload(diagnostics, expected_timing)
    assert result["diagnostics"]["indexed_files"] == 1
    assert result["diagnostics"]["ocr_success_count"] == 1
    assert manager.load_documents.call_count == 1
    assert manager.load_documents.call_args.kwargs["persist"] is False
    manager.persist_storage.assert_called_once_with()

    image_document = manager.load_documents.call_args[0][0][0]
    assert image_document.text == ocr_text
    assert image_document.metadata["kb_id"] == "kb-a"
    assert image_document.metadata["source_type"] == "image_ocr"
    assert image_document.metadata["relative_path"] == "docs/arch/flow.png"
    assert image_document.metadata["file_name"] == "flow.png"
    assert image_document.metadata["mime_type"] == "image/png"
    assert image_document.metadata["ocr_engine"] == "mock-paddleocr"
    assert image_document.metadata["asset_id"].startswith("asset-standalone-")

    assets = asset_service.list_assets("kb-a")
    assert len(assets) == 1
    assert assets[0]["asset_id"] == image_document.metadata["asset_id"]
    assert assets[0]["ocr_attempted"] is True
    assert assets[0]["ocr_status"] == "success"
    assert assets[0]["ocr_text_length"] == len(ocr_text)
    assert assets[0]["ocr_error"] is None
    assert assets[0]["indexed_from_ocr"] is True
    assert assets[0]["asset_registered"] is True
    assert assets[0]["ocr_engine"] == "mock-paddleocr"
    _assert_ocr_timing_payload(assets[0], expected_timing)
    _assert_ocr_timing_payload(assets[0]["ocr_diagnostics"], expected_timing)


def test_standalone_image_ocr_document_excludes_internal_metadata_from_chunk_budget(tmp_path: Path) -> None:
    """独立图片 OCR 文档应排除内部 metadata，避免小 chunk_size 时切块失败。"""
    image_path = tmp_path / "very" / "deep" / "nested" / "image" / "assets" / "for" / "chunk" / "budget" / "flow.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png")
    relative_path = "docs/" + "/".join(["very-deep"] * 8) + "/flow.png"
    ocr_result = {"text": "知识库是授权边界。", "engine": "mock-paddleocr"}

    document = kb_service._build_image_ocr_document(
        kb_id="kb-a",
        path=image_path,
        filename="flow.png",
        content_type="image/png",
        relative_path=relative_path,
        ocr_result=ocr_result,
    )

    assert document is not None
    assert "file_path" in document.metadata
    assert "file_path" in document.excluded_embed_metadata_keys
    assert "relative_path" in document.excluded_embed_metadata_keys
    assert "asset_id" in document.excluded_llm_metadata_keys

    splitter = create_text_splitter(chunk_size=128, chunk_overlap=16)
    raw_document = Document(text=document.text, metadata=dict(document.metadata))
    with pytest.raises(ValueError, match="Metadata length"):
        splitter.get_nodes_from_documents([raw_document])

    nodes = splitter.get_nodes_from_documents([document])
    assert len(nodes) == 1
    assert nodes[0].metadata["file_name"] == "flow.png"
    assert nodes[0].metadata["relative_path"] == relative_path



def test_image_import_keeps_asset_when_ocr_execution_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCR 执行失败时不应拖垮图片资产入库，只记录诊断并返回 empty。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    expected_timing = {
        "ocr_init_ms": 8.0,
        "ocr_load_image_ms": 2.0,
        "ocr_predict_ms": 14.5,
        "ocr_postprocess_ms": 0.0,
        "ocr_total_ms": 24.5,
        "ocr_instance_reused": False,
    }
    _patch_image_ocr(monkeypatch, status="failed", error="mock ocr crashed", **expected_timing)

    result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/flow.png"],
        import_mode="preserve_tree",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert file_result["status"] == "empty"
    assert file_result["indexed_chunks"] == 0
    assert diagnostics["empty_reason"] == "ocr_failed"
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "failed"
    assert diagnostics["ocr_text_length"] == 0
    assert diagnostics["ocr_error"] == "mock ocr crashed"
    assert diagnostics["indexed_from_ocr"] is False
    assert diagnostics["asset_registered"] is True
    _assert_ocr_timing_payload(diagnostics, expected_timing)
    assert result["diagnostics"]["empty_files"] == 1
    assert result["diagnostics"]["ocr_failed_count"] == 1
    manager.load_documents.assert_not_called()

    assets = asset_service.list_assets("kb-a")
    assert len(assets) == 1
    assert assets[0]["asset_role"] == "standalone"
    assert assets[0]["relative_path"] == "docs/flow.png"
    assert assets[0]["ocr_attempted"] is True
    assert assets[0]["ocr_status"] == "failed"
    assert assets[0]["ocr_text_length"] == 0
    assert assets[0]["ocr_error"] == "mock ocr crashed"
    assert assets[0]["indexed_from_ocr"] is False
    assert assets[0]["asset_registered"] is True
    _assert_ocr_timing_payload(assets[0], expected_timing)
    _assert_ocr_timing_payload(assets[0]["ocr_diagnostics"], expected_timing)


def test_image_import_surfaces_dependency_missing_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """?? OCR ???????????????????????"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    _patch_image_ocr(
        monkeypatch,
        status="failed",
        error="No module named 'paddleocr'",
        failure_category="dependency_missing",
        missing_dependency="paddleocr",
        dependency_status="missing",
    )

    result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/flow.png"],
        import_mode="preserve_tree",
    )

    file_result = result["file_results"][0]
    diagnostics = file_result["diagnostics"]
    assert file_result["status"] == "empty"
    assert diagnostics["empty_reason"] == "ocr_failed"
    assert diagnostics["failure_category"] == "dependency_missing"
    assert diagnostics["missing_dependency"] == "paddleocr"
    assert diagnostics["dependency_status"] == "missing"
    assert diagnostics["ocr_error"] == "No module named 'paddleocr'"
    assert result["diagnostics"]["ocr_failed_count"] == 1
    assert result["diagnostics"]["dependency_missing_count"] == 1
    assert result["diagnostics"]["failure_category_counts"]["dependency_missing"] == 1
    assert result["diagnostics"]["missing_dependency_counts"]["paddleocr"] == 1
    assert result["diagnostics"]["dependency_status_counts"]["missing"] == 1

    display_summary = result["display_summary"]
    assert display_summary["source_kind"] == "file_import"
    assert display_summary["has_blockers"] is True
    assert display_summary["has_dependency_issues"] is True
    assert display_summary["has_warnings"] is True
    assert display_summary["asset_registered_but_not_indexed_count"] == 1
    assert display_summary["top_missing_dependencies"] == [{"dependency": "paddleocr", "count": 1}]
    assert display_summary["headline"] == "1 \u4e2a\u6587\u4ef6\u56e0\u4f9d\u8d56\u7f3a\u5931\u672a\u5b8c\u6210\u5bfc\u5165"
    assert any(
        item["action"] == "install_dependency"
        and item.get("dependency") == "paddleocr"
        and item["label"] == "\u5b89\u88c5\u7f3a\u5931\u4f9d\u8d56\uff1apaddleocr"
        for item in display_summary["next_actions"]
    )

    receipt = kb_service.get_latest_import_receipt("kb-a")
    assert receipt is not None
    assert receipt["result"]["display_summary"]["top_missing_dependencies"] == [{"dependency": "paddleocr", "count": 1}]
    manager.load_documents.assert_not_called()

    assets = asset_service.list_assets("kb-a")
    assert len(assets) == 1
    assert assets[0]["ocr_status"] == "failed"
    assert assets[0]["ocr_error"] == "No module named 'paddleocr'"
    assert assets[0]["failure_category"] == "dependency_missing"
    assert assets[0]["missing_dependency"] == "paddleocr"
    assert assets[0]["dependency_status"] == "missing"
    assert assets[0]["ocr_diagnostics"]["failure_category"] == "dependency_missing"
    assert assets[0]["ocr_diagnostics"]["missing_dependency"] == "paddleocr"
    assert assets[0]["ocr_diagnostics"]["dependency_status"] == "missing"


def test_asset_routes_list_and_preview_registered_assets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """同图被 Markdown 引用时，资产列表应只保留 embedded 记录。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    kb_registry.create_kb("kb-b", "KB B")
    _patch_runtime(monkeypatch)
    expected_timing = {
        "ocr_init_ms": 6.0,
        "ocr_load_image_ms": 1.5,
        "ocr_predict_ms": 11.0,
        "ocr_postprocess_ms": 0.5,
        "ocr_total_ms": 19.0,
        "ocr_instance_reused": True,
    }
    _patch_image_ocr(monkeypatch, status="no_text", **expected_timing)

    kb_service.import_files(
        [
            FakeUploadFile(
                "readme.md",
                "![\u6d41\u7a0b\u56fe](./images/flow.png)".encode("utf-8").decode("unicode_escape").encode("utf-8"),
                content_type="text/markdown",
            ),
            FakeUploadFile("flow.png", b"png", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/readme.md", "docs/images/flow.png"],
        import_mode="preserve_tree",
    )

    registered_assets = asset_service.list_assets("kb-a")
    assert len(registered_assets) == 1
    embedded_asset = registered_assets[0]
    assert embedded_asset["asset_role"] == "embedded"
    assert embedded_asset["ocr_status"] == "no_text"
    assert embedded_asset["ocr_text_length"] == 0
    assert embedded_asset["indexed_from_ocr"] is False
    assert embedded_asset["asset_registered"] is True
    _assert_ocr_timing_payload(embedded_asset, expected_timing)
    assert embedded_asset["source_doc_relative_path"] == "docs/readme.md"
    _assert_ocr_timing_payload(embedded_asset["ocr_diagnostics"], expected_timing)

    resp = client.get("/api/kb/assets", params={"kb_id": "kb-a"})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["asset_role"] == "embedded"
    assert items[0]["ocr_status"] == "no_text"
    assert items[0]["indexed_from_ocr"] is False
    assert items[0]["asset_registered"] is True
    _assert_ocr_timing_payload(items[0], expected_timing)
    _assert_ocr_timing_payload(items[0]["ocr_diagnostics"], expected_timing)

    isolated = client.get("/api/kb/assets", params={"kb_id": "kb-b"})
    assert isolated.status_code == 200
    assert isolated.json()["data"]["items"] == []

    preview = client.get(f"/api/kb/assets/{embedded_asset['asset_id']}", params={"kb_id": "kb-a"})
    assert preview.status_code == 200
    payload = preview.json()["data"]
    assert payload["asset_id"] == embedded_asset["asset_id"]
    assert payload["source_doc_relative_path"] == "docs/readme.md"
    assert payload["locator"]["referenced_path"] == "./images/flow.png"
    assert payload["status"] == "active"
    assert payload["ocr_status"] == "no_text"
    assert payload["ocr_text_length"] == 0
    assert payload["indexed_from_ocr"] is False
    assert payload["asset_registered"] is True
    _assert_ocr_timing_payload(payload, expected_timing)
    _assert_ocr_timing_payload(payload["ocr_diagnostics"], expected_timing)

    blocked = client.get(f"/api/kb/assets/{embedded_asset['asset_id']}", params={"kb_id": "kb-b"})
    assert blocked.status_code == 404


def test_embedded_image_preempts_standalone_ocr_index_and_asset_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """同批导入同图时，应只走 embedded OCR/索引，不再额外登记 standalone。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)
    _patch_image_ocr(
        monkeypatch,
        status="success",
        text="审批流程图\n发起 -> 审批 -> 归档",
    )

    result = kb_service.import_files(
        [
            FakeUploadFile(
                "readme.md",
                "![\u6d41\u7a0b\u56fe](./images/flow.png)".encode("utf-8").decode("unicode_escape").encode("utf-8"),
                content_type="text/markdown",
            ),
            FakeUploadFile("flow.png", b"png", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/readme.md", "docs/images/flow.png"],
        import_mode="preserve_tree",
    )

    assert manager.load_documents.call_count == 1
    assert manager.load_documents.call_args.kwargs["persist"] is False
    manager.persist_storage.assert_called_once_with()
    indexed_document = manager.load_documents.call_args[0][0][0]
    assert indexed_document.metadata["source_doc_relative_path"] == "docs/readme.md"
    assert indexed_document.metadata["referenced_path"] == "./images/flow.png"
    assert indexed_document.metadata["relative_path"] == "docs/images/flow.png"

    markdown_result = result["file_results"][0]
    image_result = result["file_results"][1]
    assert markdown_result["status"] == "indexed"
    assert image_result["status"] == "empty"
    assert image_result["diagnostics"]["skip_standalone_asset"] is True
    assert image_result["diagnostics"]["asset_registered"] is False
    assert image_result["diagnostics"]["ocr_status"] == "skipped"
    _assert_ocr_timing_payload(image_result["diagnostics"])
    assert result["diagnostics"]["skip_standalone_asset_count"] == 1
    assert result["diagnostics"]["empty_reason_counts"]["shadowed_by_embedded_asset"] == 1

    registered_assets = asset_service.list_assets("kb-a")
    assert len(registered_assets) == 1
    assert registered_assets[0]["asset_role"] == "embedded"
    assert indexed_document.metadata["asset_id"] == registered_assets[0]["asset_id"]

def test_embedded_image_ocr_document_excludes_internal_metadata_from_chunk_budget(tmp_path: Path) -> None:
    """内嵌图片 OCR 文档应排除路径型 metadata，避免 128 chunk_size 下因元数据过长失败。"""
    asset_path = tmp_path / "playbooks" / "release" / "images" / "very" / "deep" / "nested" / "structure" / "escalation-board.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"png")
    source_doc_path = tmp_path / "playbooks" / "release" / "source" / "deep" / "nested" / "cutover.md"
    source_doc_path.parent.mkdir(parents=True, exist_ok=True)
    source_doc_path.write_text("![board](./images/escalation-board.png)\n", encoding="utf-8")
    asset = {
        "asset_id": "asset-embedded-kb-a-" + ("x" * 48),
        "path": str(asset_path),
        "resolved_relative_path": "playbooks/release/images/very/deep/nested/structure/escalation-board.png",
        "mime_type": "image/png",
        "source_doc_path": str(source_doc_path),
        "source_doc_relative_path": "playbooks/release/source/deep/nested/cutover.md",
        "referenced_path": "./images/escalation-board.png",
        "occurrence_index": 0,
    }
    ocr_result = {"text": "Knowledge Base is the authorization boundary.", "engine": "mock-paddleocr"}

    document = kb_service._build_embedded_image_ocr_document(kb_id="kb-a", asset=asset, ocr_result=ocr_result)

    assert document is not None
    assert "source_doc_path" in document.metadata
    assert "source_doc_path" in document.excluded_embed_metadata_keys
    assert "referenced_path" in document.excluded_llm_metadata_keys

    splitter = create_text_splitter(chunk_size=128, chunk_overlap=16)
    raw_document = Document(text=document.text, metadata=dict(document.metadata))
    with pytest.raises(ValueError, match="Metadata length"):
        splitter.get_nodes_from_documents([raw_document])

    nodes = splitter.get_nodes_from_documents([document])
    assert len(nodes) == 1
    assert nodes[0].metadata["file_name"] == "escalation-board.png"
    assert nodes[0].metadata["source_doc_relative_path"] == asset["source_doc_relative_path"]



def test_flatten_import_keeps_markdown_embedded_image_ready_via_batch_path_aliases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """flatten 导入同批 Markdown 与图片时，即使文件被改名，内嵌图片也不应落成 missing。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)
    _patch_image_ocr(monkeypatch, status="no_text")

    generated_names = iter(["readme_flat.md", "diagram_flat.png"])
    monkeypatch.setattr(
        kb_service.FilenameSanitizer,
        "generate_unique_filename",
        staticmethod(lambda safe_filename: next(generated_names)),
    )

    result = kb_service.import_files(
        [
            FakeUploadFile("readme.md", "![diagram](diagram.png)".encode("utf-8"), content_type="text/markdown"),
            FakeUploadFile("diagram.png", b"png", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        import_mode="flatten",
    )

    markdown_result = result["file_results"][0]
    image_result = result["file_results"][1]
    embedded_assets = markdown_result["embedded_assets"]

    assert markdown_result["relative_path"] == "readme_flat.md"
    assert image_result["relative_path"] == "diagram_flat.png"
    assert len(embedded_assets) == 1
    assert embedded_assets[0]["referenced_path"] == "diagram.png"
    assert embedded_assets[0]["logical_relative_path"] == "diagram.png"
    assert embedded_assets[0]["resolved_relative_path"] == "diagram_flat.png"
    assert embedded_assets[0]["status"] == "ready"
    assert Path(embedded_assets[0]["path"]).name == "diagram_flat.png"
    assert result["diagnostics"]["embedded_asset_ready_count"] == 1
    assert result["diagnostics"]["embedded_asset_missing_count"] == 0

    registered_assets = asset_service.list_assets("kb-a")
    assert len(registered_assets) == 1
    embedded_asset = registered_assets[0]
    assert embedded_asset["asset_role"] == "embedded"
    assert embedded_asset["source_doc_relative_path"] == "readme_flat.md"
    assert embedded_asset["relative_path"] == "diagram_flat.png"
    assert embedded_asset["locator"]["referenced_path"] == "diagram.png"


def test_flatten_import_does_not_guess_embedded_image_when_batch_alias_is_ambiguous(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """å½åæ¹å¯¼å
¥å­å¨å¤ä¸ªååå¾çæ¶ï¼flatten ä¸åºæ Markdown å¼ç¨è¯¯ç»å°ä»»æä¸ä¸ªéå½åæä»¶ã"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)
    _patch_image_ocr(monkeypatch, status="no_text")

    generated_names = iter(["readme_flat.md", "diagram_a.png", "diagram_b.png"])
    monkeypatch.setattr(
        kb_service.FilenameSanitizer,
        "generate_unique_filename",
        staticmethod(lambda safe_filename: next(generated_names)),
    )

    result = kb_service.import_files(
        [
            FakeUploadFile("readme.md", "![diagram](diagram.png)".encode("utf-8"), content_type="text/markdown"),
            FakeUploadFile("diagram.png", b"png-a", content_type="image/png"),
            FakeUploadFile("diagram.png", b"png-b", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        import_mode="flatten",
    )

    markdown_result = result["file_results"][0]
    embedded_assets = markdown_result["embedded_assets"]

    assert len(embedded_assets) == 1
    assert embedded_assets[0]["referenced_path"] == "diagram.png"
    assert embedded_assets[0]["logical_relative_path"] == "diagram.png"
    assert embedded_assets[0]["resolved_relative_path"] == "diagram.png"
    assert embedded_assets[0]["status"] == "missing"
    assert embedded_assets[0]["message"] == "asset file not found"
    assert result["diagnostics"]["embedded_asset_ready_count"] == 0
    assert result["diagnostics"]["embedded_asset_missing_count"] == 1

    registered_assets = asset_service.list_assets("kb-a")
    embedded_asset = next(item for item in registered_assets if item["asset_role"] == "embedded")
    assert embedded_asset["status"] == "missing"
    assert embedded_asset["relative_path"] == "diagram.png"
    assert embedded_asset["locator"]["referenced_path"] == "diagram.png"




def test_markdown_only_import_prunes_existing_standalone_asset_when_embedded_image_becomes_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """后续仅导入 Markdown 并解析出 embedded 图片时，应清理旧的 standalone 资产重复项。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)
    _patch_image_ocr(
        monkeypatch,
        status="success",
        text="审批流程图\n发起 -> 审批 -> 归档",
    )

    first_result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/images/flow.png"],
        import_mode="preserve_tree",
    )

    assert first_result["file_results"][0]["status"] == "indexed"
    first_assets = asset_service.list_assets("kb-a")
    assert len(first_assets) == 1
    assert first_assets[0]["asset_role"] == "standalone"
    standalone_asset_id = first_assets[0]["asset_id"]

    second_result = kb_service.import_files(
        [
            FakeUploadFile(
                "readme.md",
                "![流程图](./images/flow.png)".encode("utf-8"),
                content_type="text/markdown",
            )
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/readme.md"],
        import_mode="preserve_tree",
    )

    markdown_result = second_result["file_results"][0]
    assert markdown_result["status"] == "indexed"
    assert len(markdown_result["embedded_assets"]) == 1
    assert markdown_result["embedded_assets"][0]["status"] == "ready"

    assets_after_markdown = asset_service.list_assets("kb-a")
    assert len(assets_after_markdown) == 1
    assert assets_after_markdown[0]["asset_role"] == "embedded"
    assert assets_after_markdown[0]["relative_path"] == "docs/images/flow.png"
    assert assets_after_markdown[0]["source_doc_relative_path"] == "docs/readme.md"
    assert assets_after_markdown[0]["asset_id"] != standalone_asset_id



def test_image_reimport_stays_shadowed_when_existing_embedded_asset_already_owns_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """已有 embedded 关系时，单独重导入同路径图片不应再生成 standalone 资产。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)
    _patch_image_ocr(
        monkeypatch,
        status="success",
        text="审批流程图\n发起 -> 审批 -> 归档",
    )

    first_result = kb_service.import_files(
        [
            FakeUploadFile(
                "readme.md",
                "![流程图](./images/flow.png)".encode("utf-8"),
                content_type="text/markdown",
            ),
            FakeUploadFile("flow.png", b"png", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/readme.md", "docs/images/flow.png"],
        import_mode="preserve_tree",
    )

    assert first_result["diagnostics"]["skip_standalone_asset_count"] == 1
    assets_after_first_import = asset_service.list_assets("kb-a")
    assert len(assets_after_first_import) == 1
    assert assets_after_first_import[0]["asset_role"] == "embedded"
    embedded_asset_id = assets_after_first_import[0]["asset_id"]

    second_result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png-new", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/images/flow.png"],
        import_mode="preserve_tree",
    )

    image_result = second_result["file_results"][0]
    assert image_result["status"] == "empty"
    assert image_result["diagnostics"]["skip_standalone_asset"] is True
    assert image_result["diagnostics"]["asset_registered"] is False
    assert second_result["diagnostics"]["skip_standalone_asset_count"] == 1
    assert second_result["diagnostics"]["empty_reason_counts"]["shadowed_by_embedded_asset"] == 1

    assets_after_reimport = asset_service.list_assets("kb-a")
    assert len(assets_after_reimport) == 1
    assert assets_after_reimport[0]["asset_role"] == "embedded"
    assert assets_after_reimport[0]["asset_id"] == embedded_asset_id
    assert assets_after_reimport[0]["relative_path"] == "docs/images/flow.png"
