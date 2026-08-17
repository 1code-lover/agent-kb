"""半真实 PDF 单库问答回归测试：覆盖文字层与扫描件 OCR fallback。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import fitz
import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import kb_service
from server.kb_registry import KBRegistry
from server.readers.pdf_ocr import PDFOCRReader
from server.utils.file import get_kb_data_dir
from tests.api._semireal_chat_support import FakeUploadFile, SemirealIndexManager, SemirealQueryEngine
from tests.api.chat_qa_metrics import build_chat_case_report, summarize_chat_case_reports


FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Verdana.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


def _pick_font(size: int = 28):
    """优先选择支持中文的系统字体，避免扫描 PDF fixture 失真。"""
    from PIL import ImageFont

    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


client = TestClient(app)
KB_ID = "kb-pdf"
PDF_IMPORTS = {
    "scope-manual.pdf": {
        "relative_path": "pdf/contracts/scope-manual.pdf",
        "text": """
        Scope contract for PDF knowledge base queries.
        requested_scope_type must remain single_kb.
        effective_kb_ids must echo the active PDF knowledge base.
        isolation_level remains physical_isolated in the current architecture.
        """,
    },
    "preview-guide.pdf": {
        "relative_path": "pdf/evidence/preview-guide.pdf",
        "text": """
        Evidence preview for PDF imports.
        Every answer should carry doc_id and preview_locator.
        中文补充：每条 PDF 证据回答都必须带上 doc_id 和 preview_locator，方便定位原文片段。
        preview excerpt must resolve back to the original PDF chunk.
        """,
    },
    "folder-boundary.pdf": {
        "relative_path": "pdf/architecture/folder-boundary.pdf",
        "text": """
        Folder boundary note for the PDF suite.
        Folder is an organization object rather than an authorization boundary.
        Knowledge Base remains the range and authorization boundary.
        """,
    },
    "metrics-gate.pdf": {
        "relative_path": "pdf/evaluation/metrics-gate.pdf",
        "text": """
        Metrics gate for PDF suite execution.
        pass_rate scope_pass_rate and evidence_hit_rate should all stay at one point zero.
        preview_resolvable_rate should also remain one point zero for evidence-backed cases.
        """,
    },
    "scan-fallback.pdf": {
        "relative_path": "pdf/ocr/scan-fallback.pdf",
        "source_kind": "scanned_pdf",
        "image_lines": [
            "交接窗口 handover window",
            "扫描 PDF 需要 OCR fallback",
            "merge every predict batch 后写回索引",
        ],
        "ocr_text": """
        handover window 扫描页没有文字层时，OCR fallback must merge every predict batch for the same page.
        中文流程说明也要写回当前知识库，避免导入后只剩图片像素。
        Scanned PDF content should still become searchable evidence in the active knowledge base.
        """,
    },
}
PDF_CASES = [
    {
        "case_id": "pdf-scope-contract",
        "category": "fact",
        "question": "In the scope manual, what should requested_scope_type remain and what should effective_kb_ids do?",
        "expected_doc": "scope-manual.pdf",
        "expected_keypoints": ["requested_scope_type must remain single_kb", "effective_kb_ids must echo the active PDF knowledge base"],
        "must_not_contain": ["kb-other", "cross_kb"],
        "preview_terms": ["requested_scope_type", "effective_kb_ids"],
        "expected_source_count": 1,
    },
    {
        "case_id": "pdf-preview-contract",
        "category": "policy",
        "question": "According to the preview guide, what evidence fields should every answer carry?",
        "expected_doc": "preview-guide.pdf",
        "expected_keypoints": ["Every answer should carry doc_id and preview_locator", "preview excerpt must resolve back to the original PDF chunk"],
        "must_not_contain": ["fabricated reference"],
        "preview_terms": ["doc_id", "preview_locator"],
        "expected_source_count": 1,
    },
    {
        "case_id": "pdf-folder-boundary",
        "category": "architecture",
        "question": "For the folder boundary note, is folder the authorization boundary or only an organization object?",
        "expected_doc": "folder-boundary.pdf",
        "expected_keypoints": ["Folder is an organization object rather than an authorization boundary", "Knowledge Base remains the range and authorization boundary"],
        "must_not_contain": ["folder is the authorization boundary"],
        "preview_terms": ["organization object", "authorization boundary"],
        "expected_source_count": 1,
    },
    {
        "case_id": "pdf-metrics-gate",
        "category": "metrics",
        "question": "What metrics does the metrics gate expect to stay at one point zero?",
        "expected_doc": "metrics-gate.pdf",
        "expected_keypoints": ["pass_rate scope_pass_rate and evidence_hit_rate should all stay at one point zero", "preview_resolvable_rate should also remain one point zero"],
        "must_not_contain": ["zero evidence"],
        "preview_terms": ["pass_rate", "preview_resolvable_rate"],
        "expected_source_count": 1,
    },
    {
        "case_id": "pdf-scan-fallback",
        "category": "ocr-fallback",
        "question": "For the handover window scanned PDF fixture, what must OCR fallback do and what should the scanned content become?",
        "expected_doc": "scan-fallback.pdf",
        "expected_keypoints": [
            "handover window 扫描页没有文字层时，OCR fallback must merge every predict batch for the same page",
            "中文流程说明也要写回当前知识库，避免导入后只剩图片像素",
            "Scanned PDF content should still become searchable evidence in the active knowledge base",
        ],
        "must_not_contain": ["No confirmable information is available"],
        "preview_terms": ["handover window", "当前知识库", "searchable evidence"],
        "expected_source_count": 1,
    },
    {
        "case_id": "pdf-preview-contract-zh",
        "category": "policy",
        "question": "根据 preview guide，每条 PDF 回答都必须携带哪两个字段？",
        "expected_doc": "preview-guide.pdf",
        "expected_keypoints": ["doc_id", "preview_locator"],
        "must_not_contain": ["fabricated reference"],
        "preview_terms": ["doc_id", "preview_locator"],
        "expected_source_count": 1,
    },
    {
        "case_id": "pdf-no-evidence",
        "category": "no-evidence",
        "question": "Which document defines tenant shard checksum escrow and namespace pinning barriers?",
        "expected_doc": None,
        "expected_keypoints": ["No confirmable information is available in the current knowledge base."],
        "must_not_contain": ["scope-manual.pdf", "folder-boundary.pdf"],
        "preview_terms": [],
        "expected_source_count": 0,
    },
]


def _create_text_pdf(path: Path, text: str) -> None:
    """生成带真实文字层的 PDF 文件。"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(48, 48, 560, 780), text.strip(), fontsize=11)
    doc.save(path)
    doc.close()


def _create_scanned_pdf(path: Path, lines: list[str]) -> None:
    """生成只包含图片页的扫描件 PDF 文件。"""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1600, 1200), color="white")
    draw = ImageDraw.Draw(image)
    font = _pick_font(28)
    y = 120
    for line in lines:
        draw.text((96, y), line, fill="black", font=font)
        y += 72

    image_path = path.with_suffix(".png")
    image.save(image_path)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(36, 36, 559, 806), filename=str(image_path))
    doc.save(path)
    doc.close()
    image_path.unlink(missing_ok=True)


class PDFSemirealIndexManager(SemirealIndexManager):
    """使用真实 PDF reader 的半真实索引管理器。"""

    def load_files(self, paths, chunk_size: int, chunk_overlap: int, kb_id: str | None = None, persist: bool = False):
        reader = PDFOCRReader()
        nodes = []
        input_text_chars = 0
        for raw_path in paths:
            path = Path(raw_path).resolve()
            docs = reader.load_data(str(path))
            for doc in docs:
                source_kind = str(PDF_IMPORTS.get(path.name, {}).get("source_kind") or "text_layer")
                node = self.register_text_document(
                    path=path,
                    text=str(doc.text),
                    kb_id=kb_id,
                    relative_path=path.relative_to(self.kb_dir).as_posix(),
                    title=path.name,
                    page_label=str((getattr(doc, "metadata", {}) or {}).get("page_label") or "1"),
                    extra_metadata={
                        "source_type": "pdf_ocr_fallback" if source_kind == "scanned_pdf" else "pdf_text_layer",
                        "mime_type": "application/pdf",
                    },
                )
                nodes.append(node)
                input_text_chars += len(str(doc.text))
        self._record_ingestion_diagnostics(
            document_count=len(nodes),
            input_text_chars=input_text_chars,
            node_count=len(nodes),
        )
        return nodes


@pytest.fixture(autouse=True)
def _reset_service_state():
    yield
    kb_service._registry = None


@pytest.fixture
def pdf_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    import api.services.chat_service as chat_service

    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    kb_service._registry = registry
    registry.create_kb(KB_ID, "PDF KB")

    manager = PDFSemirealIndexManager(kb_id=KB_ID, kb_dir=get_kb_data_dir(KB_ID, create=True))

    def fake_ocr_pdf(self, file_path: str) -> str:
        payload = PDF_IMPORTS.get(Path(file_path).name, {})
        if payload.get("source_kind") == "scanned_pdf":
            return str(payload["ocr_text"]).strip()
        raise AssertionError(f"Unexpected OCR fallback for {Path(file_path).name}")

    monkeypatch.setattr(PDFOCRReader, "_ocr_pdf", fake_ocr_pdf)
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

    return {
        "registry": registry,
        "manager": manager,
        "build_query_engine": build_query_engine,
        "tmp_path": tmp_path,
    }


@pytest.fixture
def imported_pdf_kb(pdf_runtime: dict[str, object]):
    uploads = []
    relative_paths = []
    source_dir = Path(pdf_runtime["tmp_path"]) / "pdf-fixtures"
    source_dir.mkdir(parents=True, exist_ok=True)

    for name, payload in PDF_IMPORTS.items():
        source_path = source_dir / name
        if payload.get("source_kind") == "scanned_pdf":
            _create_scanned_pdf(source_path, list(payload["image_lines"]))
        else:
            _create_text_pdf(source_path, str(payload["text"]))
        uploads.append(
            FakeUploadFile(
                filename=name,
                content=source_path.read_bytes(),
                content_type="application/pdf",
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

    pdf_runtime["import_result"] = result
    pdf_runtime["relative_paths"] = relative_paths
    return pdf_runtime



def test_generated_scan_fallback_pdf_has_no_text_layer(tmp_path: Path) -> None:
    """确保扫描 PDF fixture 的前提成立：原始 PDF 没有可提取文字层。"""
    payload = PDF_IMPORTS["scan-fallback.pdf"]
    source_path = tmp_path / "scan-fallback.pdf"
    _create_scanned_pdf(source_path, list(payload["image_lines"]))

    doc = fitz.open(source_path)
    try:
        extracted = "\n".join(page.get_text("text") for page in doc).strip()
    finally:
        doc.close()

    assert extracted == ""

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


def test_pdf_semireal_case_matrix_is_broad_enough() -> None:
    """确保 PDF 半真实层覆盖事实、策略、架构、指标与拒答五类场景。"""
    categories = {str(case["category"]) for case in PDF_CASES}
    assert {"fact", "policy", "architecture", "metrics", "ocr-fallback", "no-evidence"}.issubset(categories)
    assert len(PDF_CASES) >= 6


def test_pdf_semireal_import_preserves_tree_and_indexes_docs(imported_pdf_kb: dict[str, object]) -> None:
    """验证 PDF 导入保留目录树，并进入索引。"""
    result = imported_pdf_kb["import_result"]
    manager: PDFSemirealIndexManager = imported_pdf_kb["manager"]
    tmp_path: Path = imported_pdf_kb["tmp_path"]

    assert result["kb_id"] == KB_ID
    assert result["success_count"] == len(PDF_IMPORTS)
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert len(result["file_results"]) == len(PDF_IMPORTS)
    assert manager.check_index_exists() is True
    assert len(manager.documents) == len(PDF_IMPORTS)

    indexed_titles = {document["title"] for document in manager.documents}
    assert indexed_titles == set(PDF_IMPORTS)
    document_by_title = {document["title"]: document for document in manager.documents}

    result_by_name = {item["name"]: item for item in result["file_results"]}
    for name, payload in PDF_IMPORTS.items():
        relative_path = str(payload["relative_path"])
        item = result_by_name[name]
        assert item["status"] == "indexed"
        assert item["relative_path"] == relative_path
        assert item["folder_path"] == Path(relative_path).parent.as_posix()
        assert Path(item["path"]).is_file()
        assert (tmp_path / "data" / KB_ID / relative_path).is_file()
        expected_source_type = "pdf_ocr_fallback" if payload.get("source_kind") == "scanned_pdf" else "pdf_text_layer"
        assert document_by_title[name]["node"].metadata["source_type"] == expected_source_type


@pytest.mark.parametrize("case", PDF_CASES, ids=[case["case_id"] for case in PDF_CASES])
def test_chat_pdf_semireal_contract(case: dict[str, object], imported_pdf_kb: dict[str, object]) -> None:
    """逐条验证 PDF 单库问答、证据与 preview 契约。"""
    build_query_engine: MagicMock = imported_pdf_kb["build_query_engine"]
    payload, preview = _query_case(case)

    assert payload["requested_scope_type"] == "single_kb"
    assert payload["requested_kb_ids"] == [KB_ID]
    assert payload["effective_scope_type"] == "single_kb"
    assert payload["effective_kb_ids"] == [KB_ID]
    assert payload["is_default_deny_applied"] is False
    assert payload["isolation_level"] == "physical_isolated"

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
        expected_isolation_level="physical_isolated",
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



def test_chat_pdf_semireal_suite_metrics(imported_pdf_kb: dict[str, object]) -> None:
    """PDF 半真实层需要输出 suite 级指标，用于测试报告聚合。"""
    build_query_engine: MagicMock = imported_pdf_kb["build_query_engine"]
    reports = []
    for case in PDF_CASES:
        payload, preview = _query_case(case)
        reports.append(
            build_chat_case_report(
                case,
                payload,
                expected_kb_ids=[KB_ID],
                expected_isolation_level="physical_isolated",
                preview_payload=preview,
            )
        )

    summary = summarize_chat_case_reports(reports)
    assert summary["total_cases"] == len(PDF_CASES)
    assert summary["passed_cases"] == len(PDF_CASES)
    assert summary["failed_cases"] == 0
    assert summary["pass_rate"] == 1.0
    assert summary["scope_pass_rate"] == 1.0
    assert summary["average_keypoint_coverage"] == 1.0
    assert summary["evidence_hit_rate"] == 1.0
    assert summary["preview_resolvable_rate"] == 1.0
    assert summary["source_count_match_rate"] == 1.0
    assert summary["forbidden_term_clean_rate"] == 1.0
    assert summary["category_breakdown"]["no-evidence"]["count"] == 1
    assert build_query_engine.call_count == len(PDF_CASES)
