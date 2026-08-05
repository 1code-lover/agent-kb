"""半真实 image OCR 单库问答回归测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import asset_service, kb_service
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry
from server.utils.file import get_kb_data_dir
from tests.api._semireal_chat_support import FakeUploadFile, SemirealIndexManager, SemirealQueryEngine
from tests.api.chat_qa_metrics import build_chat_case_report, summarize_chat_case_reports

client = TestClient(app)
KB_ID = "kb-image"
IMAGE_IMPORTS = {
    "scope-board.png": {
        "relative_path": "images/contracts/scope-board.png",
        "ocr_text": "requested_scope_type must remain single_kb and effective_kb_ids should echo the declared image knowledge base.",
    },
    "folder-board.png": {
        "relative_path": "images/architecture/folder-board.png",
        "ocr_text": "Folder is an organization object, 中文补充：文件夹只是知识库内部的组织对象. Knowledge Base is the authorization boundary for image OCR answers, 中文补充：图片 OCR 回答也必须遵守知识库边界。",
    },
    "evidence-board.png": {
        "relative_path": "images/evidence/evidence-board.png",
        "ocr_text": "Evidence output should include doc_id preview_locator and a resolvable excerpt for OCR derived assets. 中文补充：证据结果至少要包含 doc_id 和 preview_locator。",
    },
}
IMAGE_CASES = [
    {
        "case_id": "image-scope-contract",
        "category": "fact",
        "question": "From the scope board, what should requested_scope_type remain and how should effective_kb_ids behave?",
        "expected_doc": "scope-board.png",
        "expected_keypoints": ["requested_scope_type must remain single_kb", "effective_kb_ids should echo the declared image knowledge base"],
        "must_not_contain": ["kb-shadow", "cross kb"],
        "preview_terms": ["requested_scope_type", "effective_kb_ids"],
        "expected_source_count": 1,
    },
    {
        "case_id": "image-folder-boundary",
        "category": "architecture",
        "question": "According to the folder board, what is the authorization boundary?",
        "expected_doc": "folder-board.png",
        "expected_keypoints": ["Folder is an organization object", "Knowledge Base is the authorization boundary for image OCR answers"],
        "must_not_contain": ["Folder is the authorization boundary"],
        "preview_terms": ["organization object", "authorization boundary"],
        "expected_source_count": 1,
    },
    {
        "case_id": "image-evidence-contract",
        "category": "policy",
        "question": "What should evidence output include according to the evidence board?",
        "expected_doc": "evidence-board.png",
        "expected_keypoints": ["Evidence output should include doc_id preview_locator", "resolvable excerpt for OCR derived assets"],
        "must_not_contain": ["empty evidence"],
        "preview_terms": ["doc_id", "preview_locator"],
        "expected_source_count": 1,
    },
    {
        "case_id": "image-folder-boundary-zh",
        "category": "architecture",
        "question": "根据 folder board，图片 OCR 回答的授权边界是什么？",
        "expected_doc": "folder-board.png",
        "expected_keypoints": ["Knowledge Base", "图片 OCR 回答也必须遵守知识库边界"],
        "must_not_contain": ["Folder is the authorization boundary"],
        "preview_terms": ["Knowledge Base", "知识库边界"],
        "expected_source_count": 1,
    },
    {
        "case_id": "image-evidence-contract-zh",
        "category": "policy",
        "question": "根据 evidence board，证据结果至少要包含哪两个字段？",
        "expected_doc": "evidence-board.png",
        "expected_keypoints": ["doc_id", "preview_locator", "证据结果至少要包含 doc_id 和 preview_locator"],
        "must_not_contain": ["empty evidence"],
        "preview_terms": ["doc_id", "preview_locator"],
        "expected_source_count": 1,
    },
    {
        "case_id": "image-no-evidence",
        "category": "no-evidence",
        "question": "Which record defines tenant shard checksum escrow and namespace pinning barriers?",
        "expected_doc": None,
        "expected_keypoints": ["No confirmable information is available in the current knowledge base."],
        "must_not_contain": ["scope-board.png", "folder-board.png"],
        "preview_terms": [],
        "expected_source_count": 0,
    },
]


@pytest.fixture(autouse=True)
def _reset_service_state():
    yield
    kb_service._registry = None
    asset_service._registry = None


@pytest.fixture
def image_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    import api.services.chat_service as chat_service

    kb_registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    asset_registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    kb_service._registry = kb_registry
    asset_service._registry = asset_registry
    kb_registry.create_kb(KB_ID, "Image OCR KB")

    manager = SemirealIndexManager(kb_id=KB_ID, kb_dir=get_kb_data_dir(KB_ID, create=True))
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock(return_value=True))
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(
        chat_service.runtime_state,
        "ensure_index_loaded",
        MagicMock(side_effect=lambda kb_id=None: manager.check_index_exists()),
    )
    build_query_engine = MagicMock(side_effect=lambda kb_ids=None: SemirealQueryEngine(manager))
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", build_query_engine)
    monkeypatch.setattr(chat_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(chat_service, "append_chat_message", lambda *args, **kwargs: None)

    def _fake_extract_image_ocr_result(path: Path, content_type: str):
        payload = IMAGE_IMPORTS[path.name]
        return {
            "status": "success",
            "text": payload["ocr_text"],
            "error": None,
            "attempted": True,
            "engine": "mock-paddleocr",
            "ocr_init_ms": 4.0,
            "ocr_load_image_ms": 1.0,
            "ocr_predict_ms": 10.0,
            "ocr_postprocess_ms": 0.5,
            "ocr_total_ms": 15.5,
            "ocr_instance_reused": True,
        }

    monkeypatch.setattr(kb_service, "_extract_image_ocr_result", _fake_extract_image_ocr_result)

    return {
        "kb_registry": kb_registry,
        "asset_registry": asset_registry,
        "manager": manager,
        "build_query_engine": build_query_engine,
        "tmp_path": tmp_path,
    }


@pytest.fixture
def imported_image_kb(image_runtime: dict[str, object]):
    uploads = []
    relative_paths = []
    for name, payload in IMAGE_IMPORTS.items():
        uploads.append(
            FakeUploadFile(
                filename=name,
                content=f"fake-image:{name}".encode("utf-8"),
                content_type="image/png",
            )
        )
        relative_paths.append(str(payload["relative_path"]))

    result = kb_service.import_files(
        uploads,
        chunk_size=128,
        chunk_overlap=16,
        kb_id=KB_ID,
        relative_paths=relative_paths,
        import_mode="preserve_tree",
    )

    image_runtime["import_result"] = result
    image_runtime["relative_paths"] = relative_paths
    return image_runtime


def _query_case(case: dict[str, object]) -> tuple[dict[str, object], dict[str, object] | None]:
    resp = client.post(
        "/api/chat/query",
        json={
            "question": case["question"],
            "session_id": case["case_id"],
            "kb_ids": [KB_ID],
        },
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    expected_source_count = int(case.get("expected_source_count", 1))
    if expected_source_count == 0:
        return payload, None

    evidence = payload["evidence"][0]
    preview_resp = client.post(
        "/api/kb/preview",
        json={
            "kb_id": KB_ID,
            "evidence_id": evidence["id"],
        },
    )
    assert preview_resp.status_code == 200
    return payload, preview_resp.json()["data"]


def test_image_ocr_semireal_case_matrix_is_broad_enough() -> None:
    """确保 OCR 半真实层至少覆盖事实、架构、策略与拒答四类场景。"""
    categories = {str(case["category"]) for case in IMAGE_CASES}
    assert {"fact", "architecture", "policy", "no-evidence"}.issubset(categories)
    assert len(IMAGE_CASES) >= 4


def test_image_ocr_import_registers_assets_and_indexes_docs(imported_image_kb: dict[str, object]) -> None:
    """验证图片导入后，OCR 文本入索引且图片资产完成注册。"""
    result = imported_image_kb["import_result"]
    manager: SemirealIndexManager = imported_image_kb["manager"]
    tmp_path: Path = imported_image_kb["tmp_path"]

    assert result["kb_id"] == KB_ID
    assert result["success_count"] == len(IMAGE_IMPORTS)
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert result["display_summary"]["asset_registered_count"] == len(IMAGE_IMPORTS)
    assert result["display_summary"]["asset_registered_but_not_indexed_count"] == 0
    assert len(manager.documents) == len(IMAGE_IMPORTS)

    assets = asset_service.list_assets(KB_ID)
    assert len(assets) == len(IMAGE_IMPORTS)
    assets_by_title = {item["title"]: item for item in assets}
    for name, payload in IMAGE_IMPORTS.items():
        relative_path = str(payload["relative_path"])
        item = assets_by_title[name]
        assert item["relative_path"] == relative_path
        assert item["ocr_status"] == "success"
        assert item["indexed_from_ocr"] is True
        assert item["ocr_text_length"] > 0
        assert (tmp_path / "data" / KB_ID / relative_path).is_file()


@pytest.mark.parametrize("case", IMAGE_CASES, ids=[case["case_id"] for case in IMAGE_CASES])
def test_chat_image_ocr_semireal_contract(case: dict[str, object], imported_image_kb: dict[str, object]) -> None:
    """逐条验证图片 OCR 单库问答、证据与 preview 契约。"""
    build_query_engine: MagicMock = imported_image_kb["build_query_engine"]
    payload, preview = _query_case(case)

    assert payload["requested_scope_type"] == "single_kb"
    assert payload["requested_kb_ids"] == [KB_ID]
    assert payload["effective_scope_type"] == "single_kb"
    assert payload["effective_kb_ids"] == [KB_ID]
    assert payload["is_default_deny_applied"] is False
    assert payload["isolation_level"] == "logical_filter_only"

    answer = payload["answer"]
    for keypoint in case["expected_keypoints"]:
        assert keypoint in answer
    for blocked in case["must_not_contain"]:
        assert blocked not in answer

    expected_source_count = int(case.get("expected_source_count", 1))
    assert len(payload["sources"]) == expected_source_count
    assert len(payload["evidence"]) == expected_source_count

    if expected_source_count == 0:
        assert case["expected_doc"] is None
        assert payload["sources"] == []
        assert payload["evidence"] == []
    else:
        source = payload["sources"][0]
        evidence = payload["evidence"][0]
        assert source["file"] == case["expected_doc"]
        assert evidence["title"] == case["expected_doc"]
        assert evidence["source"] == case["expected_doc"]
        assert evidence["doc_id"]
        assert evidence["preview_locator"]["page"] == "1"
        assert evidence["preview_locator"]["node_id"].startswith("node-")

        assert preview is not None
        assert preview["doc_id"] == evidence["doc_id"]
        assert preview["locator"]["page"] == "1"
        assert preview["locator"]["node_id"] == evidence["preview_locator"]["node_id"]
        for term in case["preview_terms"]:
            assert term in preview["excerpt"]

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=[KB_ID],
        expected_isolation_level="logical_filter_only",
        preview_payload=preview,
    )
    assert report["passed"] is True
    assert report["scope_passed"] is True
    assert report["keypoint_coverage"] == 1.0
    assert report["blocked_term_clean"] is True
    assert report["source_count_match"] is True
    assert report["evidence_hit"] is True
    if report["preview_required"]:
        assert report["preview_resolvable"] is True
        assert report["preview_term_coverage"] == 1.0

    build_query_engine.assert_called_once_with(kb_ids=[KB_ID])


def test_chat_image_ocr_semireal_suite_metrics(imported_image_kb: dict[str, object]) -> None:
    """图片 OCR 半真实层需要输出 suite 级指标，用于测试报告聚合。"""
    build_query_engine: MagicMock = imported_image_kb["build_query_engine"]
    reports = []
    for case in IMAGE_CASES:
        payload, preview = _query_case(case)
        reports.append(
            build_chat_case_report(
                case,
                payload,
                expected_kb_ids=[KB_ID],
                expected_isolation_level="logical_filter_only",
                preview_payload=preview,
            )
        )

    summary = summarize_chat_case_reports(reports)
    assert summary["total_cases"] == len(IMAGE_CASES)
    assert summary["passed_cases"] == len(IMAGE_CASES)
    assert summary["failed_cases"] == 0
    assert summary["pass_rate"] == 1.0
    assert summary["scope_pass_rate"] == 1.0
    assert summary["average_keypoint_coverage"] == 1.0
    assert summary["evidence_hit_rate"] == 1.0
    assert summary["preview_resolvable_rate"] == 1.0
    assert summary["source_count_match_rate"] == 1.0
    assert summary["forbidden_term_clean_rate"] == 1.0
    assert summary["category_breakdown"]["no-evidence"]["count"] == 1
    assert build_query_engine.call_count == len(IMAGE_CASES)
