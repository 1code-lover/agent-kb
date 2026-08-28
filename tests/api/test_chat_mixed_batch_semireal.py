"""半真实 mixed batch 导入与问答回归测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import fitz
from tests.api._testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
import pytest

from api.app import app
from api.services import asset_service, kb_service
import api.services.chat_service as chat_service
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry
from server.utils.font_fallbacks import OCR_FONT_CANDIDATES, load_first_available_font
from server.utils.file import get_kb_data_dir
from tests.api._semireal_chat_support import FakeUploadFile, SemirealIndexManager, SemirealQueryEngine
from tests.api.chat_qa_metrics import build_chat_case_report, summarize_chat_case_reports

KB_ID = "realish-batch-kb"
FONT_CANDIDATES = OCR_FONT_CANDIDATES
MIXED_IMPORT_PATHS = {
    "cutover.md": "playbooks/release/cutover.md",
    "escalation-board.png": "playbooks/release/images/escalation-board.png",
    "vendor-cutover.pdf": "reports/vendor-cutover.pdf",
    "preview-board.png": "boards/preview-board.png",
}
CONTENT_TYPES = {
    "cutover.md": "text/markdown",
    "escalation-board.png": "image/png",
    "vendor-cutover.pdf": "application/pdf",
    "preview-board.png": "image/png",
}
OCR_TEXT_BY_FILE = {
    "escalation-board.png": (
        "Escalation board reminder. "
        "Knowledge Base is the authorization boundary. "
        "Folder remains organization only. "
        "中文补充：混合导入场景里授权边界仍然是知识库。"
    ),
    "preview-board.png": (
        "Evidence preview checklist. "
        "Every evidence preview must include doc_id and preview_locator. "
        "中文补充：每条证据预览至少包含 doc_id 和 preview_locator。"
    ),
}
MIXED_CASES = [
    {
        "case_id": "mixed-markdown-rollback-owner",
        "category": "markdown_fact",
        "question": "Who gives the final rollback approval after the deployment coordinator summarizes the evidence?",
        "expected_keypoints": ["platform duty lead"],
        "must_not_contain": ["outside memory"],
        "expected_source_count": 1,
        "expected_doc": "cutover.md",
        "required_evidence_docs": ["cutover.md"],
        "preview_terms": ["platform duty lead"],
    },
    {
        "case_id": "mixed-pdf-checklist-signer",
        "category": "pdf_fact",
        "question": "Who signs the cutover checklist before traffic moves to the vendor stack?",
        "expected_keypoints": ["customer success lead"],
        "must_not_contain": ["outside memory"],
        "expected_source_count": 1,
        "expected_doc": "vendor-cutover.pdf",
        "required_evidence_docs": ["vendor-cutover.pdf"],
        "preview_terms": ["customer success lead"],
    },
    {
        "case_id": "mixed-embedded-image-boundary",
        "category": "embedded_image_fact",
        "question": "Answer in a complete short sentence: according to the escalation board image, what remains the authorization boundary?",
        "expected_keypoints": ["knowledge base", "authorization boundary"],
        "must_not_contain": ["outside memory"],
        "expected_source_count": 1,
        "expected_doc": "escalation-board.png",
        "required_evidence_docs": ["escalation-board.png"],
        "preview_terms": ["knowledge base", "authorization boundary"],
    },
    {
        "case_id": "mixed-standalone-image-preview-fields",
        "category": "standalone_image_fact",
        "question": "Which two fields must every evidence preview include?",
        "expected_keypoints": ["doc_id", "preview_locator"],
        "must_not_contain": ["outside memory"],
        "expected_source_count": 1,
        "expected_doc": "preview-board.png",
        "required_evidence_docs": ["preview-board.png"],
        "preview_terms": ["doc_id", "preview_locator"],
    },
    {
        "case_id": "mixed-markdown-rollback-owner-zh",
        "category": "markdown_fact_zh",
        "question": "请用中文回答：谁在部署协调人汇总证据后给出最终回滚批准？",
        "expected_keypoints": ["platform duty lead", "最终回滚批准人仍然是 platform duty lead"],
        "must_not_contain": ["outside memory"],
        "expected_source_count": 1,
        "expected_doc": "cutover.md",
        "required_evidence_docs": ["cutover.md"],
        "preview_terms": ["platform duty lead", "最终回滚批准人"],
    },
    {
        "case_id": "mixed-cross-doc-rollback-and-signer",
        "category": "cross_document",
        "question": "Compare the Friday release cutover note and the vendor cutover checklist: who gives the final rollback approval and who signs the checklist before traffic moves to the vendor stack?",
        "expected_keypoints": ["platform duty lead", "customer success lead"],
        "must_not_contain": ["outside memory"],
        "expected_source_count": 2,
        "expected_doc": None,
        "required_evidence_docs": ["cutover.md", "vendor-cutover.pdf"],
        "preview_terms": ["platform duty lead", "customer success lead"],
    },
    {
        "case_id": "mixed-cross-image-boundary-and-preview",
        "category": "cross_document",
        "question": "Compare the escalation board image and the evidence preview board: what remains the authorization boundary, and does the preview board explicitly require doc_id and preview_locator?",
        "expected_keypoints": ["knowledge base", "doc_id", "preview_locator"],
        "must_not_contain": ["outside memory"],
        "expected_source_count": 2,
        "expected_doc": None,
        "required_evidence_docs": ["escalation-board.png", "preview-board.png"],
        "preview_terms": ["knowledge base", "doc_id", "preview_locator"],
    },
    {
        "case_id": "mixed-no-evidence-refusal",
        "category": "no_evidence",
        "question": "What is the GPU memory requirement for the mobile build?",
        "expected_keypoints": ["No confirmable information is available"],
        "must_not_contain": ["8 GB", "16 GB", "24 GB"],
        "expected_source_count": 0,
        "expected_doc": None,
        "required_evidence_docs": [],
        "preview_terms": [],
    },
]


def _pick_font(size: int = 28) -> ImageFont.ImageFont:
    """优先选择支持中文的系统字体，避免 fixture 渲染失真。"""
    font, _ = load_first_available_font(size=size, candidates=FONT_CANDIDATES)
    return font



def _create_text_image(path: Path, lines: list[str]) -> None:
    """生成带文字内容的 PNG fixture。"""
    font = _pick_font()
    image = Image.new("RGB", (1280, 720), color="white")
    draw = ImageDraw.Draw(image)
    y = 60
    for line in lines:
        draw.text((60, y), line, fill="black", font=font)
        y += 120
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)



def _create_text_pdf(path: Path, text: str) -> None:
    """生成带文字层的 PDF fixture。"""
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(48, 48, 560, 780), text)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()



def _build_source_workspace(base_dir: Path) -> dict[str, Path]:
    """搭建 mixed batch 导入源目录。"""
    source_dir = base_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = source_dir / "cutover.md"
    markdown_path.write_text(
        """# Friday release cutover

The Friday release cutover note explains who can approve rollback decisions.
The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence.
中文补充：最终回滚批准人仍然是 platform duty lead。
The team also keeps an escalation board image next to the runbook for scope reminders.

![Escalation board](./images/escalation-board.png)
""",
        encoding="utf-8",
    )

    embedded_image_path = source_dir / "escalation-board.png"
    _create_text_image(
        embedded_image_path,
        [
            "Escalation board reminder",
            "Knowledge Base is the authorization boundary",
            "Folder remains organization only",
            "中文补充：混合导入场景里授权边界仍然是知识库。",
        ],
    )

    pdf_path = source_dir / "vendor-cutover.pdf"
    _create_text_pdf(
        pdf_path,
        (
            "Vendor cutover checklist. "
            "The customer success lead signs the cutover checklist before traffic moves to the vendor stack. "
            "中文补充：切流到 vendor stack 之前，由 customer success lead 签署 cutover checklist。 "
            "The duty SRE confirms rollback readiness afterwards."
        ),
    )

    standalone_image_path = source_dir / "preview-board.png"
    _create_text_image(
        standalone_image_path,
        [
            "Evidence preview checklist",
            "Every evidence preview must include doc_id and preview_locator",
            "中文补充：每条证据预览至少包含 doc_id 和 preview_locator。",
        ],
    )

    return {
        "cutover.md": markdown_path,
        "escalation-board.png": embedded_image_path,
        "vendor-cutover.pdf": pdf_path,
        "preview-board.png": standalone_image_path,
    }



def _build_mixed_upload_batch(source_paths: dict[str, Path]) -> tuple[list[FakeUploadFile], list[str]]:
    """æåºå® relative_path ç»è£ mixed batch ä¸ä¼ è´è½½ã"""
    uploads: list[FakeUploadFile] = []
    relative_paths: list[str] = []
    for name, relative_path in MIXED_IMPORT_PATHS.items():
        uploads.append(
            FakeUploadFile(
                filename=name,
                content=source_paths[name].read_bytes(),
                content_type=CONTENT_TYPES[name],
            )
        )
        relative_paths.append(relative_path)
    return uploads, relative_paths


def _import_mixed_batch(source_paths: dict[str, Path]) -> dict[str, Any]:
    """ä»¥ preserve_tree æ¨¡å¼å¯¼å¥ mixed batch æä»¶ã"""
    uploads, relative_paths = _build_mixed_upload_batch(source_paths)
    return kb_service.import_files(
        uploads,
        chunk_size=128,
        chunk_overlap=16,
        kb_id=KB_ID,
        relative_paths=relative_paths,
        import_mode="preserve_tree",
    )


def _rewrite_source_workspace_for_reimport(source_paths: dict[str, Path], ocr_text_by_file: dict[str, str]) -> None:
    """éå mixed batch fixture åå®¹ï¼æ¨¡æåç®å½éå¯¼å¥ã"""
    source_paths["cutover.md"].write_text(
        """# Friday release cutover

The Friday release cutover note now records the reimported approval chain.
The incident commander gives the final rollback approval after the deployment coordinator summarizes the evidence.
ä¸­æè¡¥åï¼éå¯¼å¥åæç»åæ»æ¹åäººæ¹æ incident commanderã
The team still keeps an escalation board image next to the runbook for scope reminders.

![Escalation board](./images/escalation-board.png)
""",
        encoding="utf-8",
    )
    _create_text_pdf(
        source_paths["vendor-cutover.pdf"],
        (
            "Vendor cutover checklist revision. "
            "The service transition manager signs the cutover checklist before traffic moves to the vendor stack. "
            "ä¸­æè¡¥åï¼è¿ç§»å° vendor stack åç± service transition manager ç­¾ç½² cutover checklistã "
            "The duty SRE confirms rollback readiness afterwards."
        ),
    )
    _create_text_image(
        source_paths["escalation-board.png"],
        [
            "Escalation board revision",
            "Explicit knowledge base scope contract is the only authorization boundary",
            "Folder remains navigation only",
            "ä¸­æè¡¥åï¼åªææ¾å¼ scope contract ææ¯ææè¾¹çï¼æä»¶å¤¹ä»ç¶åªæ¿æå¯¼èªä½ç¨ã",
        ],
    )
    _create_text_image(
        source_paths["preview-board.png"],
        [
            "Evidence preview checklist revision",
            "Every evidence preview must include doc_id and asset_id",
            "ä¸­æè¡¥åï¼æ´æ°åçè¯æ®é¢è§å¿é¡»æ¾å¼æºå¸¦ doc_id å asset_idã",
        ],
    )
    ocr_text_by_file.update(
        {
            "escalation-board.png": (
                "Escalation board revision. "
                "Explicit knowledge base scope contract is the only authorization boundary. "
                "Folder remains navigation only. "
                "ä¸­æè¡¥åï¼åªææ¾å¼ scope contract ææ¯ææè¾¹çï¼æä»¶å¤¹ä»ç¶åªæ¿æå¯¼èªä½ç¨ã"
            ),
            "preview-board.png": (
                "Evidence preview checklist revision. "
                "Every evidence preview must include doc_id and asset_id. "
                "ä¸­æè¡¥åï¼æ´æ°åçè¯æ®é¢è§å¿é¡»æ¾å¼æºå¸¦ doc_id å asset_idã"
            ),
        }
    )


def _documents_by_title(manager: SemirealIndexManager) -> dict[str, dict[str, Any]]:
    """æ title æé ææ¡£å¿«ç§ï¼ä¾¿äºå¯¹æ¯éå¯¼å¥ååã"""
    return {document["title"]: document for document in manager.documents}


def _asset_ids_by_role(kb_id: str) -> dict[str, str]:
    """æ asset_role è¿åå½åç¥è¯åºä¸­çç¨³å® asset_idã"""
    return {item["asset_role"]: item["asset_id"] for item in asset_service.list_assets(kb_id)}


def _build_query_engine(
    manager: SemirealIndexManager,
    kb_ids: list[str] | None = None,
    **kwargs: Any,
) -> SemirealQueryEngine:
    """构造受控的单库 query engine。"""
    normalized = list(kb_ids or [])
    if normalized != [KB_ID]:
        raise ValueError(f"mixed semireal harness expects [{KB_ID!r}], got: {normalized}")
    return SemirealQueryEngine(manager)


@pytest.fixture
def imported_mixed_kb(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """准备包含 Markdown、PDF 与图片的混合导入知识库。"""
    monkeypatch.chdir(tmp_path)

    kb_registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    asset_registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    kb_registry.create_kb(KB_ID, "Mixed Batch KB")

    monkeypatch.setattr(kb_service, "_registry", kb_registry)
    monkeypatch.setattr(asset_service, "_registry", asset_registry)

    manager = SemirealIndexManager(kb_id=KB_ID, kb_dir=get_kb_data_dir(KB_ID, create=True))
    build_query_engine = MagicMock(side_effect=lambda kb_ids=None, **kwargs: _build_query_engine(manager, kb_ids, **kwargs))

    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock(return_value=True))
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", build_query_engine)
    monkeypatch.setattr(chat_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(chat_service, "append_chat_message", lambda *args, **kwargs: None)

    ocr_text_by_file = dict(OCR_TEXT_BY_FILE)

    def fake_extract_image_ocr_result(path: Path, content_type: str) -> dict[str, Any]:
        del content_type
        text = ocr_text_by_file[path.name]
        return {
            "status": "success",
            "text": text,
            "error": None,
            "attempted": True,
            "engine": "mock-paddleocr",
            "ocr_init_ms": 4.0,
            "ocr_load_image_ms": 1.0,
            "ocr_predict_ms": 8.0,
            "ocr_total_ms": 13.0,
        }

    monkeypatch.setattr(kb_service, "_extract_image_ocr_result", fake_extract_image_ocr_result)

    source_paths = _build_source_workspace(tmp_path)
    result = _import_mixed_batch(source_paths)

    client = TestClient(app)
    try:
        yield {
            "tmp_path": tmp_path,
            "manager": manager,
            "build_query_engine": build_query_engine,
            "import_result": result,
            "client": client,
            "kb_registry": kb_registry,
            "source_paths": source_paths,
            "ocr_text_by_file": ocr_text_by_file,
        }
    finally:
        client.close()



def _merge_preview_payloads(preview_payloads: list[dict[str, Any]]) -> dict[str, Any] | None:
    """合并多条 evidence preview，便于 cross-document case 做统一断言。"""
    if not preview_payloads:
        return None
    merged = dict(preview_payloads[0])
    excerpts = [str(item.get("excerpt", "")).strip() for item in preview_payloads if str(item.get("excerpt", "")).strip()]
    if excerpts:
        merged["excerpt"] = "\n".join(excerpts)
    merged["doc_ids"] = [str(item.get("doc_id")) for item in preview_payloads if item.get("doc_id")]
    merged["preview_locators"] = [item.get("preview_locator") for item in preview_payloads if item.get("preview_locator") is not None]
    merged["preview_count"] = len(preview_payloads)
    return merged


def _query_case(client: TestClient, case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """执行单条 case，并在需要时解析全部 evidence 的 preview。"""
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
    if int(case["expected_source_count"]) == 0:
        return payload, None

    preview_payloads: list[dict[str, Any]] = []
    for evidence in payload["evidence"]:
        preview_resp = client.post(
            "/api/kb/preview",
            json={
                "kb_id": KB_ID,
                "evidence_id": evidence["id"],
            },
        )
        assert preview_resp.status_code == 200
        preview_payloads.append(preview_resp.json()["data"])
    return payload, _merge_preview_payloads(preview_payloads)


def test_mixed_batch_cross_document_case_merges_previews(imported_mixed_kb: dict[str, Any]) -> None:
    """跨文档 mixed batch case 应同时命中两份文档并聚合 preview。"""
    client: TestClient = imported_mixed_kb["client"]
    manager: SemirealIndexManager = imported_mixed_kb["manager"]

    payload, preview = _query_case(
        client,
        {
            "case_id": "mixed-cross-doc-direct-assert",
            "question": "Compare the Friday release cutover note and the vendor cutover checklist: who gives the final rollback approval and who signs the checklist before traffic moves to the vendor stack?",
            "expected_source_count": 2,
        },
    )

    answer_lower = payload["answer"].lower()
    assert "platform duty lead" in answer_lower
    assert "customer success lead" in answer_lower
    assert len(payload["sources"]) == 2
    assert len(payload["evidence"]) == 2
    assert preview is not None
    assert preview["preview_count"] == 2
    doc_ids_by_title = {item["title"]: item["doc_id"] for item in manager.documents}
    assert set(preview["doc_ids"]) == {
        doc_ids_by_title["cutover.md"],
        doc_ids_by_title["vendor-cutover.pdf"],
    }
    assert "platform duty lead" in preview["excerpt"].lower()
    assert "customer success lead" in preview["excerpt"].lower()


def test_mixed_batch_import_preserves_tree_and_records_asset_diagnostics(imported_mixed_kb: dict[str, Any]) -> None:
    """验证混合导入能保留目录树，并区分 embedded/standalone 资产。"""
    result = imported_mixed_kb["import_result"]
    manager: SemirealIndexManager = imported_mixed_kb["manager"]
    tmp_path: Path = imported_mixed_kb["tmp_path"]

    assert result["kb_id"] == KB_ID
    assert result["success_count"] == 3
    assert result["failed_count"] == 0
    assert result["empty_count"] == 1
    assert result["indexed_chunks"] == 4
    assert manager.check_index_exists() is True
    assert len(manager.documents) == 4

    indexed_titles = {document["title"] for document in manager.documents}
    assert indexed_titles == {"cutover.md", "vendor-cutover.pdf", "escalation-board.png", "preview-board.png"}

    result_by_name = {item["name"]: item for item in result["file_results"]}
    for name, relative_path in MIXED_IMPORT_PATHS.items():
        item = result_by_name[name]
        assert item["relative_path"] == relative_path
        assert item["folder_path"] == Path(relative_path).parent.as_posix()
        assert Path(item["path"]).is_file()
        assert (tmp_path / "data" / KB_ID / relative_path).is_file()

    markdown_result = result_by_name["cutover.md"]
    embedded_image_result = result_by_name["escalation-board.png"]
    pdf_result = result_by_name["vendor-cutover.pdf"]
    standalone_image_result = result_by_name["preview-board.png"]

    assert markdown_result["status"] == "indexed"
    assert pdf_result["status"] == "indexed"
    assert standalone_image_result["status"] == "indexed"
    assert standalone_image_result["diagnostics"]["asset_registered"] is True
    assert standalone_image_result["diagnostics"]["ocr_status"] == "success"

    assert len(markdown_result["embedded_assets"]) == 1
    embedded_asset = markdown_result["embedded_assets"][0]
    assert embedded_asset["status"] == "ready"
    assert embedded_asset["referenced_path"] == "./images/escalation-board.png"
    assert embedded_asset["resolved_relative_path"] == MIXED_IMPORT_PATHS["escalation-board.png"]

    registered_assets = asset_service.list_assets(KB_ID)
    assert len(registered_assets) == 2
    embedded_asset_record = next(item for item in registered_assets if item["asset_role"] == "embedded")
    standalone_asset_record = next(item for item in registered_assets if item["asset_role"] == "standalone")
    assert embedded_asset_record["ocr_status"] == "success"
    assert embedded_asset_record["indexed_from_ocr"] is True
    assert embedded_asset_record["source_doc_relative_path"] == MIXED_IMPORT_PATHS["cutover.md"]
    assert standalone_asset_record["ocr_status"] == "success"
    assert standalone_asset_record["indexed_from_ocr"] is True
    assert standalone_asset_record["relative_path"] == MIXED_IMPORT_PATHS["preview-board.png"]

    assert embedded_image_result["status"] == "empty"
    assert embedded_image_result["diagnostics"]["skip_standalone_asset"] is True
    assert embedded_image_result["diagnostics"]["ocr_status"] == "skipped"
    assert embedded_image_result["diagnostics"]["asset_registered"] is False

    diagnostics = result["diagnostics"]
    assert diagnostics["embedded_asset_ready_count"] == 1
    assert diagnostics["embedded_asset_missing_count"] == 0
    assert diagnostics["skip_standalone_asset_count"] == 1
    assert diagnostics["ocr_success_count"] == 1
    assert diagnostics["embedded_ocr_success_count"] == 1
    assert diagnostics["indexed_from_ocr_count"] == 1
    assert diagnostics["embedded_indexed_from_ocr_count"] == 1
    assert diagnostics["asset_registered_count"] == 2
    assert diagnostics["empty_reason_counts"]["shadowed_by_embedded_asset"] == 1



def test_mixed_batch_import_persists_display_summary_consistent_with_receipt(imported_mixed_kb: dict[str, Any]) -> None:
    """?? mixed batch ??????? file_results/diagnostics ?????"""
    result = imported_mixed_kb["import_result"]

    summary = result["display_summary"]
    assert summary["source_kind"] == "file_import"
    assert summary["item_label"] == "文件"
    assert summary["total_items"] == 4
    assert summary["indexed_items"] == 3
    assert summary["empty_items"] == 1
    assert summary["failed_items"] == 0
    assert summary["asset_registered_count"] == 2
    assert summary["asset_registered_but_not_indexed_count"] == 0
    assert summary["has_blockers"] is False
    assert summary["has_dependency_issues"] is False
    assert summary["has_warnings"] is True
    assert summary["headline"] == "1 个文件未提取到可索引内容"
    assert summary["top_empty_reasons"] == [{"reason": "shadowed_by_embedded_asset", "count": 1}]
    assert summary["next_actions"] == [
        {
            "action": "review_empty_items",
            "label": "查看 1 个空结果文件",
            "count": 1,
            "top_empty_reasons": [{"reason": "shadowed_by_embedded_asset", "count": 1}],
        }
    ]

    receipt = kb_service.get_latest_import_receipt(KB_ID)
    assert receipt is not None
    assert receipt["kb_id"] == KB_ID
    assert receipt["source_label"] == "文件上传"
    assert receipt["result"]["receipt_id"] == result["receipt_id"]
    assert receipt["result"]["display_summary"] == summary


def test_mixed_batch_reimport_replaces_documents_keeps_asset_registry_stable_and_answers_from_new_content(
    imported_mixed_kb: dict[str, Any]
) -> None:
    """éªè¯ mixed batch éå¯¼å¥ä¼æ¿æ¢ææ¡£ãä¿æèµäº§ç¨³å®ï¼å¹¶è®©é®ç­åå°æ°åå®¹ã"""
    client: TestClient = imported_mixed_kb["client"]
    manager: SemirealIndexManager = imported_mixed_kb["manager"]
    kb_registry: KBRegistry = imported_mixed_kb["kb_registry"]
    source_paths: dict[str, Path] = imported_mixed_kb["source_paths"]
    ocr_text_by_file: dict[str, str] = imported_mixed_kb["ocr_text_by_file"]

    first_docs = _documents_by_title(manager)
    assert set(first_docs) == {"cutover.md", "vendor-cutover.pdf", "escalation-board.png", "preview-board.png"}
    first_doc_ids = {title: item["doc_id"] for title, item in first_docs.items()}
    first_doc_count = kb_registry.get_kb(KB_ID)["doc_count"]
    first_asset_ids = _asset_ids_by_role(KB_ID)
    assert len(manager.docstore.get_all_ref_doc_info()) == 4
    assert first_asset_ids.keys() == {"embedded", "standalone"}

    _rewrite_source_workspace_for_reimport(source_paths, ocr_text_by_file)
    second_result = _import_mixed_batch(source_paths)

    assert second_result["success_count"] == 3
    assert second_result["failed_count"] == 0
    assert second_result["empty_count"] == 1
    assert second_result["indexed_chunks"] == 4
    assert kb_registry.get_kb(KB_ID)["doc_count"] == first_doc_count
    assert len(manager.docstore.get_all_ref_doc_info()) == 4
    assert len(manager.documents) == 4

    second_docs = _documents_by_title(manager)
    second_doc_ids = {title: item["doc_id"] for title, item in second_docs.items()}
    assert set(second_doc_ids) == set(first_doc_ids)
    for title, first_doc_id in first_doc_ids.items():
        assert second_doc_ids[title] != first_doc_id

    assert "incident commander" in second_docs["cutover.md"]["text"].lower()
    assert "platform duty lead" not in second_docs["cutover.md"]["text"].lower()
    assert "service transition manager" in second_docs["vendor-cutover.pdf"]["text"].lower()
    assert "customer success lead" not in second_docs["vendor-cutover.pdf"]["text"].lower()
    assert "scope contract" in second_docs["escalation-board.png"]["text"].lower()
    assert "authorization boundary" in second_docs["escalation-board.png"]["text"].lower()
    assert "asset_id" in second_docs["preview-board.png"]["text"].lower()
    assert "preview_locator" not in second_docs["preview-board.png"]["text"].lower()

    second_asset_ids = _asset_ids_by_role(KB_ID)
    assert second_asset_ids == first_asset_ids
    assets_after_reimport = {item["asset_role"]: item for item in asset_service.list_assets(KB_ID)}
    assert len(assets_after_reimport) == 2
    assert assets_after_reimport["embedded"]["source_doc_relative_path"] == MIXED_IMPORT_PATHS["cutover.md"]
    assert assets_after_reimport["embedded"]["relative_path"] == MIXED_IMPORT_PATHS["escalation-board.png"]
    assert assets_after_reimport["standalone"]["relative_path"] == MIXED_IMPORT_PATHS["preview-board.png"]

    markdown_payload, markdown_preview = _query_case(
        client,
        {
            "case_id": "mixed-reimport-markdown-owner",
            "question": "Who gives the final rollback approval after the deployment coordinator summarizes the evidence?",
            "expected_source_count": 1,
        },
    )
    assert "incident commander" in markdown_payload["answer"].lower()
    assert "platform duty lead" not in markdown_payload["answer"].lower()
    assert markdown_payload["evidence"][0]["doc_id"] == second_doc_ids["cutover.md"]
    assert markdown_preview is not None
    assert markdown_preview["doc_id"] == second_doc_ids["cutover.md"]
    assert "incident commander" in markdown_preview["excerpt"].lower()

    pdf_payload, pdf_preview = _query_case(
        client,
        {
            "case_id": "mixed-reimport-pdf-signer",
            "question": "Who signs the cutover checklist before traffic moves to the vendor stack?",
            "expected_source_count": 1,
        },
    )
    assert "service transition manager" in pdf_payload["answer"].lower()
    assert "customer success lead" not in pdf_payload["answer"].lower()
    assert pdf_payload["evidence"][0]["doc_id"] == second_doc_ids["vendor-cutover.pdf"]
    assert pdf_preview is not None
    assert pdf_preview["doc_id"] == second_doc_ids["vendor-cutover.pdf"]
    assert "service transition manager" in pdf_preview["excerpt"].lower()

    embedded_payload, embedded_preview = _query_case(
        client,
        {
            "case_id": "mixed-reimport-embedded-boundary",
            "question": "On the escalation board revision, what is the only authorization boundary and what remains navigation only?",
            "expected_source_count": 1,
        },
    )
    assert "scope contract" in embedded_payload["answer"].lower()
    assert "knowledge base is the authorization boundary" not in embedded_payload["answer"].lower()
    assert embedded_payload["evidence"][0]["doc_id"] == second_doc_ids["escalation-board.png"]
    assert embedded_preview is not None
    assert embedded_preview["doc_id"] == second_doc_ids["escalation-board.png"]
    assert "scope contract" in embedded_preview["excerpt"].lower()

    standalone_payload, standalone_preview = _query_case(
        client,
        {
            "case_id": "mixed-reimport-standalone-fields",
            "question": "Which two fields must every evidence preview include after the checklist update?",
            "expected_source_count": 1,
        },
    )
    answer_lower = standalone_payload["answer"].lower()
    assert "doc_id" in answer_lower
    assert "asset_id" in answer_lower
    assert "preview_locator" not in answer_lower
    assert standalone_payload["evidence"][0]["doc_id"] == second_doc_ids["preview-board.png"]
    assert standalone_preview is not None
    assert standalone_preview["doc_id"] == second_doc_ids["preview-board.png"]
    assert "asset_id" in standalone_preview["excerpt"].lower()


def test_mixed_batch_semireal_qa_suite(imported_mixed_kb: dict[str, Any]) -> None:
    """验证混合问答回归覆盖多模态与 preview 解析。"""
    client: TestClient = imported_mixed_kb["client"]
    build_query_engine: MagicMock = imported_mixed_kb["build_query_engine"]

    reports = []
    for case in MIXED_CASES:
        payload, preview = _query_case(client, case)
        report = build_chat_case_report(
            case,
            payload,
            expected_kb_ids=[KB_ID],
            expected_scope_type="single_kb",
            expected_effective_scope_type="single_kb",
            expected_default_deny=False,
            expected_isolation_level="physical_isolated",
            preview_payload=preview,
            required_evidence_docs=case["required_evidence_docs"],
            preview_required=int(case["expected_source_count"]) > 0,
        )
        reports.append(report)

    summary = summarize_chat_case_reports(reports)

    assert build_query_engine.call_count == len(MIXED_CASES)
    assert summary["total_cases"] == 8
    assert summary["passed_cases"] == 8
    assert summary["failed_cases"] == 0
    assert summary["pass_rate"] == 1.0
    assert summary["pass_rate_ci95"]["low"] == pytest.approx(0.6755843804891231)
    assert summary["pass_rate_ci95"]["high"] == pytest.approx(1.0)
    assert summary["scope_pass_rate"] == 1.0
    assert summary["average_keypoint_coverage"] == 1.0
    assert summary["total_keypoints"] == 14
    assert summary["matched_keypoints"] == 14
    assert summary["missing_keypoints"] == 0
    assert summary["keypoint_hit_rate"] == 1.0
    assert summary["evidence_expected_cases"] == 7
    assert summary["evidence_hit_cases"] == 7
    assert summary["evidence_hit_rate"] == 1.0
    assert summary["preview_required_cases"] == 7
    assert summary["preview_resolved_cases"] == 7
    assert summary["preview_resolvable_rate"] == 1.0
    assert summary["preview_term_total"] == 13
    assert summary["preview_term_hits"] == 13
    assert summary["preview_term_hit_rate"] == 1.0
    assert summary["source_count_match_rate"] == 1.0
    assert summary["blocked_term_hit_cases"] == 0
    assert summary["forbidden_term_clean_rate"] == 1.0
    assert summary["category_breakdown"] == {
        "cross_document": {
            "count": 2,
            "passed": 2,
            "pass_rate": 1.0,
            "pass_rate_ci95": {"low": pytest.approx(0.34237195288961925), "high": 1.0},
        },
        "embedded_image_fact": {
            "count": 1,
            "passed": 1,
            "pass_rate": 1.0,
            "pass_rate_ci95": {"low": pytest.approx(0.2065432914738929), "high": 1.0},
        },
        "markdown_fact": {
            "count": 1,
            "passed": 1,
            "pass_rate": 1.0,
            "pass_rate_ci95": {"low": pytest.approx(0.2065432914738929), "high": 1.0},
        },
        "markdown_fact_zh": {
            "count": 1,
            "passed": 1,
            "pass_rate": 1.0,
            "pass_rate_ci95": {"low": pytest.approx(0.2065432914738929), "high": 1.0},
        },
        "no_evidence": {
            "count": 1,
            "passed": 1,
            "pass_rate": 1.0,
            "pass_rate_ci95": {"low": pytest.approx(0.2065432914738929), "high": 1.0},
        },
        "pdf_fact": {
            "count": 1,
            "passed": 1,
            "pass_rate": 1.0,
            "pass_rate_ci95": {"low": pytest.approx(0.2065432914738929), "high": 1.0},
        },
        "standalone_image_fact": {
            "count": 1,
            "passed": 1,
            "pass_rate": 1.0,
            "pass_rate_ci95": {"low": pytest.approx(0.2065432914738929), "high": 1.0},
        },
    }
