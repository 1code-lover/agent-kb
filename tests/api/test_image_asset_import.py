"""图片资产导入与接口测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

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

    def _load_files(paths, chunk_size, chunk_overlap, kb_id=None):
        path = Path(paths[0])
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}:
            return []
        return [SimpleNamespace(metadata={"file_path": str(path), "file_name": path.name}, text="plain text")]

    def _load_documents(documents, chunk_size, chunk_overlap, kb_id=None):
        nodes = []
        for document in documents:
            metadata = dict(getattr(document, "metadata", {}) or {})
            if kb_id is not None:
                metadata["kb_id"] = kb_id
            nodes.append(SimpleNamespace(metadata=metadata, text=getattr(document, "text", "")))
        return nodes

    manager.load_files.side_effect = _load_files
    manager.load_documents.side_effect = _load_documents
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
) -> None:
    """按测试场景注入图片 OCR 结果。"""

    def _fake_extract_image_ocr_result(path: Path, content_type: str) -> dict[str, object]:
        return {
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
