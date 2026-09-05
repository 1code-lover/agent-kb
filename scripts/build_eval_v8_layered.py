from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "rag_quality"
V6_CASES_PATH = FIXTURE_ROOT / "eval_v6" / "cases.json"
V6_SCHEMA_PATH = FIXTURE_ROOT / "eval_v6" / "schema.json"
V7_CASES_PATH = FIXTURE_ROOT / "eval_v7" / "cases.json"
V7_SCHEMA_PATH = FIXTURE_ROOT / "eval_v7" / "schema.json"
V8_MAIN_DIR = FIXTURE_ROOT / "eval_v8_main"
V8_HARD_DIR = FIXTURE_ROOT / "eval_v8_hard"
LAYERED_SUITE_PATH = FIXTURE_ROOT / "eval_layered_suite.json"

DATASET_MAIN = "local_multi_kb_eval_v8_layered_main"
DATASET_HARD = "local_multi_kb_eval_v8_layered_hard"

MARKDOWN_KB_ID = "eval-kb-markdown"
PDF_KB_ID = "eval-kb-pdf"
IMAGE_KB_ID = "eval-kb-image"

REQUIRED_FIELDS = [
    "case_id",
    "dataset",
    "kb_id",
    "question",
    "source_doc",
    "source_locator",
    "expected_scope_type",
    "expected_isolation_level",
    "modality",
    "answer_style",
    "difficulty",
    "category",
    "answerable",
    "expected_keypoints",
    "required_evidence_docs",
    "expected_source_count",
    "preview_required",
    "preview_terms",
    "forbidden_terms",
    "judge_focus",
]

ANSWER_JUDGE_FOCUS = [
    "factual_accuracy",
    "completeness",
    "citation_accuracy",
    "groundedness",
]
REFUSAL_JUDGE_FOCUS = ["refusal_correctness", "groundedness"]

BASE_MARKDOWN_DOCS = {
    "scope-contract.md",
    "evidence-preview.md",
    "refusal-guideline.md",
    "evaluation-metrics.md",
    "folder-boundary.md",
    "ingestion-priority.md",
    "suite-metrics-gate.md",
}
MARKDOWN_EXTRA_DOCS = {
    "cutover-approval.md",
    "handover-sla.md",
    "workflow-boundary.md",
    "utf8-boundary.md",
    "long-cutover-handbook.md",
    "refusal-wording-note.md",
    "scope-refusal-bridge.md",
}
BASE_PDF_DOCS = {
    "scope-manual.pdf",
    "preview-guide.pdf",
    "folder-boundary.pdf",
    "metrics-gate.pdf",
    "ocr-readiness.pdf",
    "scan-fallback.pdf",
    "embedding-gap.pdf",
    "zero-text-diagnostic.pdf",
    "refusal-rule.pdf",
}
PDF_EXTRA_DOCS = {
    "long-cutover-handbook.pdf",
    "release-checklist-business.pdf",
    "war-room-handover-business.pdf",
    "scope-refusal-bridge.pdf",
}
BASE_IMAGE_DOCS = {
    "scope-board.png",
    "folder-board.png",
    "evidence-board.png",
    "metrics-board.png",
    "noisy-policy-board.png",
    "weak-no-text-board.png",
    "weak-failed-board.png",
    "weak-dependency-board.png",
}
IMAGE_EXTRA_DOCS = {
    "long-cutover-handbook-board.png",
    "approval-whiteboard-business.png",
    "escalation-whiteboard-business.png",
    "boundary-knowledge-board.png",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



def _source_locator_for(doc_name: str) -> str:
    base = "tests/api/chat_eval_runner.py"
    if doc_name in BASE_MARKDOWN_DOCS:
        return f"{base}::BASE_MARKDOWN_IMPORTS['{doc_name}']"
    if doc_name in MARKDOWN_EXTRA_DOCS:
        return f"{base}::MARKDOWN_EXTRA_IMPORTS['{doc_name}']"
    if doc_name in BASE_PDF_DOCS:
        return f"{base}::BASE_PDF_IMPORTS['{doc_name}']"
    if doc_name in PDF_EXTRA_DOCS:
        return f"{base}::PDF_EXTRA_IMPORTS['{doc_name}']"
    if doc_name in BASE_IMAGE_DOCS:
        return f"{base}::BASE_IMAGE_IMPORTS['{doc_name}']"
    if doc_name in IMAGE_EXTRA_DOCS:
        return f"{base}::IMAGE_EXTRA_IMPORTS['{doc_name}']"
    raise KeyError(f"Unsupported semireal support document: {doc_name}")



def _kb_id_for_modality(modality: str) -> str:
    mapping = {
        "markdown": MARKDOWN_KB_ID,
        "pdf": PDF_KB_ID,
        "image_ocr": IMAGE_KB_ID,
    }
    return mapping[modality]



def _build_case(
    *,
    dataset: str,
    case_id: str,
    modality: str,
    question: str,
    answer_style: str,
    difficulty: str,
    category: str,
    answerable: bool,
    expected_keypoints: list[str],
    forbidden_terms: list[str],
    source_doc: str | None = None,
    source_locator: str | None = None,
    required_evidence_docs: list[str] | None = None,
    preview_terms: list[str] | None = None,
    seed_docs: list[str] | None = None,
) -> dict[str, Any]:
    required_docs = list(required_evidence_docs or ([] if not source_doc else [source_doc]))
    locator = source_locator if source_locator is not None else (_source_locator_for(source_doc) if source_doc else None)
    case: dict[str, Any] = {
        "dataset": dataset,
        "expected_scope_type": "single_kb",
        "expected_isolation_level": "physical_isolated",
        "case_id": case_id,
        "kb_id": _kb_id_for_modality(modality),
        "question": question,
        "source_doc": source_doc,
        "source_locator": locator,
        "modality": modality,
        "answer_style": answer_style,
        "difficulty": difficulty,
        "category": category,
        "answerable": answerable,
        "expected_keypoints": list(expected_keypoints),
        "required_evidence_docs": required_docs,
        "expected_source_count": len(required_docs),
        "preview_required": bool(answerable),
        "preview_terms": list(preview_terms or ([] if not answerable else expected_keypoints[:2])),
        "forbidden_terms": list(forbidden_terms),
        "judge_focus": ANSWER_JUDGE_FOCUS if answerable else REFUSAL_JUDGE_FOCUS,
    }
    if seed_docs:
        case["seed_docs"] = list(seed_docs)
    return case


MAIN_ADDITIONS: list[dict[str, Any]] = [
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-md-001",
        modality="markdown",
        question="In the long-form cutover handbook, what live final approval checkpoint should be used, and which retired rehearsal time must be ignored?",
        source_doc="long-cutover-handbook.md",
        answer_style="comparison",
        difficulty="complex",
        category="long_document",
        answerable=True,
        expected_keypoints=["21:40 Beijing time", "18:00"],
        preview_terms=["21:40 Beijing time", "18:00"],
        forbidden_terms=["21:55 Beijing time"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-md-002",
        modality="markdown",
        question="Compare the payroll cutover approval matrix with the long-form handbook: what is the checklist sign deadline, and which field must stay aligned with the cited paragraph?",
        source_doc="cutover-approval.md",
        required_evidence_docs=["cutover-approval.md", "long-cutover-handbook.md"],
        answer_style="comparison",
        difficulty="complex",
        category="cross_document",
        answerable=True,
        expected_keypoints=["22:30 Beijing time", "preview_locator"],
        preview_terms=["22:30 Beijing time", "preview_locator"],
        forbidden_terms=["5 minutes"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-md-003",
        modality="markdown",
        question="Does the current knowledge base mention any plasma escrow ledger or shard witness?",
        answer_style="refusal",
        difficulty="medium",
        category="hard_refusal",
        answerable=False,
        expected_keypoints=["No confirmable information", "current knowledge base"],
        forbidden_terms=["plasma escrow"],
        seed_docs=["long-cutover-handbook.md", "cutover-approval.md"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-md-004",
        modality="markdown",
        question="Under the single KB scope contract, can the effective scope expand beyond the requested KB, and which two id fields should stay aligned with the request?",
        source_doc="scope-contract.md",
        answer_style="policy",
        difficulty="medium",
        category="scope_contract",
        answerable=True,
        expected_keypoints=["requested_kb_ids", "effective_kb_ids", "explicitly requested knowledge base"],
        preview_terms=["requested_kb_ids", "effective_kb_ids"],
        forbidden_terms=["multi_kb"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-pdf-001",
        modality="pdf",
        question="In the PDF long-form handbook, what live checkpoint time should be used and which retired rehearsal time should not be used?",
        source_doc="long-cutover-handbook.pdf",
        answer_style="comparison",
        difficulty="complex",
        category="long_document",
        answerable=True,
        expected_keypoints=["21:55 Beijing time", "18:30"],
        preview_terms=["21:55 Beijing time", "18:30"],
        forbidden_terms=["23:00 Beijing time"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-pdf-002",
        modality="pdf",
        question="Compare the PDF release checklist with the PDF long-form handbook: who owns final sign-off, and which field must stay aligned with the cited paragraph?",
        source_doc="release-checklist-business.pdf",
        required_evidence_docs=["release-checklist-business.pdf", "long-cutover-handbook.pdf"],
        answer_style="comparison",
        difficulty="complex",
        category="cross_document",
        answerable=True,
        expected_keypoints=["Chen Yu", "preview_locator"],
        preview_terms=["Chen Yu", "preview_locator"],
        forbidden_terms=["10 minutes"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-pdf-003",
        modality="pdf",
        question="Does the current PDF knowledge base mention any zephyr lattice mirror or blue token?",
        answer_style="refusal",
        difficulty="medium",
        category="hard_refusal",
        answerable=False,
        expected_keypoints=["No confirmable information", "current knowledge base"],
        forbidden_terms=["zephyr lattice mirror", "blue token"],
        seed_docs=["release-checklist-business.pdf", "long-cutover-handbook.pdf"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-pdf-004",
        modality="pdf",
        question="In the PDF scope contract, which response field should echo the active PDF knowledge base, and what scope type must remain in force?",
        source_doc="scope-manual.pdf",
        answer_style="policy",
        difficulty="medium",
        category="scope_contract",
        answerable=True,
        expected_keypoints=["effective_kb_ids", "single_kb"],
        preview_terms=["effective_kb_ids", "single_kb"],
        forbidden_terms=["multi_kb"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-img-001",
        modality="image_ocr",
        question="On the long OCR handbook board, what live checkpoint should be used and which retired rehearsal should be ignored?",
        source_doc="long-cutover-handbook-board.png",
        answer_style="comparison",
        difficulty="complex",
        category="long_document",
        answerable=True,
        expected_keypoints=["21:50 Beijing time", "18:20"],
        preview_terms=["21:50 Beijing time", "18:20"],
        forbidden_terms=["22:45 Beijing time"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-img-002",
        modality="image_ocr",
        question="Compare the approval whiteboard and the escalation whiteboard: who is the final approver, and to whom within how many minutes do P1 issues escalate?",
        source_doc="approval-whiteboard-business.png",
        required_evidence_docs=["approval-whiteboard-business.png", "escalation-whiteboard-business.png"],
        answer_style="comparison",
        difficulty="complex",
        category="cross_document",
        answerable=True,
        expected_keypoints=["Zhao Lin", "Liu Chang", "10 minutes"],
        preview_terms=["Zhao Lin", "Liu Chang", "10 minutes"],
        forbidden_terms=["Sun Kai"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-img-003",
        modality="image_ocr",
        question="Does the current image knowledge base mention any zephyr lattice mirror or blue token?",
        answer_style="refusal",
        difficulty="medium",
        category="hard_refusal",
        answerable=False,
        expected_keypoints=["No confirmable information", "current knowledge base"],
        forbidden_terms=["zephyr lattice mirror", "blue token"],
        seed_docs=["approval-whiteboard-business.png", "long-cutover-handbook-board.png"],
    ),
    (
        _build_case(
            dataset=DATASET_MAIN,
            case_id="eval-v8-main-img-004",
            modality="image_ocr",
            question="On the scope board, which field should echo the declared image knowledge base, and what remains the authorization boundary for image answers?",
            source_doc="scope-board.png",
            answer_style="policy",
            difficulty="medium",
            category="scope_contract",
            answerable=True,
            expected_keypoints=["effective_kb_ids", "Knowledge Base"],
            preview_terms=["effective_kb_ids", "Knowledge Base"],
            forbidden_terms=["folder is the authorization boundary"],
        )
        | {"expected_source_count": 2}
    ),
    (
        _build_case(
            dataset=DATASET_MAIN,
            case_id="eval-v8-main-md-019",
            modality="markdown",
            question="According to the refusal wording note, if the current knowledge base has no confirmable evidence, what should the assistant say and what must it avoid doing?",
            source_doc="refusal-wording-note.md",
            answer_style="policy",
            difficulty="simple",
            category="scope_contract",
            answerable=True,
            expected_keypoints=[
                "No confirmable information",
                "current knowledge base",
                "must not fabricate from outside memory",
            ],
            preview_terms=["No confirmable information", "current knowledge base"],
            forbidden_terms=["guess from outside memory"],
        )
        | {"expected_source_count": 3}
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-pdf-019",
        modality="pdf",
        question="In the PDF titled 'Scope refusal bridge', repeat the exact phrase for what the assistant must not do when the current PDF knowledge base has no confirmable evidence.",
        source_doc="scope-refusal-bridge.pdf",
        answer_style="policy",
        difficulty="medium",
        category="scope_contract",
        answerable=True,
        expected_keypoints=["must not fabricate from outside memory"],
        preview_terms=["outside memory"],
        forbidden_terms=["fabricate from memory"],
    ),
    _build_case(
        dataset=DATASET_MAIN,
        case_id="eval-v8-main-img-019",
        modality="image_ocr",
        question="Summarize the OCR boundary knowledge board in one sentence: what is not the authorization boundary, and what remains it for image answers?",
        source_doc="boundary-knowledge-board.png",
        answer_style="summary",
        difficulty="complex",
        category="process_boundary",
        answerable=True,
        expected_keypoints=["not an authorization boundary", "knowledge base", "authorization boundary"],
        preview_terms=["knowledge base", "authorization boundary"],
        forbidden_terms=["folder path is the authorization boundary"],
    ),
]


HARD_CASES: list[dict[str, Any]] = [
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-001",
        modality="markdown",
        question="In the payroll cutover approval matrix, who is the final approver and who is the business confirmer?",
        source_doc="cutover-approval.md",
        answer_style="comparison",
        difficulty="medium",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["Li Qing", "Zhou Yu"],
        preview_terms=["Li Qing", "Zhou Yu"],
        forbidden_terms=["Wang Lei"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-002",
        modality="markdown",
        question="Across the approval matrix and the handover SLA, which value is a sign deadline and which is an escalation interval?",
        source_doc="cutover-approval.md",
        required_evidence_docs=["cutover-approval.md", "handover-sla.md"],
        answer_style="comparison",
        difficulty="complex",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["22:30 Beijing time", "15 minutes"],
        preview_terms=["22:30 Beijing time", "15 minutes"],
        forbidden_terms=["5 minutes"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-001",
        modality="pdf",
        question="In the PDF release checklist, who is the final sign-off owner and who is the rollback owner?",
        source_doc="release-checklist-business.pdf",
        answer_style="comparison",
        difficulty="medium",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["Chen Yu", "Xu Nan"],
        preview_terms=["Chen Yu", "Xu Nan"],
        forbidden_terms=["Zhao Lin"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-002",
        modality="pdf",
        question="Across the PDF release checklist and the war-room handover sheet, which value is the operator checklist closing time and which is the Sev1 escalation interval?",
        source_doc="release-checklist-business.pdf",
        required_evidence_docs=["release-checklist-business.pdf", "war-room-handover-business.pdf"],
        answer_style="comparison",
        difficulty="complex",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["23:00 Beijing time", "10 minutes"],
        preview_terms=["23:00 Beijing time", "10 minutes"],
        forbidden_terms=["21:55 Beijing time"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-001",
        modality="image_ocr",
        question="On the approval whiteboard, who is the final approver and who is the rollback owner?",
        source_doc="approval-whiteboard-business.png",
        answer_style="comparison",
        difficulty="medium",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["Zhao Lin", "Sun Kai"],
        preview_terms=["Zhao Lin", "Sun Kai"],
        forbidden_terms=["Liu Chang"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-002",
        modality="image_ocr",
        question="Across the long OCR handbook board and the escalation whiteboard, which value is the live checkpoint time and which is the P1 escalation interval?",
        source_doc="long-cutover-handbook-board.png",
        required_evidence_docs=["long-cutover-handbook-board.png", "escalation-whiteboard-business.png"],
        answer_style="comparison",
        difficulty="complex",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["21:50 Beijing time", "10 minutes"],
        preview_terms=["21:50 Beijing time", "10 minutes"],
        forbidden_terms=["18:20"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-003",
        modality="markdown",
        question="In the long-form handbook, what is the live final approval checkpoint and which retired rehearsal time must not be used?",
        source_doc="long-cutover-handbook.md",
        answer_style="comparison",
        difficulty="complex",
        category="stale_version_conflict",
        answerable=True,
        expected_keypoints=["21:40 Beijing time", "18:00"],
        preview_terms=["21:40 Beijing time", "18:00"],
        forbidden_terms=["22:30 Beijing time"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-004",
        modality="markdown",
        question="When answering from the long-form handbook, should the retired rehearsal time or the live checkpoint be used?",
        source_doc="long-cutover-handbook.md",
        answer_style="policy",
        difficulty="complex",
        category="stale_version_conflict",
        answerable=True,
        expected_keypoints=["21:40 Beijing time", "should not be used for the live answer"],
        preview_terms=["21:40 Beijing time", "18:00"],
        forbidden_terms=["18:00 should be used"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-003",
        modality="pdf",
        question="In the PDF long-form handbook, what is the live checkpoint time and which retired rehearsal time must not be used?",
        source_doc="long-cutover-handbook.pdf",
        answer_style="comparison",
        difficulty="complex",
        category="stale_version_conflict",
        answerable=True,
        expected_keypoints=["21:55 Beijing time", "18:30"],
        preview_terms=["21:55 Beijing time", "18:30"],
        forbidden_terms=["23:00 Beijing time"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-004",
        modality="pdf",
        question="Which time is retired and which is live in the PDF long-form handbook?",
        source_doc="long-cutover-handbook.pdf",
        answer_style="comparison",
        difficulty="complex",
        category="stale_version_conflict",
        answerable=True,
        expected_keypoints=["18:30", "21:55 Beijing time"],
        preview_terms=["18:30", "21:55 Beijing time"],
        forbidden_terms=["18:30 should be used for the live answer"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-003",
        modality="image_ocr",
        question="On the long OCR handbook board, what live checkpoint should be used and which retired rehearsal should be ignored?",
        source_doc="long-cutover-handbook-board.png",
        answer_style="comparison",
        difficulty="complex",
        category="stale_version_conflict",
        answerable=True,
        expected_keypoints=["21:50 Beijing time", "18:20"],
        preview_terms=["21:50 Beijing time", "18:20"],
        forbidden_terms=["22:45 Beijing time"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-004",
        modality="image_ocr",
        question="Which time is retired and which is live on the long OCR handbook board?",
        source_doc="long-cutover-handbook-board.png",
        answer_style="comparison",
        difficulty="complex",
        category="stale_version_conflict",
        answerable=True,
        expected_keypoints=["18:20", "21:50 Beijing time"],
        preview_terms=["18:20", "21:50 Beijing time"],
        forbidden_terms=["18:20 should be used for the live answer"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-005",
        modality="markdown",
        question="According to the workflow boundary note, which two fields must an evidence preview include, and what remains the access-control boundary?",
        source_doc="workflow-boundary.md",
        answer_style="policy",
        difficulty="complex",
        category="chunk_boundary",
        answerable=True,
        expected_keypoints=["doc_id", "preview_locator", "knowledge base level"],
        preview_terms=["doc_id", "preview_locator", "knowledge base level"],
        forbidden_terms=["folder path is the authorization boundary"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-006",
        modality="markdown",
        question="In the long-form handbook, what field must stay aligned with the cited paragraph, and what live checkpoint closes later in the document?",
        source_doc="long-cutover-handbook.md",
        answer_style="comparison",
        difficulty="complex",
        category="chunk_boundary",
        answerable=True,
        expected_keypoints=["preview_locator", "21:40 Beijing time"],
        preview_terms=["preview_locator", "21:40 Beijing time"],
        forbidden_terms=["18:00"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-005",
        modality="pdf",
        question="From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?",
        source_doc="preview-guide.pdf",
        answer_style="policy",
        difficulty="complex",
        category="chunk_boundary",
        answerable=True,
        expected_keypoints=["doc_id", "preview_locator", "original PDF chunk"],
        preview_terms=["doc_id", "preview_locator", "original PDF chunk"],
        forbidden_terms=["room number"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-006",
        modality="pdf",
        question="In the PDF long-form handbook, what field must stay aligned and what live checkpoint time closes later in the document?",
        source_doc="long-cutover-handbook.pdf",
        answer_style="comparison",
        difficulty="complex",
        category="chunk_boundary",
        answerable=True,
        expected_keypoints=["preview_locator", "21:55 Beijing time"],
        preview_terms=["preview_locator", "21:55 Beijing time"],
        forbidden_terms=["18:30"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-005",
        modality="image_ocr",
        question="From the evidence board, what fields should evidence output include, and what else must be resolvable for OCR-derived assets?",
        source_doc="evidence-board.png",
        answer_style="policy",
        difficulty="complex",
        category="chunk_boundary",
        answerable=True,
        expected_keypoints=["doc_id", "preview_locator", "excerpt"],
        preview_terms=["doc_id", "preview_locator", "excerpt"],
        forbidden_terms=["checksum_id"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-006",
        modality="image_ocr",
        question="On the long OCR handbook board, what must stay aligned and what live checkpoint time is listed?",
        source_doc="long-cutover-handbook-board.png",
        answer_style="comparison",
        difficulty="complex",
        category="chunk_boundary",
        answerable=True,
        expected_keypoints=["preview_locator", "21:50 Beijing time"],
        preview_terms=["preview_locator", "21:50 Beijing time"],
        forbidden_terms=["18:20"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-007",
        modality="markdown",
        question="In the workflow note, what is the real permission wall, and what thing is only an internal filing path?",
        source_doc="workflow-boundary.md",
        answer_style="policy",
        difficulty="medium",
        category="paraphrase_rewrite",
        answerable=True,
        expected_keypoints=["knowledge base level", "cutover/runbook/"],
        preview_terms=["knowledge base level", "cutover/runbook/"],
        forbidden_terms=["folder path is the authorization boundary"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-008",
        modality="markdown",
        question="In the evidence preview contract, what is the jump-back pointer field that lets the frontend return to the origin document?",
        source_doc="evidence-preview.md",
        answer_style="policy",
        difficulty="medium",
        category="paraphrase_rewrite",
        answerable=True,
        expected_keypoints=["preview_locator"],
        preview_terms=["preview_locator"],
        forbidden_terms=["checksum_id"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-007",
        modality="pdf",
        question="In the PDF scope refusal bridge, paraphrase what the assistant must not do when the current PDF knowledge base has no confirmable evidence.",
        source_doc="scope-refusal-bridge.pdf",
        required_evidence_docs=["scope-refusal-bridge.pdf"],
        answer_style="policy",
        difficulty="medium",
        category="paraphrase_rewrite",
        answerable=True,
        expected_keypoints=["must not fabricate from outside memory", "current PDF knowledge base"],
        preview_terms=["outside memory", "current PDF knowledge base"],
        forbidden_terms=["outside memory may be used"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-008",
        modality="pdf",
        question="In the PDF preview guide, what jump-back pointer should accompany doc_id so the UI can locate the source snippet?",
        source_doc="preview-guide.pdf",
        answer_style="policy",
        difficulty="medium",
        category="paraphrase_rewrite",
        answerable=True,
        expected_keypoints=["preview_locator"],
        preview_terms=["preview_locator"],
        forbidden_terms=["checksum_id"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-007",
        modality="image_ocr",
        question="On the folder board, what is the real permission wall for image OCR answers?",
        source_doc="folder-board.png",
        answer_style="policy",
        difficulty="medium",
        category="paraphrase_rewrite",
        answerable=True,
        expected_keypoints=["Knowledge Base"],
        preview_terms=["Knowledge Base"],
        forbidden_terms=["folder is the authorization boundary"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-008",
        modality="image_ocr",
        question="On the evidence board, what jump-back pointer should accompany doc_id in OCR evidence output?",
        source_doc="evidence-board.png",
        answer_style="policy",
        difficulty="medium",
        category="paraphrase_rewrite",
        answerable=True,
        expected_keypoints=["preview_locator"],
        preview_terms=["preview_locator"],
        forbidden_terms=["checksum_id"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-009",
        modality="markdown",
        question="What is the CAB ticket number for the payroll cutover?",
        answer_style="refusal",
        difficulty="complex",
        category="evidence_insufficient",
        answerable=False,
        expected_keypoints=["No confirmable information", "current knowledge base"],
        forbidden_terms=["CAB-2048"],
        seed_docs=["cutover-approval.md", "refusal-guideline.md"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-010",
        modality="markdown",
        question="What bridge URL is listed for the war-room handover?",
        answer_style="refusal",
        difficulty="complex",
        category="evidence_insufficient",
        answerable=False,
        expected_keypoints=["No confirmable information", "current knowledge base"],
        forbidden_terms=["https://handover-bridge.local"],
        seed_docs=["handover-sla.md", "refusal-guideline.md"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-009",
        modality="pdf",
        question="What checksum token is listed in the PDF release checklist?",
        answer_style="refusal",
        difficulty="complex",
        category="evidence_insufficient",
        answerable=False,
        expected_keypoints=["No confirmable information", "active PDF knowledge base"],
        forbidden_terms=["checksum-pdf-2048"],
        seed_docs=["release-checklist-business.pdf", "refusal-rule.pdf"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-010",
        modality="pdf",
        question="What pager rotation id is listed in the PDF war-room handover sheet?",
        answer_style="refusal",
        difficulty="complex",
        category="evidence_insufficient",
        answerable=False,
        expected_keypoints=["No confirmable information", "active PDF knowledge base"],
        forbidden_terms=["pager-rotation-42"],
        seed_docs=["war-room-handover-business.pdf", "refusal-rule.pdf"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-009",
        modality="image_ocr",
        question="What room number is listed on the approval whiteboard?",
        answer_style="refusal",
        difficulty="complex",
        category="evidence_insufficient",
        answerable=False,
        expected_keypoints=["No confirmable information", "current knowledge base"],
        forbidden_terms=["Room 214"],
        seed_docs=["approval-whiteboard-business.png", "noisy-policy-board.png"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-010",
        modality="image_ocr",
        question="What bridge URL is printed on the escalation whiteboard?",
        answer_style="refusal",
        difficulty="complex",
        category="evidence_insufficient",
        answerable=False,
        expected_keypoints=["No confirmable information", "current knowledge base"],
        forbidden_terms=["https://ocr-bridge.local"],
        seed_docs=["escalation-whiteboard-business.png", "noisy-policy-board.png"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-011",
        modality="markdown",
        question="Does folder path cutover/runbook/ create a separate authorization boundary, or does access control stay at the knowledge-base level?",
        source_doc="workflow-boundary.md",
        answer_style="policy",
        difficulty="medium",
        category="scope_isolation_trap",
        answerable=True,
        expected_keypoints=["cutover/runbook/", "authorization boundary", "knowledge base level"],
        preview_terms=["authorization boundary", "knowledge base level"],
        forbidden_terms=["folder path creates the authorization boundary"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-012",
        modality="markdown",
        question="Under the single KB scope contract, which field must echo the requested knowledge base, and if evidence is missing may the assistant fabricate from outside memory?",
        source_doc="scope-refusal-bridge.md",
        answer_style="policy",
        difficulty="medium",
        category="scope_isolation_trap",
        answerable=True,
        expected_keypoints=["effective_kb_ids", "must not fabricate from outside memory"],
        preview_terms=["effective_kb_ids", "outside memory"],
        forbidden_terms=["effective scope may expand outside the request", "fabrication from outside memory is allowed"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-011",
        modality="pdf",
        question="Across the PDF scope refusal bridge and folder boundary note, which field must echo the active PDF knowledge base, and what remains the authorization boundary?",
        source_doc="scope-refusal-bridge.pdf",
        required_evidence_docs=["scope-refusal-bridge.pdf", "folder-boundary.pdf"],
        answer_style="policy",
        difficulty="medium",
        category="scope_isolation_trap",
        answerable=True,
        expected_keypoints=["effective_kb_ids", "authorization boundary", "Knowledge Base"],
        preview_terms=["effective_kb_ids", "authorization boundary"],
        forbidden_terms=["folder is the authorization boundary"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-012",
        modality="pdf",
        question="If the active PDF knowledge base has no confirmable evidence, may the assistant answer from outside memory?",
        source_doc="refusal-rule.pdf",
        answer_style="policy",
        difficulty="medium",
        category="scope_isolation_trap",
        answerable=True,
        expected_keypoints=["No confirmable information", "must not fabricate from outside memory"],
        preview_terms=["No confirmable information", "outside memory"],
        forbidden_terms=["outside memory may be used"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-011",
        modality="image_ocr",
        question="On the scope and folder boards, which field should echo the declared image knowledge base, and what remains the authorization boundary?",
        source_doc="scope-board.png",
        required_evidence_docs=["scope-board.png", "folder-board.png"],
        answer_style="policy",
        difficulty="medium",
        category="scope_isolation_trap",
        answerable=True,
        expected_keypoints=["effective_kb_ids", "authorization boundary", "Knowledge Base"],
        preview_terms=["effective_kb_ids", "authorization boundary"],
        forbidden_terms=["folder is the authorization boundary"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-012",
        modality="image_ocr",
        question="When OCR evidence is sparse on the noisy policy board, may the assistant rely on fabricated memory, or must it stay inside the active knowledge base?",
        source_doc="noisy-policy-board.png",
        answer_style="policy",
        difficulty="medium",
        category="scope_isolation_trap",
        answerable=True,
        expected_keypoints=["No confirmable information", "Active knowledge base only", "must not fabricate from outside memory"],
        preview_terms=["No confirmable information", "must not fabricate"],
        forbidden_terms=["fabricated memory is allowed", "outside memory may be used"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-md-013",
        modality="markdown",
        question="刚才看的那两份文档里，最终审批人是谁，P1 cutover incident 又要在几分钟内升级给谁？",
        source_doc="cutover-approval.md",
        required_evidence_docs=["cutover-approval.md", "handover-sla.md"],
        answer_style="comparison",
        difficulty="complex",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["Li Qing", "Zhao Lin", "15 minutes"],
        preview_terms=["Li Qing", "15 minutes"],
        forbidden_terms=["10 minutes", "Liu Chang"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-pdf-013",
        modality="pdf",
        question="From those two PDFs we just opened, who owns the final sign-off, and what Sev1 escalation interval belongs to the handover sheet?",
        source_doc="release-checklist-business.pdf",
        required_evidence_docs=["release-checklist-business.pdf", "war-room-handover-business.pdf"],
        answer_style="comparison",
        difficulty="complex",
        category="similar_document_confusion",
        answerable=True,
        expected_keypoints=["Chen Yu", "10 minutes"],
        preview_terms=["Chen Yu", "10 minutes"],
        forbidden_terms=["15 minutes", "Xu Nan"],
    ),
    _build_case(
        dataset=DATASET_HARD,
        case_id="eval-v8-hard-img-013",
        modality="image_ocr",
        question="If OCR on that noisy board is too patchy to verify anything, can the assistant freestyle from cached memory, or must it stay inside the active knowledge base?",
        source_doc="noisy-policy-board.png",
        source_locator="tests/api/chat_eval_runner.py::IMAGE_EXTRA_IMPORTS['noisy-policy-board.png']",
        answer_style="policy",
        difficulty="complex",
        category="paraphrase_rewrite",
        answerable=True,
        expected_keypoints=["No confirmable information", "active knowledge base", "must not fabricate from outside memory"],
        preview_terms=["No confirmable information", "outside memory"],
        forbidden_terms=["cached memory may be used", "fabricated memory is allowed"],
    ),
]



def build_main_schema() -> dict[str, Any]:
    schema = copy.deepcopy(_load_json(V6_SCHEMA_PATH))
    schema["dataset_name"] = DATASET_MAIN
    schema["required_fields"] = REQUIRED_FIELDS
    schema["quality_gates"] = {
        "minimum_total_cases": 93,
        "minimum_cases_per_modality": 28,
        "minimum_cases_per_difficulty": 24,
        "minimum_no_evidence_cases": 20,
        "minimum_preview_required_cases": 60,
        "minimum_refusal_cases_per_modality": 6,
        "minimum_cases_per_answer_style": 8,
        "minimum_cases_per_category": 5,
        "minimum_cases_per_judge_dimension": 20,
        "minimum_cjk_cases": 54,
        "minimum_cjk_cases_per_modality": 18,
        "minimum_weak_signal_cases": 5,
        "minimum_negative_contract_cases_per_modality": 5,
        "minimum_history_grounded_cases": 6,
        "minimum_history_grounded_cases_per_modality": 2,
    }
    schema["required_refusal_categories"] = ["no_evidence", "hard_refusal", "scope_contract"]
    schema["required_refusal_markers_by_category"] = {
        "no_evidence": ["No confirmable information", "knowledge base"],
        "hard_refusal": ["No confirmable information", "knowledge base"],
        "scope_contract": ["must not fabricate", "knowledge base"],
    }
    schema["required_negative_contract_categories"] = ["process_boundary", "scope_contract"]
    schema["required_negative_contract_markers_by_category"] = {
        "process_boundary": ["authorization boundary", "knowledge base"],
        "scope_contract": ["must not fabricate", "effective_kb_ids"],
    }
    return schema



def build_hard_schema() -> dict[str, Any]:
    return {
        "dataset_name": DATASET_HARD,
        "evaluation_mode": "healthy",
        "required_fields": REQUIRED_FIELDS,
        "allowed_modalities": ["markdown", "pdf", "image_ocr"],
        "allowed_answer_styles": ["comparison", "policy", "refusal"],
        "allowed_difficulties": ["medium", "complex"],
        "allowed_categories": [
            "similar_document_confusion",
            "stale_version_conflict",
            "chunk_boundary",
            "paraphrase_rewrite",
            "evidence_insufficient",
            "scope_isolation_trap",
        ],
        "allowed_scope_types": ["single_kb"],
        "allowed_isolation_levels": ["physical_isolated"],
        "allowed_judge_dimensions": [
            "factual_accuracy",
            "completeness",
            "citation_accuracy",
            "groundedness",
            "refusal_correctness",
        ],
        "quality_gates": {
            "minimum_total_cases": 36,
            "minimum_cases_per_modality": 12,
            "minimum_cases_per_difficulty": 12,
            "minimum_no_evidence_cases": 6,
            "minimum_preview_required_cases": 30,
            "minimum_refusal_cases_per_modality": 2,
            "minimum_cases_per_answer_style": 6,
            "minimum_cases_per_category": 6,
            "minimum_cases_per_judge_dimension": 6,
            "minimum_negative_contract_cases_per_modality": 2,
            "minimum_history_grounded_cases": 6,
            "minimum_history_grounded_cases_per_modality": 2,
        },
        "run_gates": {
            "scope_pass_rate_min": 1.0,
            "average_keypoint_coverage_min": 0.75,
            "evidence_hit_rate_min": 0.85,
            "preview_resolvable_rate_min": 0.85,
            "source_count_match_rate_min": 0.85,
            "forbidden_term_clean_rate_min": 1.0,
        },
        "rubric_dimensions": {
            "factual_accuracy": {"weight": 0.3, "min": 0.8},
            "completeness": {"weight": 0.25, "min": 0.7},
            "citation_accuracy": {"weight": 0.2, "min": 0.85},
            "groundedness": {"weight": 0.15, "min": 0.85},
            "refusal_correctness": {"weight": 0.1, "min": 0.95},
        },
        "required_refusal_categories": ["evidence_insufficient"],
        "required_refusal_markers_by_category": {
            "evidence_insufficient": ["No confirmable information", "knowledge base"],
        },
        "required_negative_contract_categories": ["scope_isolation_trap"],
        "required_negative_contract_markers_by_category": {
            "scope_isolation_trap": ["authorization boundary", "must not fabricate", "effective_kb_ids"],
        },
    }


MAIN_HISTORY_GROUNDED_UPDATES: dict[str, dict[str, Any]] = {
    "eval-v4-md-001": {
        "history_turns": ["先看一下 Payroll cutover approval matrix。"],
        "question": "刚才看的 Payroll cutover approval matrix 里面，最终审批人是谁？",
    },
    "eval-v5-md-002": {
        "history_turns": ["先比较一下 payroll cutover approval matrix 和 war-room handover SLA。"],
        "question": "那最终审批人和 on-call manager 分别是谁？",
    },
    "eval-v4-pdf-001": {
        "history_turns": ["先看一下 Payroll release checklist。"],
        "question": "那里面 final sign-off owner 是谁？",
    },
    "eval-v5-pdf-002": {
        "history_turns": ["先比较一下 payroll release checklist 和 war-room handover sheet。"],
        "question": "那 final sign-off owner 和 incident commander 分别是谁？",
    },
    "eval-v4-img-001": {
        "history_turns": ["先看一下 approval whiteboard。"],
        "question": "那上面写的 final approver 是谁？",
    },
    "eval-v5-img-002": {
        "history_turns": ["先比较一下 approval whiteboard 和 escalation whiteboard。"],
        "question": "那 final approver 和 on-call manager 分别是谁？",
    },
}



def build_main_cases() -> list[dict[str, Any]]:
    base_cases = copy.deepcopy(_load_json(V6_CASES_PATH))
    normalized: list[dict[str, Any]] = []
    for record in base_cases:
        item = copy.deepcopy(record)
        item["dataset"] = DATASET_MAIN
        item.setdefault("preview_terms", [])
        item.setdefault("forbidden_terms", [])
        if item["case_id"] in MAIN_HISTORY_GROUNDED_UPDATES:
            item.update(copy.deepcopy(MAIN_HISTORY_GROUNDED_UPDATES[item["case_id"]]))
        normalized.append(item)
    normalized.extend(copy.deepcopy(MAIN_ADDITIONS))
    return normalized



HARD_HISTORY_GROUNDED_UPDATES: dict[str, dict[str, Any]] = {
    "eval-v8-hard-md-009": {
        "history_turns": ["Summarize the payroll cutover approval matrix."],
        "question": "What is its CAB ticket number?",
    },
    "eval-v8-hard-md-010": {
        "history_turns": ["Summarize the war-room handover SLA."],
        "question": "What bridge URL does it list?",
    },
    "eval-v8-hard-pdf-009": {
        "history_turns": ["Summarize the PDF release checklist."],
        "question": "What checksum token does it list?",
    },
    "eval-v8-hard-pdf-010": {
        "history_turns": ["Summarize the PDF war-room handover sheet."],
        "question": "What pager rotation id does it list?",
    },
    "eval-v8-hard-img-009": {
        "history_turns": ["Summarize the approval whiteboard."],
        "question": "What room number does it list?",
    },
    "eval-v8-hard-img-010": {
        "history_turns": ["Summarize the escalation whiteboard."],
        "question": "What bridge URL does it print?",
    },
    "eval-v8-hard-md-013": {
        "history_turns": [
            "先看一下 Payroll cutover approval matrix。",
            "再打开 war-room handover SLA。",
        ],
        "question": "刚才看的那两份文档里，最终审批人是谁，P1 cutover incident 又要在几分钟内升级给谁？",
    },
    "eval-v8-hard-pdf-013": {
        "history_turns": [
            "Open the PDF release checklist.",
            "Then show the war-room handover sheet.",
        ],
        "question": "From those two PDFs we just opened, who owns the final sign-off, and what Sev1 escalation interval belongs to the handover sheet?",
    },
    "eval-v8-hard-img-013": {
        "history_turns": ["Show me the noisy policy board."],
        "question": "If OCR on that noisy board is too patchy to verify anything, can the assistant freestyle from cached memory, or must it stay inside the active knowledge base?",
    },
}


def build_hard_cases() -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for record in HARD_CASES:
        item = copy.deepcopy(record)
        if item["case_id"] in HARD_HISTORY_GROUNDED_UPDATES:
            item.update(copy.deepcopy(HARD_HISTORY_GROUNDED_UPDATES[item["case_id"]]))
        normalized.append(item)
    return normalized



def build_layered_suite() -> dict[str, Any]:
    return {
        "suite_name": "local_multi_kb_eval_v8_layered_suite",
        "strategy": "A-most-practical-layered-expansion",
        "layers": [
            {
                "name": "smoke",
                "purpose": "environment_rebuild_ci_smoke",
                "dataset_name": "local_multi_kb_eval_v7_holdout_regression",
                "target_case_count": 24,
                "cases_path": str(V7_CASES_PATH.relative_to(REPO_ROOT)).replace('\\', '/'),
                "schema_path": str(V7_SCHEMA_PATH.relative_to(REPO_ROOT)).replace('\\', '/'),
            },
            {
                "name": "main",
                "purpose": "pre_release_primary_gate",
                "dataset_name": DATASET_MAIN,
                "target_case_count": 93,
                "focus": [
                    "qa_accuracy",
                    "multi_source_merge",
                    "refusal",
                    "scope_isolation",
                    "preview_grounding",
                ],
                "cases_path": str((V8_MAIN_DIR / 'cases.json').relative_to(REPO_ROOT)).replace('\\', '/'),
                "schema_path": str((V8_MAIN_DIR / 'schema.json').relative_to(REPO_ROOT)).replace('\\', '/'),
            },
            {
                "name": "hard",
                "purpose": "boundary_bug_hunting",
                "dataset_name": DATASET_HARD,
                "target_case_count": 39,
                "focus": [
                    "similar_document_confusion",
                    "stale_version_conflict",
                    "chunk_boundary",
                    "paraphrase_rewrite",
                    "evidence_insufficient",
                    "scope_isolation_trap",
                ],
                "cases_path": str((V8_HARD_DIR / 'cases.json').relative_to(REPO_ROOT)).replace('\\', '/'),
                "schema_path": str((V8_HARD_DIR / 'schema.json').relative_to(REPO_ROOT)).replace('\\', '/'),
            },
        ],
    }



def main() -> None:
    parser = argparse.ArgumentParser(description="Build layered eval_v8 fixture files.")
    parser.parse_args()

    main_schema = build_main_schema()
    hard_schema = build_hard_schema()
    main_cases = build_main_cases()
    hard_cases = build_hard_cases()
    layered_suite = build_layered_suite()

    _write_json(V8_MAIN_DIR / "schema.json", main_schema)
    _write_json(V8_MAIN_DIR / "cases.json", main_cases)
    _write_json(V8_HARD_DIR / "schema.json", hard_schema)
    _write_json(V8_HARD_DIR / "cases.json", hard_cases)
    _write_json(LAYERED_SUITE_PATH, layered_suite)

    summary = {
        "main_dataset": main_schema["dataset_name"],
        "main_total_cases": len(main_cases),
        "hard_dataset": hard_schema["dataset_name"],
        "hard_total_cases": len(hard_cases),
        "suite_path": str(LAYERED_SUITE_PATH.relative_to(REPO_ROOT)).replace('\\', '/'),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
