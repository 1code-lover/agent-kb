from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import MagicMock

import fitz
from tests.api._testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from api.app import app
from api.services import asset_service, kb_service
import api.services.chat_service as chat_service
from scripts.validate_rag_quality_fixtures import load_eval_schema, validate_eval_cases_file
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry
from server.readers.pdf_ocr import PDFOCRReader
from server.utils.font_fallbacks import OCR_FONT_CANDIDATES, load_first_available_font
from server.utils.file import get_kb_data_dir
from tests.api._semireal_chat_support import FakeUploadFile, SemirealIndexManager, SemirealQueryEngine
from tests.api.chat_eval_contracts import (
    build_negative_contract_summary,
    build_refusal_summary,
    evaluate_contract_gates,
    evaluate_report_run_passed,
)
from tests.api.chat_eval_suite_reporting import (
    build_eval_suite_layer_summary,
    load_eval_suite_manifest,
)
from tests.api.chat_qa_metrics import (
    _confidence_interval_wilson,
    build_chat_case_report,
    summarize_chat_case_reports,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "rag_quality" / "eval_v1" / "cases.json"
DEFAULT_EVAL_SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "rag_quality" / "eval_v1" / "schema.json"
DEFAULT_LAYERED_SUITE_PATH = REPO_ROOT / "tests" / "fixtures" / "rag_quality" / "eval_layered_suite.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "docs" / "20260722-local-multi-kb-assistant" / "artifacts" / "qa-eval"
MARKDOWN_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "rag_quality" / "semireal_markdown"
MARKDOWN_KB_ID = "eval-kb-markdown"
PDF_KB_ID = "eval-kb-pdf"
PDF_ZERO_KB_ID = "eval-kb-pdf-zero"
IMAGE_KB_ID = "eval-kb-image"
FONT_CANDIDATES = OCR_FONT_CANDIDATES
EVAL_KB_MODALITIES = {
    MARKDOWN_KB_ID: "markdown",
    PDF_KB_ID: "pdf",
    PDF_ZERO_KB_ID: "pdf",
    IMAGE_KB_ID: "image_ocr",
}
BASE_MARKDOWN_IMPORTS = {
    "scope-contract.md": "qa/contracts/scope-contract.md",
    "evidence-preview.md": "qa/evidence/evidence-preview.md",
    "refusal-guideline.md": "qa/policies/refusal-guideline.md",
    "evaluation-metrics.md": "qa/evaluation/evaluation-metrics.md",
    "folder-boundary.md": "qa/architecture/folder-boundary.md",
    "ingestion-priority.md": "qa/ingestion/ingestion-priority.md",
    "suite-metrics-gate.md": "qa/evaluation/suite-metrics-gate.md",
}
MARKDOWN_EXTRA_IMPORTS = {
    "cutover-approval.md": "business/cutover/cutover-approval.md",
    "handover-sla.md": "business/handover/handover-sla.md",
    "workflow-boundary.md": "business/architecture/workflow-boundary.md",
    "utf8-boundary.md": "business/architecture/utf8-boundary.md",
    "long-cutover-handbook.md": "business/cutover/long-cutover-handbook.md",
    "refusal-wording-note.md": "qa/policies/refusal-wording-note.md",
    "scope-refusal-bridge.md": "qa/contracts/scope-refusal-bridge.md",
}
BASE_PDF_IMPORTS = {
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
        Folder is an organization object and not an authorization boundary.
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
}
BASE_IMAGE_IMPORTS = {
    "scope-board.png": {
        "relative_path": "images/contracts/scope-board.png",
        "ocr_text": "requested_scope_type must remain single_kb and effective_kb_ids should echo the declared image knowledge base. Knowledge Base remains the authorization boundary for this scope board.",
    },
    "folder-board.png": {
        "relative_path": "images/architecture/folder-board.png",
        "ocr_text": "Folders are organizational objects inside one knowledge base. Folder is an organization object, 中文补充：文件夹只是知识库内部的组织对象. Knowledge Base is the authorization boundary for image OCR answers, 中文补充：图片 OCR 回答也必须遵守知识库边界。",
    },
    "evidence-board.png": {
        "relative_path": "images/evidence/evidence-board.png",
        "ocr_text": "Evidence output should include doc_id preview_locator and a resolvable excerpt for OCR derived assets. 中文补充：证据结果至少要包含 doc_id 和 preview_locator。",
    },
}

PDF_EXTRA_IMPORTS = {
    "long-cutover-handbook.pdf": {
        "relative_path": "pdf/business/long-cutover-handbook.pdf",
        "text": """
        Payroll long-form handbook.
        Warm-up note: archive stale dashboards after each rehearsal.
        Folder labels stay inside a single knowledge base.
        Final approval checkpoint closes at 21:55 Beijing time.
        Evidence packets must keep preview_locator aligned with the cited paragraph.
        Legacy dry-run note: the retired rehearsal closed at 18:30 and should not be used for the live answer.
        """,
    },
    "refusal-rule.pdf": {
        "relative_path": "pdf/policies/refusal-rule.pdf",
        "text": """
        Refusal rule for PDF QA.
        If no confirmable evidence appears inside the active PDF knowledge base, the assistant must say no confirmable information is available and must not fabricate from outside memory.
        """,
    },
    "ocr-readiness.pdf": {
        "relative_path": "pdf/ingestion/ocr-readiness.pdf",
        "text": """
        OCR readiness note for PDF ingestion checks.
        fitz text-layer extraction should run before OCR fallback.
        Tests should surface paddleocr dependency readiness.
        Tests must not hide readiness behind generic failures.
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
    "embedding-gap.pdf": {
        "relative_path": "pdf/weak-signals/embedding-gap.pdf",
        "text": """
        Authorization boundary remains the knowledge base.
        External agents must stay inside the declared knowledge scope.
        Missing embeddings should be surfaced as a weak-signal diagnostic.
        """,
        "simulate_nodes_without_embedding": True,
    },
    "zero-text-diagnostic.pdf": {
        "relative_path": "pdf/weak-signals/zero-text-diagnostic.pdf",
        "text": "",
        "kb_id": PDF_ZERO_KB_ID,
        "force_empty_text_document": True,
    },
    "release-checklist-business.pdf": {
        "relative_path": "pdf/business/release-checklist-business.pdf",
        "text": """
        Payroll release checklist.
        Final sign-off owner: Operations Director Chen Yu.
        Rollback owner: Database Lead Xu Nan.
        The operator checklist must close before 23:00 Beijing time.
        Evidence package must include doc_id and preview_locator.
        """,
    },
    "war-room-handover-business.pdf": {
        "relative_path": "pdf/business/war-room-handover-business.pdf",
        "text": """
        War-room handover sheet.
        Primary incident commander: SRE Manager Zhao Lin.
        Sev1 cutover issues must be escalated to the commander within 10 minutes.
        If the active knowledge base has no confirmable evidence, the answer must say No confirmable information is available in the current knowledge base.
        """,
    },
    "scope-refusal-bridge.pdf": {
        "relative_path": "pdf/contracts/scope-refusal-bridge.pdf",
        "text": """
        PDF title: Scope refusal bridge.
        Scope refusal bridge rule: the assistant must not fabricate from outside memory when the current PDF knowledge base has no confirmable evidence.
        Scope refusal bridge also requires the assistant to stay inside the current PDF knowledge base.
        Knowledge Base remains the authorization boundary for this PDF scope bridge.
        Exact field name for scope echo: effective_kb_ids.
        If the active scope still needs an explicit field name, effective_kb_ids must stay aligned with the current PDF knowledge base.
        """,
    },
}
IMAGE_EXTRA_IMPORTS = {
    "long-cutover-handbook-board.png": {
        "relative_path": "images/business/long-cutover-handbook-board.png",
        "image_lines": [
            "Payroll long OCR handbook",
            "Final approval checkpoint 21:50 Beijing time",
            "Folder names stay in one knowledge base",
            "Legacy rehearsal 18:20 is retired",
            "preview_locator must stay aligned",
        ],
        "ocr_text": "Payroll long OCR handbook. Final approval checkpoint closes at 21:50 Beijing time. Folder names stay inside one knowledge base. preview_locator must stay aligned with the cited evidence. Legacy rehearsal 18:20 is retired and must not be used for the live answer.",
    },
    "metrics-board.png": {
        "relative_path": "images/evaluation/metrics-board.png",
        "ocr_text": "pass_rate evidence_hit_rate and preview_resolvable_rate should stay at one point zero for a clean OCR answer suite.",
    },
    "noisy-policy-board.png": {
        "relative_path": "images/policies/noisy-policy-board.png",
        "render_mode": "low_contrast_rotated",
        "image_lines": [
            "Low-contrast policy board for OCR stress checks",
            "If OCR remains sparse, say no confirmable information",
            "Active knowledge base only. Must not fabricate from outside memory",
        ],
        "ocr_text": "low contrast OCR fallback. no confirmable information. active knowledge base only. must not fabricate from outside memory.",
    },
    "weak-no-text-board.png": {
        "relative_path": "images/weak-signals/weak-no-text-board.png",
        "image_lines": [
            "Beacon no text board",
            "doc_id and preview_locator are required evidence fields",
            "weak signal should trigger diagnostic capture",
        ],
        "ocr_status": "no_text",
        "ocr_text": "",
    },
    "weak-failed-board.png": {
        "relative_path": "images/weak-signals/weak-failed-board.png",
        "image_lines": [
            "Beacon failed board",
            "active knowledge base only",
            "no fabricated memory allowed",
        ],
        "ocr_status": "failed",
        "ocr_error": "mock weak signal ocr failed",
        "ocr_text": "",
    },
    "weak-dependency-board.png": {
        "relative_path": "images/weak-signals/weak-dependency-board.png",
        "image_lines": [
            "Beacon dependency board",
            "paddleocr dependency must be ready before OCR import",
            "If dependency is missing, surface the issue instead of fabricating an answer",
        ],
        "ocr_status": "failed",
        "ocr_error": "No module named 'paddleocr'",
        "missing_dependency": "paddleocr",
        "dependency_status": "missing",
        "ocr_text": "",
    },
    "approval-whiteboard-business.png": {
        "relative_path": "images/business/approval-whiteboard-business.png",
        "image_lines": [
            "Final approver Zhao Lin",
            "Rollback owner Sun Kai",
            "Deadline 22:45 Beijing time",
        ],
        "ocr_text": "Final approver Zhao Lin. Rollback owner Sun Kai. Deadline 22:45 Beijing time.",
    },
    "escalation-whiteboard-business.png": {
        "relative_path": "images/business/escalation-whiteboard-business.png",
        "image_lines": [
            "P1 issues escalate to Liu Chang in 10 minutes",
            "folder is not an authorization boundary",
            "knowledge base remains the authorization boundary",
            "No confirmable information when evidence is missing",
        ],
        "ocr_text": "P1 cutover issues must escalate to on-call manager Liu Chang within 10 minutes. folder is not an authorization boundary. Knowledge base remains the authorization boundary for this escalation board. If evidence is missing, reply No confirmable information is available in the current knowledge base.",
    },
    "boundary-knowledge-board.png": {
        "relative_path": "images/architecture/boundary-knowledge-board.png",
        "image_lines": [
            "OCR boundary knowledge board",
            "folder path is not an authorization boundary",
            "knowledge base remains the authorization boundary",
        ],
        "ocr_text": "OCR boundary knowledge board. Folder path is not an authorization boundary. Knowledge base remains the authorization boundary for image OCR answers.",
    },
}


def build_semireal_import_catalog(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build the semireal import catalog from requested eval cases."""
    catalog = {
        "markdown": dict(BASE_MARKDOWN_IMPORTS),
        "pdf": dict(BASE_PDF_IMPORTS),
        "image_ocr": dict(BASE_IMAGE_IMPORTS),
    }
    extra_catalogs = {
        "markdown": MARKDOWN_EXTRA_IMPORTS,
        "pdf": PDF_EXTRA_IMPORTS,
        "image_ocr": IMAGE_EXTRA_IMPORTS,
    }

    for case in cases:
        modality = str(case.get("modality") or "")
        if modality not in catalog:
            continue

        candidate_docs: list[str] = []
        source_doc = case.get("source_doc")
        if source_doc:
            candidate_docs.append(str(source_doc))

        for name in list(case.get("required_evidence_docs") or []):
            normalized = str(name).strip()
            if normalized:
                candidate_docs.append(normalized)

        for name in list(case.get("seed_docs") or []):
            normalized = str(name).strip()
            if normalized:
                candidate_docs.append(normalized)

        if not candidate_docs:
            continue

        extra_catalog = extra_catalogs[modality]
        for doc_name in dict.fromkeys(candidate_docs):
            if doc_name in catalog[modality]:
                continue
            if doc_name not in extra_catalog:
                raise ValueError(f"unsupported semireal support document for modality={modality}: {doc_name}")
            extra_entry = extra_catalog[doc_name]
            catalog[modality][doc_name] = dict(extra_entry) if isinstance(extra_entry, dict) else str(extra_entry)

    return catalog
RUN_GATE_FIELD_MAP = {
    "scope_pass_rate_min": "scope_pass_rate",
    "average_keypoint_coverage_min": "average_keypoint_coverage",
    "evidence_hit_rate_min": "evidence_hit_rate",
    "preview_resolvable_rate_min": "preview_resolvable_rate",
    "source_count_match_rate_min": "source_count_match_rate",
    "forbidden_term_clean_rate_min": "forbidden_term_clean_rate",
}
DIAGNOSTIC_GATE_FIELD_MAP = {
    "case_expectation_match_rate_min": "case_expectation_match_rate",
    "minimum_weak_signal_kb_count": "weak_signal_kb_count",
    "minimum_weak_signal_modality_count": "weak_signal_modality_count",
}


def load_eval_cases(
    path: str | Path = DEFAULT_EVAL_CASES_PATH,
    *,
    schema_path: str | Path = DEFAULT_EVAL_SCHEMA_PATH,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """加载并校验 eval_v1 评测数据集。"""
    validate_eval_cases_file(path, schema_path=schema_path)
    schema = load_eval_schema(schema_path)
    case_path = Path(path)
    if not case_path.is_absolute():
        case_path = (REPO_ROOT / case_path).resolve()
    cases = json.loads(case_path.read_text(encoding="utf-8"))
    return schema, list(cases)


def _normalize_eval_case(case: dict[str, Any]) -> dict[str, Any]:
    """把原始评测 case 归一化为指标计算所需字段。"""
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "expected_doc": case["source_doc"] if case.get("answerable") else None,
        "expected_keypoints": list(case.get("expected_keypoints", [])),
        "must_not_contain": list(case.get("forbidden_terms", [])),
        "preview_terms": list(case.get("preview_terms", [])),
        "expected_source_count": int(case.get("expected_source_count", 0)),
    }


def _normalize_history_turns(case: dict[str, Any]) -> list[str]:
    """清理 case 中可选的 history_turns，供 follow-up 评测预热复用。"""
    turns: list[str] = []
    for item in list(case.get("history_turns") or []):
        normalized = str(item).strip()
        if normalized:
            turns.append(normalized)
    return turns


def _attach_history_metadata(report: dict[str, Any], history_turns: list[str] | None = None) -> dict[str, Any]:
    """把 history-grounded 评测元信息挂到 case report 上。"""
    normalized_turns = [str(item) for item in list(history_turns or [])]
    report.update(
        {
            "history_grounded": bool(normalized_turns),
            "history_turn_count": len(normalized_turns),
            "history_turns": normalized_turns,
        }
    )
    return report


def _build_breakdown(reports: Iterable[dict[str, Any]], field_name: str) -> dict[str, dict[str, Any]]:
    """按指定字段聚合 case 结果，并输出 breakdown 指标。"""
    groups: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        key = str(report.get(field_name, "unknown"))
        groups.setdefault(key, []).append(report)

    breakdown: dict[str, dict[str, Any]] = {}
    for key, items in sorted(groups.items()):
        passed = sum(1 for item in items if item.get("passed"))
        scope_passed = sum(1 for item in items if item.get("scope_passed"))
        total_keypoints = sum(int(item.get("keypoint_total") or 0) for item in items)
        matched_keypoints = sum(len(item.get("keypoint_hits") or []) for item in items)
        evidence_expected_items = [
            item
            for item in items
            if item.get("required_evidence_docs") or item.get("expected_doc") is not None or item.get("expected_source_count", 0) > 0
        ]
        evidence_hit = sum(1 for item in evidence_expected_items if item.get("evidence_hit"))
        preview_required_items = [item for item in items if item.get("preview_required")]
        preview_resolved = sum(1 for item in preview_required_items if item.get("preview_resolvable"))
        preview_term_total = sum(int(item.get("preview_term_total") or 0) for item in preview_required_items)
        preview_term_hits = sum(len(item.get("preview_term_hits") or []) for item in preview_required_items)
        source_count_match = sum(1 for item in items if item.get("source_count_match"))
        forbidden_term_clean = sum(1 for item in items if item.get("blocked_term_clean"))
        breakdown[key] = {
            "count": len(items),
            "passed": passed,
            "failed": len(items) - passed,
            "pass_rate": passed / len(items) if items else 0.0,
            "pass_rate_ci95": _confidence_interval_wilson(passed, len(items)),
            "scope_pass_rate": scope_passed / len(items) if items else 0.0,
            "average_keypoint_coverage": sum(float(item.get("keypoint_coverage", 0.0)) for item in items) / len(items) if items else 0.0,
            "total_keypoints": total_keypoints,
            "matched_keypoints": matched_keypoints,
            "keypoint_hit_rate": matched_keypoints / total_keypoints if total_keypoints else 1.0,
            "evidence_expected_cases": len(evidence_expected_items),
            "evidence_hit_cases": evidence_hit,
            "evidence_hit_rate": evidence_hit / len(evidence_expected_items) if evidence_expected_items else 1.0,
            "preview_required_cases": len(preview_required_items),
            "preview_resolved_cases": preview_resolved,
            "preview_resolvable_rate": preview_resolved / len(preview_required_items) if preview_required_items else 1.0,
            "preview_term_total": preview_term_total,
            "preview_term_hits": preview_term_hits,
            "preview_term_hit_rate": preview_term_hits / preview_term_total if preview_term_total else 1.0,
            "source_count_match_rate": source_count_match / len(items) if items else 0.0,
            "forbidden_term_clean_rate": forbidden_term_clean / len(items) if items else 0.0,
        }
    return breakdown


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    """安全计算比率，避免除零。"""
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _build_import_quality_signal_tags(metrics: dict[str, Any]) -> list[str]:
    """根据导入指标提取需要重点关注的质量弱信号标签。"""
    tags: list[str] = []
    if int(metrics.get("failed_count") or 0) > 0:
        tags.append("failed_imports")
    if int(metrics.get("empty_count") or 0) > 0:
        tags.append("empty_imports")
    if int(metrics.get("dependency_missing_count") or 0) > 0:
        tags.append("dependency_missing")
    if int(metrics.get("total_ocr_failed_count") or 0) > 0:
        tags.append("ocr_failed")
    if int(metrics.get("total_ocr_no_text_count") or 0) > 0:
        tags.append("ocr_no_text")
    if int(metrics.get("nodes_without_embedding_count") or 0) > 0:
        tags.append("nodes_without_embedding")
    if int(metrics.get("document_count") or 0) > 0 and int(metrics.get("input_text_chars") or 0) == 0:
        tags.append("zero_text_content")
    if int(metrics.get("asset_registered_without_index_count") or 0) > 0:
        tags.append("asset_registered_without_index")
    return tags


def _finalize_import_metrics(entry: dict[str, Any]) -> dict[str, Any]:
    """补齐单条导入摘要的派生指标，便于后续做 QA 关联分析。"""
    indexed_from_ocr_count = int(entry.get("indexed_from_ocr_count") or 0)
    embedded_indexed_from_ocr_count = int(entry.get("embedded_indexed_from_ocr_count") or 0)
    asset_registered_count = int(entry.get("asset_registered_count") or 0)
    asset_registered_without_index_count = max(
        asset_registered_count - indexed_from_ocr_count - embedded_indexed_from_ocr_count,
        0,
    )
    total_ocr_failed_count = int(entry.get("ocr_failed_count") or 0) + int(entry.get("embedded_ocr_failed_count") or 0)
    total_ocr_no_text_count = int(entry.get("ocr_no_text_count") or 0) + int(entry.get("embedded_ocr_no_text_count") or 0)
    entry["asset_registered_without_index_count"] = asset_registered_without_index_count
    entry["total_ocr_failed_count"] = total_ocr_failed_count
    entry["total_ocr_no_text_count"] = total_ocr_no_text_count
    entry["success_rate"] = _safe_ratio(int(entry.get("success_count") or 0), int(entry.get("total_files") or 0))
    entry["failed_rate"] = _safe_ratio(int(entry.get("failed_count") or 0), int(entry.get("total_files") or 0))
    entry["empty_rate"] = _safe_ratio(int(entry.get("empty_count") or 0), int(entry.get("total_files") or 0))
    entry["avg_input_text_chars_per_doc"] = _safe_ratio(
        int(entry.get("input_text_chars") or 0),
        int(entry.get("document_count") or 0),
    )
    entry["avg_indexed_chunks_per_doc"] = _safe_ratio(
        int(entry.get("indexed_chunks") or 0),
        int(entry.get("document_count") or 0),
    )
    entry["nodes_without_embedding_rate"] = _safe_ratio(
        int(entry.get("nodes_without_embedding_count") or 0),
        int(entry.get("node_count") or 0),
    )
    entry["quality_signal_tags"] = _build_import_quality_signal_tags(entry)
    return entry


def summarize_import_results(
    import_results: dict[str, dict[str, Any]],
    *,
    kb_modalities: dict[str, str] | None = None,
) -> dict[str, Any]:
    """汇总导入结果，并按知识库与模态聚合 OCR 等诊断指标。"""
    kb_breakdown: dict[str, dict[str, Any]] = {}
    modality_breakdown: dict[str, dict[str, Any]] = {}

    total_files = 0
    total_success_count = 0
    total_failed_count = 0
    total_empty_count = 0
    total_indexed_chunks = 0
    total_document_count = 0
    total_node_count = 0
    total_nodes_with_embedding_count = 0
    total_nodes_without_embedding_count = 0
    total_input_text_chars = 0
    total_ocr_success_count = 0
    total_ocr_no_text_count = 0
    total_ocr_failed_count = 0
    total_ocr_skipped_count = 0
    total_indexed_from_ocr_count = 0
    total_embedded_ocr_attempted_count = 0
    total_embedded_ocr_success_count = 0
    total_embedded_ocr_no_text_count = 0
    total_embedded_ocr_failed_count = 0
    total_embedded_ocr_skipped_count = 0
    total_embedded_indexed_from_ocr_count = 0
    total_dependency_missing_count = 0
    total_asset_registered_count = 0
    total_import_ms = 0.0

    for kb_id, result in sorted(import_results.items()):
        diagnostics = dict(result.get("diagnostics") or {})
        display_summary = dict(result.get("display_summary") or {})
        files = list(result.get("files") or [])
        modality = str((kb_modalities or {}).get(kb_id, "unknown"))
        total_file_count = int(diagnostics.get("total_files") or len(files))
        success_count = int(result.get("success_count") or 0)
        failed_count = int(result.get("failed_count") or 0)
        empty_count = int(result.get("empty_count") or 0)
        indexed_chunks = int(result.get("indexed_chunks") or diagnostics.get("node_count") or 0)
        document_count = int(diagnostics.get("document_count") or 0)
        node_count = int(diagnostics.get("node_count") or 0)
        nodes_with_embedding_count = int(diagnostics.get("nodes_with_embedding_count") or 0)
        nodes_without_embedding_count = int(diagnostics.get("nodes_without_embedding_count") or 0)
        input_text_chars = int(diagnostics.get("input_text_chars") or 0)
        ocr_success_count = int(diagnostics.get("ocr_success_count") or 0)
        ocr_no_text_count = int(diagnostics.get("ocr_no_text_count") or 0)
        ocr_failed_count = int(diagnostics.get("ocr_failed_count") or 0)
        ocr_skipped_count = int(diagnostics.get("ocr_skipped_count") or 0)
        indexed_from_ocr_count = int(diagnostics.get("indexed_from_ocr_count") or 0)
        embedded_ocr_attempted_count = int(diagnostics.get("embedded_ocr_attempted_count") or 0)
        embedded_ocr_success_count = int(diagnostics.get("embedded_ocr_success_count") or 0)
        embedded_ocr_no_text_count = int(diagnostics.get("embedded_ocr_no_text_count") or 0)
        embedded_ocr_failed_count = int(diagnostics.get("embedded_ocr_failed_count") or 0)
        embedded_ocr_skipped_count = int(diagnostics.get("embedded_ocr_skipped_count") or 0)
        embedded_indexed_from_ocr_count = int(diagnostics.get("embedded_indexed_from_ocr_count") or 0)
        dependency_missing_count = int(diagnostics.get("dependency_missing_count") or 0)
        asset_registered_count = int(diagnostics.get("asset_registered_count") or 0)
        stage_timings = dict(diagnostics.get("stage_timings") or {})
        import_total_ms = float(stage_timings.get("total_ms") or 0.0)

        kb_breakdown[kb_id] = _finalize_import_metrics(
            {
                "kb_id": kb_id,
                "modality": modality,
                "receipt_id": result.get("receipt_id"),
                "import_mode": result.get("import_mode"),
                "headline": str(display_summary.get("headline") or ""),
                "total_files": total_file_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "empty_count": empty_count,
                "indexed_chunks": indexed_chunks,
                "document_count": document_count,
                "node_count": node_count,
                "nodes_with_embedding_count": nodes_with_embedding_count,
                "nodes_without_embedding_count": nodes_without_embedding_count,
                "input_text_chars": input_text_chars,
                "ocr_success_count": ocr_success_count,
                "ocr_no_text_count": ocr_no_text_count,
                "ocr_failed_count": ocr_failed_count,
                "ocr_skipped_count": ocr_skipped_count,
                "indexed_from_ocr_count": indexed_from_ocr_count,
                "embedded_ocr_attempted_count": embedded_ocr_attempted_count,
                "embedded_ocr_success_count": embedded_ocr_success_count,
                "embedded_ocr_no_text_count": embedded_ocr_no_text_count,
                "embedded_ocr_failed_count": embedded_ocr_failed_count,
                "embedded_ocr_skipped_count": embedded_ocr_skipped_count,
                "embedded_indexed_from_ocr_count": embedded_indexed_from_ocr_count,
                "dependency_missing_count": dependency_missing_count,
                "asset_registered_count": asset_registered_count,
                "import_total_ms": import_total_ms,
            }
        )

        modality_metrics = modality_breakdown.setdefault(
            modality,
            {
                "modality": modality,
                "kb_count": 0,
                "total_files": 0,
                "success_count": 0,
                "failed_count": 0,
                "empty_count": 0,
                "indexed_chunks": 0,
                "document_count": 0,
                "node_count": 0,
                "nodes_with_embedding_count": 0,
                "nodes_without_embedding_count": 0,
                "input_text_chars": 0,
                "ocr_success_count": 0,
                "ocr_no_text_count": 0,
                "ocr_failed_count": 0,
                "ocr_skipped_count": 0,
                "indexed_from_ocr_count": 0,
                "embedded_ocr_attempted_count": 0,
                "embedded_ocr_success_count": 0,
                "embedded_ocr_no_text_count": 0,
                "embedded_ocr_failed_count": 0,
                "embedded_ocr_skipped_count": 0,
                "embedded_indexed_from_ocr_count": 0,
                "dependency_missing_count": 0,
                "asset_registered_count": 0,
                "import_total_ms": 0.0,
            },
        )
        modality_metrics["kb_count"] += 1
        modality_metrics["total_files"] += total_file_count
        modality_metrics["success_count"] += success_count
        modality_metrics["failed_count"] += failed_count
        modality_metrics["empty_count"] += empty_count
        modality_metrics["indexed_chunks"] += indexed_chunks
        modality_metrics["document_count"] += document_count
        modality_metrics["node_count"] += node_count
        modality_metrics["nodes_with_embedding_count"] += nodes_with_embedding_count
        modality_metrics["nodes_without_embedding_count"] += nodes_without_embedding_count
        modality_metrics["input_text_chars"] += input_text_chars
        modality_metrics["ocr_success_count"] += ocr_success_count
        modality_metrics["ocr_no_text_count"] += ocr_no_text_count
        modality_metrics["ocr_failed_count"] += ocr_failed_count
        modality_metrics["ocr_skipped_count"] += ocr_skipped_count
        modality_metrics["indexed_from_ocr_count"] += indexed_from_ocr_count
        modality_metrics["embedded_ocr_attempted_count"] += embedded_ocr_attempted_count
        modality_metrics["embedded_ocr_success_count"] += embedded_ocr_success_count
        modality_metrics["embedded_ocr_no_text_count"] += embedded_ocr_no_text_count
        modality_metrics["embedded_ocr_failed_count"] += embedded_ocr_failed_count
        modality_metrics["embedded_ocr_skipped_count"] += embedded_ocr_skipped_count
        modality_metrics["embedded_indexed_from_ocr_count"] += embedded_indexed_from_ocr_count
        modality_metrics["dependency_missing_count"] += dependency_missing_count
        modality_metrics["asset_registered_count"] += asset_registered_count
        modality_metrics["import_total_ms"] += import_total_ms

        total_files += total_file_count
        total_success_count += success_count
        total_failed_count += failed_count
        total_empty_count += empty_count
        total_indexed_chunks += indexed_chunks
        total_document_count += document_count
        total_node_count += node_count
        total_nodes_with_embedding_count += nodes_with_embedding_count
        total_nodes_without_embedding_count += nodes_without_embedding_count
        total_input_text_chars += input_text_chars
        total_ocr_success_count += ocr_success_count
        total_ocr_no_text_count += ocr_no_text_count
        total_ocr_failed_count += ocr_failed_count
        total_ocr_skipped_count += ocr_skipped_count
        total_indexed_from_ocr_count += indexed_from_ocr_count
        total_embedded_ocr_attempted_count += embedded_ocr_attempted_count
        total_embedded_ocr_success_count += embedded_ocr_success_count
        total_embedded_ocr_no_text_count += embedded_ocr_no_text_count
        total_embedded_ocr_failed_count += embedded_ocr_failed_count
        total_embedded_ocr_skipped_count += embedded_ocr_skipped_count
        total_embedded_indexed_from_ocr_count += embedded_indexed_from_ocr_count
        total_dependency_missing_count += dependency_missing_count
        total_asset_registered_count += asset_registered_count
        total_import_ms += import_total_ms

    finalized_modality_breakdown = {
        modality: _finalize_import_metrics(metrics)
        for modality, metrics in sorted(modality_breakdown.items())
    }
    summary = _finalize_import_metrics(
        {
            "total_kbs": len(kb_breakdown),
            "total_files": total_files,
            "success_count": total_success_count,
            "failed_count": total_failed_count,
            "empty_count": total_empty_count,
            "total_success_count": total_success_count,
            "total_failed_count": total_failed_count,
            "total_empty_count": total_empty_count,
            "indexed_chunks": total_indexed_chunks,
            "total_indexed_chunks": total_indexed_chunks,
            "document_count": total_document_count,
            "total_document_count": total_document_count,
            "node_count": total_node_count,
            "total_node_count": total_node_count,
            "nodes_with_embedding_count": total_nodes_with_embedding_count,
            "total_nodes_with_embedding_count": total_nodes_with_embedding_count,
            "nodes_without_embedding_count": total_nodes_without_embedding_count,
            "total_nodes_without_embedding_count": total_nodes_without_embedding_count,
            "input_text_chars": total_input_text_chars,
            "total_input_text_chars": total_input_text_chars,
            "ocr_success_count": total_ocr_success_count,
            "total_ocr_success_count": total_ocr_success_count,
            "ocr_no_text_count": total_ocr_no_text_count,
            "total_ocr_no_text_count": total_ocr_no_text_count,
            "ocr_failed_count": total_ocr_failed_count,
            "total_ocr_failed_count": total_ocr_failed_count,
            "ocr_skipped_count": total_ocr_skipped_count,
            "total_ocr_skipped_count": total_ocr_skipped_count,
            "indexed_from_ocr_count": total_indexed_from_ocr_count,
            "total_indexed_from_ocr_count": total_indexed_from_ocr_count,
            "embedded_ocr_attempted_count": total_embedded_ocr_attempted_count,
            "total_embedded_ocr_attempted_count": total_embedded_ocr_attempted_count,
            "embedded_ocr_success_count": total_embedded_ocr_success_count,
            "total_embedded_ocr_success_count": total_embedded_ocr_success_count,
            "embedded_ocr_no_text_count": total_embedded_ocr_no_text_count,
            "total_embedded_ocr_no_text_count": total_embedded_ocr_no_text_count,
            "embedded_ocr_failed_count": total_embedded_ocr_failed_count,
            "total_embedded_ocr_failed_count": total_embedded_ocr_failed_count,
            "embedded_ocr_skipped_count": total_embedded_ocr_skipped_count,
            "total_embedded_ocr_skipped_count": total_embedded_ocr_skipped_count,
            "embedded_indexed_from_ocr_count": total_embedded_indexed_from_ocr_count,
            "total_embedded_indexed_from_ocr_count": total_embedded_indexed_from_ocr_count,
            "dependency_missing_count": total_dependency_missing_count,
            "total_dependency_missing_count": total_dependency_missing_count,
            "asset_registered_count": total_asset_registered_count,
            "total_asset_registered_count": total_asset_registered_count,
            "import_total_ms": total_import_ms,
            "total_import_ms": total_import_ms,
        }
    )
    summary["kb_breakdown"] = kb_breakdown
    summary["modality_breakdown"] = finalized_modality_breakdown
    return summary


def _group_case_results_by(case_results: list[dict[str, Any]], field_name: str) -> dict[str, list[dict[str, Any]]]:
    """按指定字段对 case 结果分组，供导入质量关联分析复用。"""
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in case_results:
        key = str(item.get(field_name, "unknown"))
        groups.setdefault(key, []).append(item)
    return groups


def _build_import_qa_alignment(
    import_breakdown: dict[str, dict[str, Any]],
    qa_breakdown: dict[str, dict[str, Any]],
    grouped_case_results: dict[str, list[dict[str, Any]]],
    *,
    id_field: str,
) -> dict[str, dict[str, Any]]:
    """对齐导入指标与 QA 指标，形成可报告的 KB / modality 视图。"""
    alignment: dict[str, dict[str, Any]] = {}
    for key, import_entry in sorted(import_breakdown.items()):
        qa_entry = dict(qa_breakdown.get(key) or {})
        case_items = list(grouped_case_results.get(key, []))
        total_cases = len(case_items)
        passed_cases = sum(1 for item in case_items if item.get("passed"))
        failed_cases = total_cases - passed_cases
        evidence_miss_cases = sum(1 for item in case_items if not item.get("evidence_hit", True))
        preview_failure_cases = sum(
            1 for item in case_items if item.get("preview_required") and not item.get("preview_resolvable")
        )
        source_count_mismatch_cases = sum(1 for item in case_items if not item.get("source_count_match", True))
        alignment[key] = {
            id_field: key,
            "modality": str(import_entry.get("modality") or (key if id_field == "modality" else "unknown")),
            "quality_signal_tags": list(import_entry.get("quality_signal_tags") or []),
            "signal_count": len(list(import_entry.get("quality_signal_tags") or [])),
            "qa_total_cases": total_cases,
            "qa_passed_cases": passed_cases,
            "qa_failed_cases": failed_cases,
            "qa_pass_rate": float(qa_entry.get("pass_rate", _safe_ratio(passed_cases, total_cases))),
            "qa_scope_pass_rate": float(qa_entry.get("scope_pass_rate", 1.0 if total_cases else 0.0)),
            "qa_evidence_hit_rate": float(qa_entry.get("evidence_hit_rate", 1.0 if total_cases else 0.0)),
            "qa_preview_resolvable_rate": float(
                qa_entry.get("preview_resolvable_rate", 1.0 if total_cases else 0.0)
            ),
            "evidence_miss_cases": evidence_miss_cases,
            "preview_failure_cases": preview_failure_cases,
            "source_count_mismatch_cases": source_count_mismatch_cases,
            "import_total_files": int(import_entry.get("total_files") or 0),
            "import_success_count": int(import_entry.get("success_count") or 0),
            "import_failed_count": int(import_entry.get("failed_count") or 0),
            "import_empty_count": int(import_entry.get("empty_count") or 0),
            "import_document_count": int(import_entry.get("document_count") or 0),
            "import_input_text_chars": int(import_entry.get("input_text_chars") or 0),
            "import_avg_input_text_chars_per_doc": float(import_entry.get("avg_input_text_chars_per_doc") or 0.0),
            "import_nodes_without_embedding_count": int(import_entry.get("nodes_without_embedding_count") or 0),
            "import_nodes_without_embedding_rate": float(import_entry.get("nodes_without_embedding_rate") or 0.0),
            "import_total_ocr_failed_count": int(import_entry.get("total_ocr_failed_count") or 0),
            "import_total_ocr_no_text_count": int(import_entry.get("total_ocr_no_text_count") or 0),
            "import_dependency_missing_count": int(import_entry.get("dependency_missing_count") or 0),
            "import_asset_registered_without_index_count": int(
                import_entry.get("asset_registered_without_index_count") or 0
            ),
        }
    return alignment


def build_import_qa_correlation(
    import_summary: dict[str, Any] | None,
    *,
    breakdowns: dict[str, Any] | None = None,
    case_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """把导入质量弱信号与 QA 结果按 KB / 模态对齐，便于测试报告解释。"""
    if not isinstance(import_summary, dict):
        return {
            "weak_signal_kb_count": 0,
            "weak_signal_kb_ids": [],
            "weak_signal_modality_count": 0,
            "weak_signal_modalities": [],
            "signal_breakdown": {},
            "kb_alignment": {},
            "modality_alignment": {},
        }

    resolved_breakdowns = dict(breakdowns or {})
    resolved_case_results = list(case_results or [])
    kb_alignment = _build_import_qa_alignment(
        dict(import_summary.get("kb_breakdown") or {}),
        dict(resolved_breakdowns.get("kb_id") or {}),
        _group_case_results_by(resolved_case_results, "kb_id"),
        id_field="kb_id",
    )
    modality_alignment = _build_import_qa_alignment(
        dict(import_summary.get("modality_breakdown") or {}),
        dict(resolved_breakdowns.get("modality") or {}),
        _group_case_results_by(resolved_case_results, "modality"),
        id_field="modality",
    )

    signal_breakdown: dict[str, dict[str, Any]] = {}
    for item in kb_alignment.values():
        signal_tags = list(item.get("quality_signal_tags") or [])
        if not signal_tags:
            continue
        for signal in signal_tags:
            aggregate = signal_breakdown.setdefault(
                signal,
                {
                    "kb_count": 0,
                    "kb_ids": [],
                    "qa_case_count": 0,
                    "qa_passed_cases": 0,
                    "qa_failed_cases": 0,
                    "evidence_miss_cases": 0,
                    "preview_failure_cases": 0,
                    "source_count_mismatch_cases": 0,
                },
            )
            aggregate["kb_count"] += 1
            aggregate["kb_ids"].append(item["kb_id"])
            aggregate["qa_case_count"] += int(item.get("qa_total_cases") or 0)
            aggregate["qa_passed_cases"] += int(item.get("qa_passed_cases") or 0)
            aggregate["qa_failed_cases"] += int(item.get("qa_failed_cases") or 0)
            aggregate["evidence_miss_cases"] += int(item.get("evidence_miss_cases") or 0)
            aggregate["preview_failure_cases"] += int(item.get("preview_failure_cases") or 0)
            aggregate["source_count_mismatch_cases"] += int(item.get("source_count_mismatch_cases") or 0)

    for signal, aggregate in signal_breakdown.items():
        aggregate["kb_ids"] = sorted(set(aggregate["kb_ids"]))
        aggregate["qa_pass_rate"] = _safe_ratio(
            int(aggregate.get("qa_passed_cases") or 0),
            int(aggregate.get("qa_case_count") or 0),
        )

    weak_signal_kb_ids = [key for key, item in kb_alignment.items() if item.get("quality_signal_tags")]
    weak_signal_modalities = [key for key, item in modality_alignment.items() if item.get("quality_signal_tags")]
    return {
        "weak_signal_kb_count": len(weak_signal_kb_ids),
        "weak_signal_kb_ids": weak_signal_kb_ids,
        "weak_signal_modality_count": len(weak_signal_modalities),
        "weak_signal_modalities": weak_signal_modalities,
        "signal_breakdown": dict(sorted(signal_breakdown.items())),
        "kb_alignment": kb_alignment,
        "modality_alignment": modality_alignment,
    }


def _resolve_expected_case_passed(case: dict[str, Any]) -> bool:
    """????????? case ????????"""
    expected_case_passed = case.get("expected_case_passed")
    if expected_case_passed is None:
        return True
    return bool(expected_case_passed)


def _resolve_actual_failure_stage(report: dict[str, Any]) -> str | None:
    """? case ?????????????????????"""
    if report.get("passed"):
        return None
    stage = str(report.get("failure_stage") or "").strip()
    if stage:
        return stage
    return "quality_gate"


def build_diagnostic_summary(
    cases: list[dict[str, Any]],
    case_results: list[dict[str, Any]],
    import_qa_correlation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """?? diagnostic ??????????????????"""
    reports_by_case_id = {str(item.get("case_id") or ""): item for item in case_results}
    weak_signal_counter: Counter[str] = Counter()
    weak_signal_case_ids: list[str] = []
    comparisons: list[dict[str, Any]] = []
    mismatch_cases: list[dict[str, Any]] = []
    expectation_matched_cases = 0

    for case in cases:
        case_id = str(case["case_id"])
        report = reports_by_case_id.get(case_id, {})
        expected_passed = _resolve_expected_case_passed(case)
        actual_passed = bool(report.get("passed"))
        expected_failure_stage = case.get("expected_failure_stage")
        actual_failure_stage = _resolve_actual_failure_stage(report)
        stage_matches = expected_failure_stage is None or str(expected_failure_stage) == str(actual_failure_stage)
        expectation_matches = actual_passed == expected_passed and stage_matches
        if expectation_matches:
            expectation_matched_cases += 1

        weak_signal_tags = [str(item) for item in list(case.get("weak_signal_tags") or [])]
        if weak_signal_tags:
            weak_signal_case_ids.append(case_id)
            weak_signal_counter.update(weak_signal_tags)

        comparison = {
            "case_id": case_id,
            "kb_id": str(case.get("kb_id") or report.get("kb_id") or ""),
            "modality": str(case.get("modality") or report.get("modality") or "unknown"),
            "weak_signal_tags": weak_signal_tags,
            "expected_case_passed": expected_passed,
            "actual_case_passed": actual_passed,
            "expected_failure_stage": expected_failure_stage,
            "actual_failure_stage": actual_failure_stage,
            "expectation_matches": expectation_matches,
            "failure_message": str(report.get("failure_message") or ""),
        }
        comparisons.append(comparison)
        if not expectation_matches:
            mismatch_cases.append(comparison)

    resolved_import_correlation = dict(import_qa_correlation or {})
    signal_breakdown = dict(resolved_import_correlation.get("signal_breakdown") or {})
    return {
        "total_cases": len(cases),
        "expected_passed_cases": sum(1 for case in cases if _resolve_expected_case_passed(case)),
        "expected_failed_cases": sum(1 for case in cases if not _resolve_expected_case_passed(case)),
        "actual_passed_cases": sum(1 for item in case_results if item.get("passed")),
        "actual_failed_cases": sum(1 for item in case_results if not item.get("passed")),
        "expectation_matched_cases": expectation_matched_cases,
        "expectation_mismatched_cases": len(mismatch_cases),
        "case_expectation_match_rate": _safe_ratio(expectation_matched_cases, len(cases)),
        "weak_signal_case_count": len(weak_signal_case_ids),
        "weak_signal_case_ids": weak_signal_case_ids,
        "weak_signal_breakdown": dict(sorted(weak_signal_counter.items())),
        "weak_signal_kb_count": int(resolved_import_correlation.get("weak_signal_kb_count") or 0),
        "weak_signal_kb_ids": list(resolved_import_correlation.get("weak_signal_kb_ids") or []),
        "weak_signal_modality_count": int(resolved_import_correlation.get("weak_signal_modality_count") or 0),
        "weak_signal_modalities": list(resolved_import_correlation.get("weak_signal_modalities") or []),
        "signal_breakdown": signal_breakdown,
        "comparisons": comparisons,
        "mismatch_cases": mismatch_cases,
    }


def evaluate_diagnostic_gates(summary: dict[str, Any], schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """?? diagnostic_gates ????????????"""
    gate_results: dict[str, dict[str, Any]] = {}
    diagnostic_gates = dict(schema.get("diagnostic_gates") or {})
    for gate_name, minimum in diagnostic_gates.items():
        if gate_name == "required_signal_tags":
            actual_tags = sorted(dict(summary.get("signal_breakdown") or {}).keys())
            required_tags = [str(item) for item in list(minimum or [])]
            gate_results[gate_name] = {
                "metric": "signal_breakdown",
                "actual": actual_tags,
                "required": required_tags,
                "passed": all(tag in actual_tags for tag in required_tags),
            }
            continue

        metric_name = DIAGNOSTIC_GATE_FIELD_MAP[gate_name]
        actual = float(summary.get(metric_name, 0.0))
        gate_results[gate_name] = {
            "metric": metric_name,
            "actual": actual,
            "minimum": float(minimum),
            "passed": actual >= float(minimum),
        }
    return gate_results


def _extract_preview_payload(response: Any) -> dict[str, Any] | None:
    """? preview API ??????? data ???"""
    if response.status_code != 200:
        return None
    body = response.json()
    if not isinstance(body, dict):
        return None
    data = body.get("data")
    return data if isinstance(data, dict) else None


def _merge_preview_payloads(preview_payloads: Iterable[dict[str, Any] | None]) -> dict[str, Any] | None:
    """?????? preview??? cross-document case ??????"""
    normalized = [item for item in preview_payloads if isinstance(item, dict)]
    if not normalized:
        return None

    merged = dict(normalized[0])
    excerpts = [str(item.get("excerpt", "")).strip() for item in normalized if str(item.get("excerpt", "")).strip()]
    if excerpts:
        merged["excerpt"] = "\n".join(excerpts)
    merged["doc_ids"] = [str(item.get("doc_id")) for item in normalized if item.get("doc_id")]
    merged["preview_locators"] = [item.get("preview_locator") for item in normalized if item.get("preview_locator") is not None]
    merged["preview_count"] = len(normalized)
    return merged


def _build_transport_failure_report(
    case: dict[str, Any],
    *,
    stage: str,
    status_code: int | None,
    message: str,
    preview_requested: bool,
    history_turns: list[str] | None = None,
) -> dict[str, Any]:
    """在 chat 或 preview 请求失败时构造统一失败报告。"""
    expected_source_count = int(case.get("expected_source_count", 0))
    return _attach_history_metadata(
        {
            "case_id": case["case_id"],
            "category": case["category"],
            "modality": case["modality"],
            "difficulty": case["difficulty"],
            "answer_style": case["answer_style"],
            "kb_id": case["kb_id"],
            "question": case["question"],
            "answerable": bool(case.get("answerable")),
            "judge_focus": list(case.get("judge_focus", [])),
            "scope_passed": False,
            "expected_kb_ids": [case["kb_id"]],
            "keypoint_total": len(case.get("expected_keypoints", [])),
            "keypoint_hits": [],
            "keypoint_missed": list(case.get("expected_keypoints", [])),
            "keypoint_coverage": 0.0,
            "blocked_term_total": len(case.get("forbidden_terms", [])),
            "blocked_term_hits": [],
            "blocked_term_clean": True,
            "forbidden_term_clean_rate": 1.0,
            "expected_source_count": expected_source_count,
            "actual_source_count": 0,
            "actual_evidence_count": 0,
            "source_count_match": expected_source_count == 0,
            "expected_doc": case["source_doc"] if case.get("answerable") else None,
            "required_evidence_docs": list(case.get("required_evidence_docs", [])),
            "returned_titles": [],
            "evidence_hit": False if expected_source_count > 0 else True,
            "preview_required": bool(case.get("preview_required")) and expected_source_count > 0,
            "preview_resolvable": False if case.get("preview_required") and expected_source_count > 0 else True,
            "preview_term_total": 0,
            "preview_term_hits": [],
            "preview_term_coverage": 0.0 if case.get("preview_required") and expected_source_count > 0 else 1.0,
            "passed": False,
            "response_status_code": status_code,
            "preview_status_code": None,
            "preview_requested": preview_requested,
            "failure_stage": stage,
            "failure_message": message,
        },
        history_turns,
    )


def build_eval_case_report(
    case: dict[str, Any],
    payload: dict[str, Any],
    *,
    preview_payload: dict[str, Any] | None = None,
    response_status_code: int = 200,
    preview_status_code: int | None = None,
    preview_requested: bool = False,
    history_turns: list[str] | None = None,
) -> dict[str, Any]:
    """把单个 case 的预览需求规整为布尔值。"""
    report = build_chat_case_report(
        _normalize_eval_case(case),
        payload,
        expected_kb_ids=[case["kb_id"]],
        expected_scope_type=str(case["expected_scope_type"]),
        expected_effective_scope_type=str(case["expected_scope_type"]),
        expected_default_deny=False,
        expected_isolation_level=str(case["expected_isolation_level"]),
        preview_payload=preview_payload,
        required_evidence_docs=list(case.get("required_evidence_docs", [])),
        preview_required=bool(case.get("preview_required")) and int(case.get("expected_source_count", 0)) > 0,
    )
    report.update(
        {
            "modality": case["modality"],
            "difficulty": case["difficulty"],
            "answer_style": case["answer_style"],
            "kb_id": case["kb_id"],
            "question": case["question"],
            "answerable": bool(case.get("answerable")),
            "judge_focus": list(case.get("judge_focus", [])),
            "response_status_code": response_status_code,
            "preview_status_code": preview_status_code,
            "preview_requested": preview_requested,
            "failure_stage": None,
            "failure_message": "",
        }
    )
    return _attach_history_metadata(report, history_turns)


def evaluate_run_gates(summary: dict[str, Any], schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """根据 schema 中的 run_gates 生成运行门槛结果。"""
    gate_results: dict[str, dict[str, Any]] = {}
    for gate_name, minimum in schema.get("run_gates", {}).items():
        metric_name = RUN_GATE_FIELD_MAP[gate_name]
        actual = float(summary.get(metric_name, 0.0))
        gate_results[gate_name] = {
            "metric": metric_name,
            "actual": actual,
            "minimum": float(minimum),
            "passed": actual >= float(minimum),
        }
    return gate_results


def _build_failures(reports: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """执行一组问答 case 并输出完整评测报告。"""
    failures: list[dict[str, Any]] = []
    for report in reports:
        if report.get("passed"):
            continue
        failures.append(
            {
                "case_id": report["case_id"],
                "kb_id": report["kb_id"],
                "modality": report["modality"],
                "difficulty": report["difficulty"],
                "category": report["category"],
                "failure_stage": report.get("failure_stage") or "quality_gate",
                "failure_message": report.get("failure_message") or "contract or metric mismatch",
                "keypoint_missed": list(report.get("keypoint_missed", [])),
                "blocked_term_hits": list(report.get("blocked_term_hits", [])),
                "returned_titles": list(report.get("returned_titles", [])),
                "answer": str(report.get("answer") or ""),
                "preview_excerpt": str(report.get("preview_excerpt") or ""),
                "source_count_match": bool(report.get("source_count_match")),
                "evidence_hit": bool(report.get("evidence_hit")),
                "preview_resolvable": bool(report.get("preview_resolvable")),
                "preview_requested": bool(report.get("preview_requested")),
                "response_status_code": report.get("response_status_code"),
                "preview_status_code": report.get("preview_status_code"),
            }
        )
    return failures


def run_chat_eval_cases(
    client: TestClient,
    cases: list[dict[str, Any]],
    schema: dict[str, Any],
    *,
    dataset_name: str | None = None,
) -> dict[str, Any]:
    """执行 eval case 的 chat / preview 链路，并支持可选的同 session follow-up 预热。"""
    reports: list[dict[str, Any]] = []

    for case in cases:
        session_id = f"eval::{case['case_id']}"
        history_turns = _normalize_history_turns(case)
        chat_service.clear_history(session_id)

        prewarm_failed = False
        for turn_index, history_turn in enumerate(history_turns, start=1):
            prewarm_response = client.post(
                "/api/chat/query",
                json={
                    "question": history_turn,
                    "session_id": session_id,
                    "kb_ids": [case["kb_id"]],
                },
            )
            if prewarm_response.status_code != 200:
                body = (
                    prewarm_response.json()
                    if prewarm_response.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                message = str(body.get("detail") or body.get("message") or prewarm_response.text)
                reports.append(
                    _build_transport_failure_report(
                        case,
                        stage="chat_query",
                        status_code=prewarm_response.status_code,
                        message=f"history prewarm turn {turn_index} failed: {message}",
                        preview_requested=False,
                        history_turns=history_turns,
                    )
                )
                prewarm_failed = True
                break

            prewarm_body = prewarm_response.json()
            prewarm_payload = prewarm_body.get("data") if isinstance(prewarm_body, dict) else None
            if not isinstance(prewarm_payload, dict):
                reports.append(
                    _build_transport_failure_report(
                        case,
                        stage="chat_query",
                        status_code=prewarm_response.status_code,
                        message=f"history prewarm turn {turn_index} returned no data payload",
                        preview_requested=False,
                        history_turns=history_turns,
                    )
                )
                prewarm_failed = True
                break

        if prewarm_failed:
            continue

        response = client.post(
            "/api/chat/query",
            json={
                "question": case["question"],
                "session_id": session_id,
                "kb_ids": [case["kb_id"]],
            },
        )
        if response.status_code != 200:
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            message = str(body.get("detail") or body.get("message") or response.text)
            reports.append(
                _build_transport_failure_report(
                    case,
                    stage="chat_query",
                    status_code=response.status_code,
                    message=message,
                    preview_requested=False,
                    history_turns=history_turns,
                )
            )
            continue

        body = response.json()
        payload = body.get("data") if isinstance(body, dict) else None
        if not isinstance(payload, dict):
            reports.append(
                _build_transport_failure_report(
                    case,
                    stage="chat_query",
                    status_code=response.status_code,
                    message="response data is missing",
                    preview_requested=False,
                    history_turns=history_turns,
                )
            )
            continue

        preview_payload: dict[str, Any] | None = None
        preview_status_code: int | None = None
        preview_requested = False

        if bool(case.get("preview_required")) and int(case.get("expected_source_count", 0)) > 0:
            evidence_items = list(payload.get("evidence", []))
            if evidence_items:
                preview_requested = True
                preview_payloads: list[dict[str, Any]] = []
                preview_failed = False
                for evidence_item in evidence_items:
                    preview_response = client.post(
                        "/api/kb/preview",
                        json={
                            "kb_id": case["kb_id"],
                            "evidence_id": evidence_item.get("id"),
                            "preview_locator": evidence_item.get("preview_locator"),
                        },
                    )
                    preview_status_code = preview_response.status_code
                    preview_item = _extract_preview_payload(preview_response)
                    if preview_status_code != 200 or preview_item is None:
                        preview_body = (
                            preview_response.json()
                            if preview_response.headers.get("content-type", "").startswith("application/json")
                            else {}
                        )
                        message = str(preview_body.get("detail") or preview_body.get("message") or preview_response.text)
                        reports.append(
                            _build_transport_failure_report(
                                case,
                                stage="preview",
                                status_code=preview_status_code,
                                message=message,
                                preview_requested=True,
                                history_turns=history_turns,
                            )
                        )
                        preview_failed = True
                        break
                    preview_payloads.append(preview_item)
                if preview_failed:
                    continue
                preview_payload = _merge_preview_payloads(preview_payloads)
                if preview_payload is None:
                    reports.append(
                        _build_transport_failure_report(
                            case,
                            stage="preview",
                            status_code=preview_status_code,
                            message="preview payload missing data",
                            preview_requested=True,
                            history_turns=history_turns,
                        )
                    )
                    continue

        reports.append(
            build_eval_case_report(
                case,
                payload,
                preview_payload=preview_payload,
                response_status_code=response.status_code,
                preview_status_code=preview_status_code,
                preview_requested=preview_requested,
                history_turns=history_turns,
            )
        )

    suite_summary = summarize_chat_case_reports(reports)
    refusal_summary = build_refusal_summary(reports, schema)
    negative_contract_summary = build_negative_contract_summary(reports, schema)
    run_gates = evaluate_run_gates(suite_summary, schema)
    contract_gates = evaluate_contract_gates(refusal_summary, negative_contract_summary)
    failures = _build_failures(reports)
    failure_stage_breakdown = dict(sorted(Counter(item["failure_stage"] for item in failures).items()))
    preview_required_cases = sum(1 for item in reports if item.get("preview_required"))
    preview_requested_cases = sum(1 for item in reports if item.get("preview_requested"))
    evaluation_mode = str(schema.get("evaluation_mode") or "healthy")
    return {
        "dataset_name": dataset_name or schema.get("dataset_name", "chat_eval"),
        "evaluation_mode": evaluation_mode,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "suite_summary": suite_summary,
        "refusal_summary": refusal_summary,
        "negative_contract_summary": negative_contract_summary,
        "run_gates": run_gates,
        "contract_gates": contract_gates,
        "run_passed": evaluate_report_run_passed(
            evaluation_mode=evaluation_mode,
            suite_summary=suite_summary,
            run_gates=run_gates,
            contract_gates=contract_gates,
        ),
        "breakdowns": {
            "modality": _build_breakdown(reports, "modality"),
            "difficulty": _build_breakdown(reports, "difficulty"),
            "answer_style": _build_breakdown(reports, "answer_style"),
            "category": _build_breakdown(reports, "category"),
            "kb_id": _build_breakdown(reports, "kb_id"),
        },
        "preview_stats": {
            "requested_cases": preview_requested_cases,
            "required_cases": preview_required_cases,
            "skipped_cases": max(preview_required_cases - preview_requested_cases, 0),
        },
        "failure_stage_breakdown": failure_stage_breakdown,
        "case_results": reports,
        "failures": failures,
    }



def write_eval_json_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """将评测结果写入 JSON 报告。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _format_confidence_interval(interval: dict[str, Any] | None) -> str:
    """格式化 Wilson 置信区间，供 Markdown 报告复用。"""
    if not interval:
        return "-"
    low = float(interval.get("low", 0.0))
    high = float(interval.get("high", 0.0))
    return f"[{low:.3f}, {high:.3f}]"


def _render_table(rows: list[list[str]], headers: list[str]) -> str:
    """渲染 Markdown 表格。"""
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _format_contract_gate_detail(item: dict[str, Any]) -> str:
    """格式化 Contract Gate 的缺口细节。"""
    detail = dict(item).get("detail")
    if detail is not None:
        return json.dumps(detail, ensure_ascii=False)
    return json.dumps(dict(item).get("missing", []), ensure_ascii=False)


def build_eval_markdown_report(report: dict[str, Any]) -> str:
    """?????????? Markdown ???"""
    summary = dict(report.get("suite_summary") or {})
    run_gates = dict(report.get("run_gates") or {})
    contract_gates = dict(report.get("contract_gates") or {})
    import_summary = dict(report.get("import_summary") or {})
    import_qa_correlation = dict(report.get("import_qa_correlation") or {})
    preview_stats = dict(report.get("preview_stats") or {})
    failure_stage_breakdown = dict(report.get("failure_stage_breakdown") or {})
    diagnostic_summary = dict(report.get("diagnostic_summary") or {})
    diagnostic_gates = dict(report.get("diagnostic_gates") or {})
    evaluation_mode = str(report.get("evaluation_mode") or "healthy")

    if import_summary and not import_qa_correlation:
        import_qa_correlation = build_import_qa_correlation(
            import_summary,
            breakdowns=dict(report.get("breakdowns") or {}),
            case_results=list(report.get("case_results") or []),
        )

    lines: list[str] = [
        f"# 问答评测报告：{report['dataset_name']}",
        "",
        f"- 运行时间：{report['run_at']}",
        f"- 评测模式：{evaluation_mode}",
        f"- 总用例数：{summary.get('total_cases', 0)}",
        f"- 通过用例：{summary.get('passed_cases', 0)}",
        f"- 失败用例：{summary.get('failed_cases', 0)}",
        f"- 运行结论：{'通过' if report.get('run_passed') else '失败'}",
        "",
        "## 1. Suite 摘要",
        "",
        _render_table(
            [
                ["pass_rate", f"{float(summary.get('pass_rate', 0.0)):.3f}"],
                ["pass_rate_ci95", _format_confidence_interval(summary.get("pass_rate_ci95"))],
                ["scope_pass_rate", f"{float(summary.get('scope_pass_rate', 0.0)):.3f}"],
                ["average_keypoint_coverage", f"{float(summary.get('average_keypoint_coverage', 0.0)):.3f}"],
                ["total_keypoints", str(summary.get("total_keypoints", 0))],
                ["matched_keypoints", str(summary.get("matched_keypoints", 0))],
                ["keypoint_hit_rate", f"{float(summary.get('keypoint_hit_rate', 0.0)):.3f}"],
                ["evidence_expected_cases", str(summary.get("evidence_expected_cases", 0))],
                ["evidence_hit_cases", str(summary.get("evidence_hit_cases", 0))],
                ["evidence_hit_rate", f"{float(summary.get('evidence_hit_rate', 0.0)):.3f}"],
                ["preview_required_cases", str(summary.get("preview_required_cases", 0))],
                ["preview_resolved_cases", str(summary.get("preview_resolved_cases", 0))],
                ["preview_resolvable_rate", f"{float(summary.get('preview_resolvable_rate', 0.0)):.3f}"],
                ["preview_term_total", str(summary.get("preview_term_total", 0))],
                ["preview_term_hits", str(summary.get("preview_term_hits", 0))],
                ["preview_term_hit_rate", f"{float(summary.get('preview_term_hit_rate', 0.0)):.3f}"],
                ["source_count_match_rate", f"{float(summary.get('source_count_match_rate', 0.0)):.3f}"],
                ["blocked_term_hit_cases", str(summary.get("blocked_term_hit_cases", 0))],
                ["forbidden_term_clean_rate", f"{float(summary.get('forbidden_term_clean_rate', 0.0)):.3f}"],
            ],
            ["指标", "数值"],
        ),
        "",
        "## 2. Run Gate",
        "",
    ]

    if run_gates:
        lines.append(
            _render_table(
                [
                    [
                        gate_name,
                        str(item.get("metric", "-")),
                        f"{float(item.get('actual', 0.0)):.3f}",
                        f"{float(item.get('minimum', 0.0)):.3f}",
                        "通过" if item.get("passed") else "失败",
                    ]
                    for gate_name, item in run_gates.items()
                ],
                ["Gate", "指标", "实际值", "阈值", "结果"],
            )
        )
    else:
        lines.append("本次运行未配置 Run Gate。")

    lines.extend(["", "### Contract Gate", ""])
    if contract_gates:
        lines.append(
            _render_table(
                [
                    [
                        gate_name,
                        str(item.get("metric", "-")),
                        f"{float(item.get('actual', 0.0)):.3f}",
                        f"{float(item.get('minimum', 0.0)):.3f}",
                        "通过" if item.get("passed") else "失败",
                        _format_contract_gate_detail(item),
                    ]
                    for gate_name, item in contract_gates.items()
                ],
                ["Gate", "指标", "实际值", "阈值", "结果", "details"],
            )
        )
    else:
        lines.append("本次运行未配置 Contract Gate。")
    lines.extend([
        "",
        "## 3. Preview 请求摘要",
        "",
        _render_table(
            [
                ["required_cases", str(preview_stats.get("required_cases", 0))],
                ["requested_cases", str(preview_stats.get("requested_cases", 0))],
                ["skipped_cases", str(preview_stats.get("skipped_cases", 0))],
            ],
            ["指标", "数值"],
        ),
        "",
    ])

    refusal_summary = dict(report.get("refusal_summary") or {})
    refusal_category_breakdown = dict(refusal_summary.get("category_breakdown") or {})
    refusal_modality_breakdown = dict(refusal_summary.get("modality_breakdown") or {})
    refusal_overview_rows = [
        ["refusal_case_count", str(refusal_summary.get("refusal_case_count", 0))],
        ["passed_refusal_cases", str(refusal_summary.get("passed_refusal_cases", 0))],
        ["failed_refusal_cases", str(refusal_summary.get("failed_refusal_cases", 0))],
        ["refusal_pass_rate", f"{float(refusal_summary.get('refusal_pass_rate', 0.0)):.3f}"],
        ["required_categories_passed", "通过" if refusal_summary.get("required_categories_passed") else "失败"],
        ["required_marker_coverage_passed", "通过" if refusal_summary.get("required_marker_coverage_passed") else "失败"],
        ["required_modalities_passed", "通过" if refusal_summary.get("required_modalities_passed") else "失败"],
        ["missing_required_categories", ", ".join(refusal_summary.get("missing_required_categories") or []) or "-"],
        [
            "required_categories_without_passed_cases",
            ", ".join(refusal_summary.get("required_categories_without_passed_cases") or []) or "-",
        ],
        ["missing_required_modalities", ", ".join(refusal_summary.get("missing_required_modalities") or []) or "-"],
        [
            "required_modalities_without_passed_cases",
            ", ".join(refusal_summary.get("required_modalities_without_passed_cases") or []) or "-",
        ],
    ]
    lines.extend([
        "## 4. Refusal 覆盖摘要",
        "",
        _render_table(refusal_overview_rows, ["指标", "数值"]),
        "",
    ])
    if refusal_category_breakdown:
        lines.extend([
            _render_table(
                [
                    [
                        category,
                        str(item.get("count", 0)),
                        str(item.get("passed", 0)),
                        str(item.get("failed", 0)),
                        f"{float(item.get('pass_rate', 0.0)):.3f}",
                        "; ".join(
                            f"{marker}:{marker_item.get('hit_cases', 0)}({'通过' if marker_item.get('covered') else '失败'})"
                            for marker, marker_item in dict(item.get("required_markers") or {}).items()
                        ) or "-",
                    ]
                    for category, item in refusal_category_breakdown.items()
                ],
                ["category", "count", "passed", "failed", "pass_rate", "required_markers"],
            ),
            "",
        ])
    if refusal_modality_breakdown:
        lines.extend([
            _render_table(
                [
                    [
                        modality,
                        str(item.get("count", 0)),
                        str(item.get("passed", 0)),
                        str(item.get("failed", 0)),
                        f"{float(item.get('pass_rate', 0.0)):.3f}",
                    ]
                    for modality, item in refusal_modality_breakdown.items()
                ],
                ["modality", "count", "passed", "failed", "pass_rate"],
            ),
            "",
        ])

    negative_contract_summary = dict(report.get("negative_contract_summary") or {})
    negative_contract_category_breakdown = dict(negative_contract_summary.get("category_breakdown") or {})
    negative_contract_modality_breakdown = dict(negative_contract_summary.get("modality_breakdown") or {})
    has_negative_contract_section = bool(
        negative_contract_summary.get("negative_contract_case_count", 0)
        or negative_contract_summary.get("required_categories")
        or negative_contract_summary.get("required_modalities")
        or negative_contract_category_breakdown
        or negative_contract_modality_breakdown
    )
    section_index = 5
    if has_negative_contract_section:
        negative_contract_rows = [
            ["negative_contract_case_count", str(negative_contract_summary.get("negative_contract_case_count", 0))],
            [
                "passed_negative_contract_cases",
                str(negative_contract_summary.get("passed_negative_contract_cases", 0)),
            ],
            [
                "failed_negative_contract_cases",
                str(negative_contract_summary.get("failed_negative_contract_cases", 0)),
            ],
            [
                "negative_contract_pass_rate",
                f"{float(negative_contract_summary.get('negative_contract_pass_rate', 0.0)):.3f}",
            ],
            [
                "required_categories_passed",
                "通过" if negative_contract_summary.get("required_categories_passed") else "失败",
            ],
            [
                "required_modalities_passed",
                "通过" if negative_contract_summary.get("required_modalities_passed") else "失败",
            ],
            [
                "missing_required_categories",
                ", ".join(negative_contract_summary.get("missing_required_categories") or []) or "-",
            ],
            [
                "required_categories_without_passed_cases",
                ", ".join(negative_contract_summary.get("required_categories_without_passed_cases") or []) or "-",
            ],
            [
                "missing_required_modalities",
                ", ".join(negative_contract_summary.get("missing_required_modalities") or []) or "-",
            ],
            [
                "required_modalities_without_passed_cases",
                ", ".join(negative_contract_summary.get("required_modalities_without_passed_cases") or []) or "-",
            ],
        ]
        lines.extend([
            "## 5. Negative Contract 覆盖摘要",
            "",
            _render_table(negative_contract_rows, ["指标", "数值"]),
            "",
        ])
        if negative_contract_category_breakdown:
            lines.extend([
                _render_table(
                    [
                        [
                            category,
                            str(item.get("count", 0)),
                            str(item.get("passed", 0)),
                            str(item.get("failed", 0)),
                            f"{float(item.get('pass_rate', 0.0)):.3f}",
                        ]
                        for category, item in negative_contract_category_breakdown.items()
                    ],
                    ["category", "count", "passed", "failed", "pass_rate"],
                ),
                "",
            ])
        if negative_contract_modality_breakdown:
            lines.extend([
                _render_table(
                    [
                        [
                            modality,
                            str(item.get("count", 0)),
                            str(item.get("passed", 0)),
                            str(item.get("failed", 0)),
                            f"{float(item.get('pass_rate', 0.0)):.3f}",
                        ]
                        for modality, item in negative_contract_modality_breakdown.items()
                    ],
                    ["modality", "count", "passed", "failed", "pass_rate"],
                ),
                "",
            ])
        section_index = 6
    if import_summary:
        lines.extend([
            f"## {section_index}. 导入基线摘要",
            "",
            _render_table(
                [
                    ["total_kbs", str(import_summary.get("total_kbs", 0))],
                    ["total_files", str(import_summary.get("total_files", 0))],
                    ["total_success_count", str(import_summary.get("total_success_count", 0))],
                    ["total_failed_count", str(import_summary.get("total_failed_count", 0))],
                    ["total_empty_count", str(import_summary.get("total_empty_count", 0))],
                    ["total_indexed_chunks", str(import_summary.get("total_indexed_chunks", 0))],
                    ["total_document_count", str(import_summary.get("total_document_count", 0))],
                    ["total_node_count", str(import_summary.get("total_node_count", 0))],
                    ["total_input_text_chars", str(import_summary.get("total_input_text_chars", 0))],
                    ["total_ocr_success_count", str(import_summary.get("total_ocr_success_count", 0))],
                    ["total_asset_registered_count", str(import_summary.get("total_asset_registered_count", 0))],
                    ["total_import_ms", f"{float(import_summary.get('total_import_ms', 0.0)):.2f}"],
                ],
                ["指标", "数值"],
            ),
            "",
        ])

        modality_rows = [
            [
                modality,
                str(item.get("kb_count", 0)),
                str(item.get("total_files", 0)),
                str(item.get("success_count", 0)),
                str(item.get("failed_count", 0)),
                str(item.get("empty_count", 0)),
                str(item.get("indexed_chunks", 0)),
                str(item.get("document_count", 0)),
                str(item.get("node_count", 0)),
                str(item.get("input_text_chars", 0)),
                str(item.get("ocr_success_count", 0)),
                str(item.get("asset_registered_count", 0)),
                f"{float(item.get('import_total_ms', 0.0)):.2f}",
            ]
            for modality, item in dict(import_summary.get("modality_breakdown") or {}).items()
        ]
        if modality_rows:
            lines.extend([
                _render_table(
                    modality_rows,
                    [
                        "modality",
                        "kb_count",
                        "total_files",
                        "success",
                        "failed",
                        "empty",
                        "indexed_chunks",
                        "document_count",
                        "node_count",
                        "input_text_chars",
                        "ocr_success_count",
                        "asset_registered_count",
                        "import_total_ms",
                    ],
                ),
                "",
            ])

        kb_rows = [
            [
                kb_id,
                str(item.get("modality", "unknown")),
                str(item.get("total_files", 0)),
                str(item.get("success_count", 0)),
                str(item.get("failed_count", 0)),
                str(item.get("empty_count", 0)),
                str(item.get("indexed_chunks", 0)),
                str(item.get("document_count", 0)),
                str(item.get("node_count", 0)),
                str(item.get("input_text_chars", 0)),
                str(item.get("ocr_success_count", 0)),
                str(item.get("asset_registered_count", 0)),
                f"{float(item.get('import_total_ms', 0.0)):.2f}",
            ]
            for kb_id, item in dict(import_summary.get("kb_breakdown") or {}).items()
        ]
        if kb_rows:
            lines.extend([
                _render_table(
                    kb_rows,
                    [
                        "kb_id",
                        "modality",
                        "total_files",
                        "success",
                        "failed",
                        "empty",
                        "indexed_chunks",
                        "document_count",
                        "node_count",
                        "input_text_chars",
                        "ocr_success_count",
                        "asset_registered_count",
                        "import_total_ms",
                    ],
                ),
                "",
            ])
        section_index += 1

    if import_summary or import_qa_correlation:
        lines.extend([
            f"## {section_index}. 导入质量与问答关联",
            "",
            _render_table(
                [
                    ["weak_signal_kb_count", str(import_qa_correlation.get("weak_signal_kb_count", 0))],
                    ["weak_signal_kb_ids", ", ".join(import_qa_correlation.get("weak_signal_kb_ids", [])) or "-"],
                    ["weak_signal_modality_count", str(import_qa_correlation.get("weak_signal_modality_count", 0))],
                    ["weak_signal_modalities", ", ".join(import_qa_correlation.get("weak_signal_modalities", [])) or "-"],
                ],
                ["指标", "数值"],
            ),
            "",
        ])

        signal_breakdown = dict(import_qa_correlation.get("signal_breakdown") or {})
        if not signal_breakdown:
            lines.extend(["本次运行未发现导入弱信号知识库。", ""])
        else:
            lines.extend([
                _render_table(
                    [
                        [
                            signal,
                            str(item.get("kb_count", 0)),
                            ", ".join(item.get("kb_ids", [])) or "-",
                            str(item.get("qa_case_count", 0)),
                            str(item.get("qa_failed_cases", 0)),
                            str(item.get("evidence_miss_cases", 0)),
                            str(item.get("preview_failure_cases", 0)),
                            str(item.get("source_count_mismatch_cases", 0)),
                            f"{float(item.get('qa_pass_rate', 0.0)):.3f}",
                        ]
                        for signal, item in signal_breakdown.items()
                    ],
                    [
                        "signal",
                        "kb_count",
                        "kb_ids",
                        "qa_case_count",
                        "qa_failed_cases",
                        "evidence_miss_cases",
                        "preview_failure_cases",
                        "source_count_mismatch_cases",
                        "qa_pass_rate",
                    ],
                ),
                "",
            ])

        kb_alignment = dict(import_qa_correlation.get("kb_alignment") or {})
        if kb_alignment:
            lines.extend([
                _render_table(
                    [
                        [
                            kb_id,
                            str(item.get("modality", "unknown")),
                            ", ".join(item.get("quality_signal_tags", [])) or "-",
                            str(item.get("qa_total_cases", 0)),
                            str(item.get("qa_failed_cases", 0)),
                            str(item.get("evidence_miss_cases", 0)),
                            str(item.get("preview_failure_cases", 0)),
                            f"{float(item.get('import_nodes_without_embedding_rate', 0.0)):.3f}",
                            str(item.get("import_total_ocr_failed_count", 0)),
                            str(item.get("import_total_ocr_no_text_count", 0)),
                            str(item.get("import_asset_registered_without_index_count", 0)),
                        ]
                        for kb_id, item in kb_alignment.items()
                    ],
                    [
                        "kb_id",
                        "modality",
                        "quality_signal_tags",
                        "qa_total_cases",
                        "qa_failed_cases",
                        "evidence_miss_cases",
                        "preview_failure_cases",
                        "import_nodes_without_embedding_rate",
                        "import_total_ocr_failed_count",
                        "import_total_ocr_no_text_count",
                        "import_asset_registered_without_index_count",
                    ],
                ),
                "",
            ])

        modality_alignment = dict(import_qa_correlation.get("modality_alignment") or {})
        if modality_alignment:
            lines.extend([
                _render_table(
                    [
                        [
                            modality,
                            ", ".join(item.get("quality_signal_tags", [])) or "-",
                            str(item.get("qa_total_cases", 0)),
                            str(item.get("qa_failed_cases", 0)),
                            str(item.get("evidence_miss_cases", 0)),
                            str(item.get("preview_failure_cases", 0)),
                            f"{float(item.get('import_nodes_without_embedding_rate', 0.0)):.3f}",
                            str(item.get("import_total_ocr_failed_count", 0)),
                            str(item.get("import_total_ocr_no_text_count", 0)),
                            str(item.get("import_asset_registered_without_index_count", 0)),
                        ]
                        for modality, item in modality_alignment.items()
                    ],
                    [
                        "modality",
                        "quality_signal_tags",
                        "qa_total_cases",
                        "qa_failed_cases",
                        "evidence_miss_cases",
                        "preview_failure_cases",
                        "import_nodes_without_embedding_rate",
                        "import_total_ocr_failed_count",
                        "import_total_ocr_no_text_count",
                        "import_asset_registered_without_index_count",
                    ],
                ),
                "",
            ])
        section_index += 1

    if evaluation_mode == "diagnostic" or diagnostic_summary or diagnostic_gates:
        lines.extend([
            f"## {section_index}. 诊断摘要",
            "",
            _render_table(
                [
                    ["total_cases", str(diagnostic_summary.get("total_cases", 0))],
                    ["expected_failed_cases", str(diagnostic_summary.get("expected_failed_cases", 0))],
                    ["actual_failed_cases", str(diagnostic_summary.get("actual_failed_cases", 0))],
                    ["case_expectation_match_rate", f"{float(diagnostic_summary.get('case_expectation_match_rate', 0.0)):.3f}"],
                    ["weak_signal_case_count", str(diagnostic_summary.get("weak_signal_case_count", 0))],
                    ["weak_signal_kb_count", str(diagnostic_summary.get("weak_signal_kb_count", 0))],
                    ["weak_signal_modality_count", str(diagnostic_summary.get("weak_signal_modality_count", 0))],
                ],
                ["指标", "数值"],
            ),
            "",
        ])

        weak_signal_breakdown = dict(diagnostic_summary.get("weak_signal_breakdown") or {})
        if weak_signal_breakdown:
            lines.extend([
                _render_table(
                    [[signal, str(count)] for signal, count in weak_signal_breakdown.items()],
                    ["weak_signal_tag", "case_count"],
                ),
                "",
            ])

        mismatch_cases = list(diagnostic_summary.get("mismatch_cases") or [])
        if mismatch_cases:
            lines.extend([
                _render_table(
                    [
                        [
                            item.get("case_id", "-"),
                            str(item.get("expected_case_passed")),
                            str(item.get("actual_case_passed")),
                            str(item.get("expected_failure_stage") or "-"),
                            str(item.get("actual_failure_stage") or "-"),
                            ", ".join(item.get("weak_signal_tags", [])) or "-",
                            item.get("failure_message", "") or "-",
                        ]
                        for item in mismatch_cases
                    ],
                    [
                        "case_id",
                        "expected_case_passed",
                        "actual_case_passed",
                        "expected_failure_stage",
                        "actual_failure_stage",
                        "weak_signal_tags",
                        "failure_message",
                    ],
                ),
                "",
            ])
        else:
            lines.extend(["本次诊断运行无预期偏差样本。", ""])
        section_index += 1

        lines.extend([f"## {section_index}. Diagnostic Gate", ""])
        if diagnostic_gates:
            diagnostic_rows = []
            for gate_name, item in diagnostic_gates.items():
                actual = item.get("actual")
                if isinstance(actual, list):
                    actual_text = ", ".join(str(value) for value in actual) or "-"
                else:
                    actual_text = f"{float(actual or 0.0):.3f}"
                minimum = item.get("minimum")
                if minimum is None:
                    minimum_text = ", ".join(str(value) for value in list(item.get("required") or [])) or "-"
                else:
                    minimum_text = f"{float(minimum):.3f}"
                diagnostic_rows.append(
                    [
                        gate_name,
                        str(item.get("metric", "-")),
                        actual_text,
                        minimum_text,
                        "通过" if item.get("passed") else "失败",
                    ]
                )
            lines.extend([
                _render_table(diagnostic_rows, ["Gate", "指标", "实际值", "阈值/要求", "结果"]),
                "",
            ])
        else:
            lines.extend(["本次运行未配置 Diagnostic Gate。", ""])
        section_index += 1

    for section_name, breakdown in dict(report.get("breakdowns") or {}).items():
        lines.extend([
            f"## {section_index}. {section_name} 分层统计",
            "",
            _render_table(
                [
                    [
                        key,
                        str(item.get("count", 0)),
                        str(item.get("passed", 0)),
                        str(item.get("failed", 0)),
                        f"{float(item.get('pass_rate', 0.0)):.3f}",
                        _format_confidence_interval(item.get("pass_rate_ci95")),
                        f"{float(item.get('scope_pass_rate', 0.0)):.3f}",
                        f"{float(item.get('average_keypoint_coverage', 0.0)):.3f}",
                        f"{float(item.get('keypoint_hit_rate', 0.0)):.3f}",
                        f"{float(item.get('evidence_hit_rate', 0.0)):.3f}",
                        f"{float(item.get('preview_resolvable_rate', 0.0)):.3f}",
                        f"{float(item.get('preview_term_hit_rate', 0.0)):.3f}",
                        f"{float(item.get('source_count_match_rate', 0.0)):.3f}",
                        f"{float(item.get('forbidden_term_clean_rate', 0.0)):.3f}",
                    ]
                    for key, item in dict(breakdown or {}).items()
                ],
                [
                    section_name,
                    "count",
                    "passed",
                    "failed",
                    "pass_rate",
                    "pass_rate_ci95",
                    "scope_pass_rate",
                    "average_keypoint_coverage",
                    "keypoint_hit_rate",
                    "evidence_hit_rate",
                    "preview_resolvable_rate",
                    "preview_term_hit_rate",
                    "source_count_match_rate",
                    "forbidden_term_clean_rate",
                ],
            ),
            "",
        ])
        section_index += 1

    lines.extend([f"## {section_index}. 失败阶段分布", ""])
    if failure_stage_breakdown:
        lines.extend([
            _render_table([[stage, str(count)] for stage, count in failure_stage_breakdown.items()], ["failure_stage", "count"]),
            "",
        ])
    else:
        lines.extend(["本次运行无失败阶段样本。", ""])
    section_index += 1

    failures = list(report.get("failures") or [])
    lines.extend([f"## {section_index}. 失败样本", ""])
    if failures:
        lines.extend([
            _render_table(
                [
                    [
                        item.get("case_id", "-"),
                        item.get("kb_id", "-"),
                        item.get("modality", "-"),
                        item.get("category", "-"),
                        item.get("difficulty", "-"),
                        item.get("failure_stage", "-"),
                        item.get("failure_message", "-"),
                        "<br>".join(item.get("keypoint_missed", [])) or "-",
                        "<br>".join(item.get("returned_titles", [])) or "-",
                        str(item.get("source_count_match")),
                        str(item.get("evidence_hit")),
                        str(item.get("preview_resolvable")),
                        (item.get("answer", "") or "-")[:160],
                        str(item.get("response_status_code") or "-"),
                        str(item.get("preview_status_code") or "-"),
                    ]
                    for item in failures
                ],
                [
                    "case_id",
                    "kb_id",
                    "modality",
                    "category",
                    "difficulty",
                    "failure_stage",
                    "failure_message",
                    "keypoint_missed",
                    "returned_titles",
                    "source_count_match",
                    "evidence_hit",
                    "preview_resolvable",
                    "answer_excerpt",
                    "response_status_code",
                    "preview_status_code",
                ],
            ),
            "",
        ])
    else:
        lines.extend(["本次运行无失败样本。", ""])
    return "\n".join(lines).strip() + "\n"
def write_eval_markdown_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """将评测结果写入 Markdown 报告。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_eval_markdown_report(report), encoding="utf-8")
    return path


def _format_gate_detail_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)



def _render_failed_gate_detail_lines(title: str, details: dict[str, Any] | None) -> list[str]:
    detail_items = dict(details or {})
    if not detail_items:
        return [f"- {title}：-", ""]

    lines = [f"- {title}："]
    for gate_name, item in detail_items.items():
        gate = dict(item or {})
        parts: list[str] = []
        for key in (
            "metric",
            "actual",
            "minimum",
            "required_count",
            "covered_count",
            "missing",
            "required_categories_without_passed_cases",
            "required_modalities_without_passed_cases",
            "detail",
        ):
            if key not in gate:
                continue
            value = gate.get(key)
            if value in (None, "", [], {}):
                continue
            parts.append(f"{key}={_format_gate_detail_value(value)}")
        lines.append(f"  - {gate_name}: {'; '.join(parts) or '-'}")
    lines.append("")
    return lines


def _pick_font(size: int = 28) -> ImageFont.ImageFont:
    """为评测图片 fixture 选择可用字体，避免不同环境完全失真。"""
    font, _ = load_first_available_font(size=size, candidates=FONT_CANDIDATES)
    return font


def _text_to_image_lines(text: str, *, width: int = 48, max_lines: int = 5) -> list[str]:
    """将 OCR 文本裁成适合图片渲染的多行内容。"""
    normalized = " ".join(str(text).split())
    if not normalized:
        return ["empty fixture"]

    words = normalized.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        proposed = word if not current else f"{current} {word}"
        if len(proposed) <= width:
            current = proposed
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or [normalized[:width]]


def _create_text_image(path: Path, lines: list[str], *, render_mode: str = "clean") -> None:
    """生成真实 PNG fixture，用于 image OCR semireal/import 回归。"""
    background = (255, 255, 255)
    foreground = (32, 32, 32)
    if render_mode == "low_contrast_rotated":
        background = (245, 244, 240)
        foreground = (112, 112, 112)

    image = Image.new("RGB", (1440, 960), color=background)
    draw = ImageDraw.Draw(image)
    font = _pick_font(30)
    y = 96
    for index, line in enumerate(lines):
        x = 72 if index % 2 == 0 else 96
        draw.text((x, y), line, fill=foreground, font=font)
        y += 132

    if render_mode == "low_contrast_rotated":
        for offset in range(80, 960, 56):
            draw.line((48, offset, 1392, offset), fill=(230, 229, 224), width=1)
        image = image.rotate(-1.4, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=background)
        image = image.filter(ImageFilter.GaussianBlur(radius=0.6))

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _create_text_pdf(path: Path, text: str) -> None:
    """生成可检索文字层 PDF fixture。"""
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(48, 48, 560, 780), text)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()


def _create_scanned_pdf(path: Path, lines: list[str]) -> None:
    """生成无文字层的扫描 PDF fixture，用于触发 OCR fallback。"""
    image = Image.new("RGB", (1600, 1200), color="white")
    draw = ImageDraw.Draw(image)
    font = _pick_font(28)
    y = 120
    for line in lines:
        draw.text((96, y), line, fill="black", font=font)
        y += 72

    image_path = path.with_suffix('.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(image_path)

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(36, 36, 559, 806), filename=str(image_path))
    document.save(path)
    document.close()
    image_path.unlink(missing_ok=True)


class EvalPDFSemirealIndexManager(SemirealIndexManager):
    """在 eval harness 中复用真实 PDFOCRReader 导入 PDF 样本。"""

    def __init__(self, kb_id: str, kb_dir: Path, import_catalog: dict[str, dict[str, Any]]) -> None:
        super().__init__(kb_id=kb_id, kb_dir=kb_dir)
        self.import_catalog = import_catalog

    def load_files(self, paths, chunk_size: int, chunk_overlap: int, kb_id: str | None = None, persist: bool = False):
        reader = PDFOCRReader()
        nodes = []
        input_text_chars = 0
        for raw_path in paths:
            path = Path(raw_path).resolve()
            payload = dict(self.import_catalog.get(path.name, {}) or {})
            source_kind = str(payload.get('source_kind') or 'text_layer')
            if payload.get('force_empty_text_document'):
                docs = [SimpleNamespace(text='', metadata={'page_label': '1'})]
            else:
                docs = reader.load_data(str(path))
            for doc in docs:
                metadata = dict(getattr(doc, 'metadata', {}) or {})
                node = self.register_text_document(
                    path=path,
                    text=str(doc.text),
                    kb_id=kb_id,
                    relative_path=path.relative_to(self.kb_dir).as_posix(),
                    title=path.name,
                    page_label=str(metadata.get('page_label') or '1'),
                    extra_metadata={
                        'source_type': 'pdf_ocr_fallback' if source_kind == 'scanned_pdf' else 'pdf_text_layer',
                        'mime_type': 'application/pdf',
                        'simulate_nodes_without_embedding': payload.get('simulate_nodes_without_embedding', False),
                        **metadata,
                    },
                )
                nodes.append(node)
                input_text_chars += len(str(doc.text))
        self._record_ingestion_diagnostics(
            document_count=len(nodes),
            input_text_chars=input_text_chars,
            node_count=len(nodes),
            nodes=nodes,
        )
        return nodes



class EvalV1SemirealHarness:
    """Build the semireal QA harness runtime."""

    def __init__(
        self,
        workspace: str | Path | None = None,
        *,
        import_catalog: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._workspace = Path(workspace).resolve() if workspace else None
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.base_dir: Path | None = None
        self.client: TestClient | None = None
        self.import_catalog = import_catalog or {
            "markdown": dict(BASE_MARKDOWN_IMPORTS),
            "pdf": dict(BASE_PDF_IMPORTS),
            "image_ocr": dict(BASE_IMAGE_IMPORTS),
        }
        self.managers: dict[str, SemirealIndexManager] = {}
        self.import_results: dict[str, dict[str, Any]] = {}
        self._saved_state: dict[str, Any] = {}
        self._old_cwd = Path.cwd()
        self._fake_pdf_ocr_impl = None

    def _select_import_entries(self, modality: str, kb_id: str) -> dict[str, Any]:
        catalog = dict(self.import_catalog.get(modality, {}) or {})
        if modality == "markdown":
            return catalog if kb_id == MARKDOWN_KB_ID else {}

        default_kb_id = PDF_KB_ID if modality == "pdf" else IMAGE_KB_ID
        selected: dict[str, Any] = {}
        for name, payload in catalog.items():
            if not isinstance(payload, dict):
                continue
            target_kb_id = str(payload.get("kb_id") or default_kb_id)
            if target_kb_id == kb_id:
                selected[name] = payload
        return selected


    def __enter__(self) -> "EvalV1SemirealHarness":
        if self._workspace is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="chat-eval-")
            self.base_dir = Path(self._temp_dir.name).resolve()
        else:
            self.base_dir = self._workspace
            self.base_dir.mkdir(parents=True, exist_ok=True)

        os.chdir(self.base_dir)
        self._save_state()
        self._install_runtime()
        self._seed_all_kbs()
        self.client = TestClient(app)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            self.client.close()
        self._restore_state()
        os.chdir(self._old_cwd)
        if self._temp_dir is not None:
            self._temp_dir.cleanup()

    def _save_state(self) -> None:
        self._saved_state = {
            "kb_registry": kb_service._registry,
            "asset_registry": asset_service._registry,
            "kb_ensure_models_ready": kb_service.runtime_state.ensure_models_ready,
            "kb_get_index_manager": kb_service.runtime_state.get_index_manager,
            "chat_ensure_index_loaded": chat_service.runtime_state.ensure_index_loaded,
            "chat_build_query_engine": chat_service.runtime_state.build_query_engine,
            "chat_get_index_manager": chat_service.runtime_state.get_index_manager,
            "chat_append_message": chat_service.append_chat_message,
            "kb_extract_image_ocr_result": kb_service._extract_image_ocr_result,
            "pdf_reader_ocr_pdf": PDFOCRReader._ocr_pdf,
        }

    def _restore_state(self) -> None:
        kb_service._registry = self._saved_state["kb_registry"]
        asset_service._registry = self._saved_state["asset_registry"]
        kb_service.runtime_state.ensure_models_ready = self._saved_state["kb_ensure_models_ready"]
        kb_service.runtime_state.get_index_manager = self._saved_state["kb_get_index_manager"]
        chat_service.runtime_state.ensure_index_loaded = self._saved_state["chat_ensure_index_loaded"]
        chat_service.runtime_state.build_query_engine = self._saved_state["chat_build_query_engine"]
        chat_service.runtime_state.get_index_manager = self._saved_state["chat_get_index_manager"]
        chat_service.append_chat_message = self._saved_state["chat_append_message"]
        kb_service._extract_image_ocr_result = self._saved_state["kb_extract_image_ocr_result"]
        PDFOCRReader._ocr_pdf = self._saved_state["pdf_reader_ocr_pdf"]

    def _install_runtime(self) -> None:
        registry = KBRegistry(storage_path=self.base_dir / "storage" / "kb_registry.json")
        asset_registry = KBAssetRegistry(base_dir=self.base_dir / "storage" / "kb_assets")
        kb_service._registry = registry
        asset_service._registry = asset_registry

        registry.create_kb(MARKDOWN_KB_ID, "Eval Markdown KB")
        registry.create_kb(PDF_KB_ID, "Eval PDF KB")
        if self._select_import_entries("pdf", PDF_ZERO_KB_ID):
            registry.create_kb(PDF_ZERO_KB_ID, "Eval Zero Text PDF KB")
        registry.create_kb(IMAGE_KB_ID, "Eval Image KB")

        self.managers[MARKDOWN_KB_ID] = SemirealIndexManager(kb_id=MARKDOWN_KB_ID, kb_dir=get_kb_data_dir(MARKDOWN_KB_ID, create=True))
        self.managers[PDF_KB_ID] = EvalPDFSemirealIndexManager(
            kb_id=PDF_KB_ID,
            kb_dir=get_kb_data_dir(PDF_KB_ID, create=True),
            import_catalog=self.import_catalog["pdf"],
        )
        if self._select_import_entries("pdf", PDF_ZERO_KB_ID):
            self.managers[PDF_ZERO_KB_ID] = EvalPDFSemirealIndexManager(
                kb_id=PDF_ZERO_KB_ID,
                kb_dir=get_kb_data_dir(PDF_ZERO_KB_ID, create=True),
                import_catalog=self.import_catalog["pdf"],
            )
        self.managers[IMAGE_KB_ID] = SemirealIndexManager(kb_id=IMAGE_KB_ID, kb_dir=get_kb_data_dir(IMAGE_KB_ID, create=True))

        original_pdf_ocr = self._saved_state["pdf_reader_ocr_pdf"]

        def fake_pdf_ocr(reader: PDFOCRReader, file_path):
            payload = self.import_catalog["pdf"].get(Path(file_path).name, {})
            if payload.get("source_kind") == "scanned_pdf":
                return str(payload["ocr_text"]).strip()
            return original_pdf_ocr(reader, file_path)

        self._fake_pdf_ocr_impl = fake_pdf_ocr
        PDFOCRReader._ocr_pdf = fake_pdf_ocr

        kb_service.runtime_state.ensure_models_ready = MagicMock(return_value=True)
        kb_service.runtime_state.get_index_manager = MagicMock(side_effect=lambda kb_id: self.managers[str(kb_id)])
        chat_service.runtime_state.ensure_index_loaded = MagicMock(return_value=True)
        chat_service.runtime_state.build_query_engine = MagicMock(side_effect=self._build_query_engine)
        chat_service.runtime_state.get_index_manager = MagicMock(side_effect=lambda kb_id=None: self.managers[str(kb_id)])
        kb_service._extract_image_ocr_result = self._fake_extract_image_ocr_result

    def _build_query_engine(self, kb_ids: list[str] | None = None, **kwargs: Any) -> SemirealQueryEngine:
        normalized = list(kb_ids or [])
        if len(normalized) != 1:
            raise ValueError(f"semireal eval expects exactly one kb_id, got: {normalized}")
        return SemirealQueryEngine(self.managers[normalized[0]])

    def _fake_extract_image_ocr_result(self, path: Path, content_type: str) -> dict[str, Any]:
        payload = self.import_catalog["image_ocr"][path.name]
        status = str(payload.get("ocr_status") or "success")
        text = str(payload.get("ocr_text") or "")
        error = payload.get("ocr_error")
        missing_dependency = payload.get("missing_dependency")
        dependency_status = payload.get("dependency_status")
        if status == "failed" and error is None:
            error = "mock image ocr failed"
        if missing_dependency is not None and dependency_status is None:
            dependency_status = "missing"
        return {
            "status": status,
            "text": text,
            "error": error,
            "attempted": bool(payload.get("ocr_attempted", True)),
            "engine": str(payload.get("ocr_engine") or "mock-paddleocr"),
            "missing_dependency": missing_dependency,
            "dependency_status": dependency_status,
            "ocr_init_ms": float(payload.get("ocr_init_ms") or 4.0),
            "ocr_load_image_ms": float(payload.get("ocr_load_image_ms") or 1.0),
            "ocr_predict_ms": float(payload.get("ocr_predict_ms") or 10.0),
            "ocr_total_ms": float(payload.get("ocr_total_ms") or 15.0),
        }

    def _seed_all_kbs(self) -> None:
        self.import_results[MARKDOWN_KB_ID] = self._import_markdown_kb(MARKDOWN_KB_ID)
        self.import_results[PDF_KB_ID] = self._import_pdf_kb(PDF_KB_ID)
        if PDF_ZERO_KB_ID in self.managers:
            self.import_results[PDF_ZERO_KB_ID] = self._import_pdf_kb(PDF_ZERO_KB_ID)
        self.import_results[IMAGE_KB_ID] = self._import_image_kb(IMAGE_KB_ID)

    def _import_markdown_kb(self, kb_id: str) -> dict[str, Any]:
        uploads = []
        relative_paths = []
        for name, relative_path in self._select_import_entries("markdown", kb_id).items():
            path = MARKDOWN_FIXTURE_DIR / name
            uploads.append(FakeUploadFile(filename=name, content=path.read_bytes(), content_type="text/markdown"))
            relative_paths.append(relative_path)
        return kb_service.import_files(
            uploads,
            chunk_size=128,
            chunk_overlap=16,
            kb_id=kb_id,
            relative_paths=relative_paths,
            import_mode="preserve_tree",
        )

    def _import_pdf_kb(self, kb_id: str) -> dict[str, Any]:
        source_dir = self.base_dir / "fixtures-src" / "pdf"
        uploads = []
        relative_paths = []
        for name, payload in self._select_import_entries("pdf", kb_id).items():
            pdf_path = source_dir / name
            if str(payload.get("source_kind") or "") == "scanned_pdf":
                _create_scanned_pdf(pdf_path, list(payload.get("image_lines") or []))
            else:
                _create_text_pdf(pdf_path, str(payload.get("text") or "").strip())
            uploads.append(FakeUploadFile(filename=name, content=pdf_path.read_bytes(), content_type="application/pdf"))
            relative_paths.append(str(payload["relative_path"]))
        return kb_service.import_files(
            uploads,
            chunk_size=128,
            chunk_overlap=16,
            kb_id=kb_id,
            relative_paths=relative_paths,
            import_mode="preserve_tree",
        )

    def _import_image_kb(self, kb_id: str) -> dict[str, Any]:
        source_dir = self.base_dir / "fixtures-src" / "image_ocr"
        uploads = []
        relative_paths = []
        for name, payload in self._select_import_entries("image_ocr", kb_id).items():
            image_path = source_dir / name
            lines = list(payload.get("image_lines") or _text_to_image_lines(str(payload.get("ocr_text") or "")))
            render_mode = str(payload.get("render_mode") or "clean")
            _create_text_image(image_path, lines, render_mode=render_mode)
            uploads.append(
                FakeUploadFile(
                    filename=name,
                    content=image_path.read_bytes(),
                    content_type="image/png",
                )
            )
            relative_paths.append(str(payload["relative_path"]))
        return kb_service.import_files(
            uploads,
            chunk_size=128,
            chunk_overlap=16,
            kb_id=kb_id,
            relative_paths=relative_paths,
            import_mode="preserve_tree",
        )









def build_eval_suite_markdown_report(report: dict[str, Any]) -> str:
    """渲染分层 semireal suite 的总览报告。"""
    totals = dict(report.get("totals") or {})
    layer_summaries = list(report.get("layer_summaries") or [])
    lines: list[str] = [
        f"# 问答分层评测报告：{report['suite_name']}",
        "",
        f"- 运行时间：{report['run_at']}",
        f"- 分层策略：{report.get('strategy') or '-'}",
        f"- suite 是否通过：{'是' if report.get('suite_passed') else '否'}",
        "",
        "## 1. Suite 汇总",
        "",
        _render_table(
            [[
                str(totals.get('target_cases') or 0),
                str(totals.get('actual_cases') or 0),
                str(totals.get('passed_cases') or 0),
                str(totals.get('failed_cases') or 0),
                f"{float(totals.get('pass_rate') or 0.0):.4f}",
                str(totals.get('passed_layers') or 0),
                str(totals.get('failed_layers') or 0),
            ]],
            ['target_cases', 'actual_cases', 'passed_cases', 'failed_cases', 'pass_rate', 'passed_layers', 'failed_layers'],
        ),
        "",
        "## 2. 各层结果",
        "",
    ]
    if layer_summaries:
        lines.extend([
            _render_table(
                [
                    [
                        str(item.get('name') or '-'),
                        str(item.get('dataset_name') or '-'),
                        str(item.get('evaluation_mode') or '-'),
                        str(item.get('target_case_count') or 0),
                        str(item.get('actual_case_count') or 0),
                        str(item.get('failed_cases') or 0),
                        f"{float(item.get('pass_rate') or 0.0):.4f}",
                        ', '.join(
                            list(item.get('failed_run_gates') or [])
                            + list(item.get('failed_contract_gates') or [])
                            + list(item.get('failed_diagnostic_gates') or [])
                        ) or '-',
                        '; '.join(
                            f"{cat['category']}({cat['pass_rate']:.2f}/{cat['count']})"
                            for cat in list(item.get('weakest_categories') or [])
                        ) or '-',
                    ]
                    for item in layer_summaries
                ],
                ['layer', 'dataset', 'mode', 'target_cases', 'actual_cases', 'failed_cases', 'pass_rate', 'failed_gates', 'weakest_categories'],
            ),
            '',
        ])
    else:
        lines.extend(['当前没有 layer 结果。', ''])

    lines.extend(['## 3. 分层瓶颈', ''])
    for index, item in enumerate(layer_summaries, start=1):
        lines.extend([
            f"### 3.{index} {item.get('name')}",
            '',
            f"- purpose：{item.get('purpose') or '-'}",
            f"- run_passed：{item.get('run_passed')}",
            f"- failed_run_gates：{', '.join(item.get('failed_run_gates') or []) or '-'}",
            f"- failed_contract_gates：{', '.join(item.get('failed_contract_gates') or []) or '-'}",
            f"- failed_diagnostic_gates：{', '.join(item.get('failed_diagnostic_gates') or []) or '-'}",
            f"- top_failure_cases：{', '.join(item.get('failure_case_ids') or []) or '-'}",
            f"- markdown_artifact：{dict(item.get('artifacts') or {}).get('markdown') or '-'}",
            '',
        ])
        lines.extend(_render_failed_gate_detail_lines('failed_run_gate_details', item.get('failed_run_gate_details')))
        lines.extend(_render_failed_gate_detail_lines('failed_contract_gate_details', item.get('failed_contract_gate_details')))
        lines.extend(_render_failed_gate_detail_lines('failed_diagnostic_gate_details', item.get('failed_diagnostic_gate_details')))
    return "\n".join(lines).strip() + "\n"


def write_eval_suite_markdown_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_eval_suite_markdown_report(report), encoding="utf-8")
    return path



def run_eval_semireal(
    *,
    cases_path: str | Path = DEFAULT_EVAL_CASES_PATH,
    schema_path: str | Path = DEFAULT_EVAL_SCHEMA_PATH,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> dict[str, Any]:
    """运行 semireal 问答评测并输出 JSON/Markdown 报告。"""
    schema, cases = load_eval_cases(cases_path, schema_path=schema_path)
    import_catalog = build_semireal_import_catalog(cases)
    with EvalV1SemirealHarness(import_catalog=import_catalog) as harness:
        report = run_chat_eval_cases(harness.client, cases, schema, dataset_name=schema["dataset_name"])
        report["import_summary"] = summarize_import_results(
            harness.import_results,
            kb_modalities=EVAL_KB_MODALITIES,
        )
        report["import_qa_correlation"] = build_import_qa_correlation(
            report["import_summary"],
            breakdowns=report.get("breakdowns"),
            case_results=report.get("case_results"),
        )

    evaluation_mode = str(schema.get("evaluation_mode") or report.get("evaluation_mode") or "healthy")
    report["evaluation_mode"] = evaluation_mode
    report["contract_gates"] = evaluate_contract_gates(
        report.get("refusal_summary"),
        report.get("negative_contract_summary"),
    )
    if evaluation_mode == "diagnostic":
        diagnostic_summary = build_diagnostic_summary(
            cases,
            list(report.get("case_results") or []),
            dict(report.get("import_qa_correlation") or {}),
        )
        diagnostic_gates = evaluate_diagnostic_gates(diagnostic_summary, schema)
        report["diagnostic_summary"] = diagnostic_summary
        report["diagnostic_gates"] = diagnostic_gates
        report["run_passed"] = evaluate_report_run_passed(
            evaluation_mode=evaluation_mode,
            suite_summary=report.get("suite_summary"),
            run_gates=report.get("run_gates"),
            contract_gates=report.get("contract_gates"),
            diagnostic_gates=diagnostic_gates,
        )
    else:
        report["run_passed"] = evaluate_report_run_passed(
            evaluation_mode=evaluation_mode,
            suite_summary=report.get("suite_summary"),
            run_gates=report.get("run_gates"),
            contract_gates=report.get("contract_gates"),
            diagnostic_gates=report.get("diagnostic_gates"),
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{schema['dataset_name']}-semireal-report.json"
    markdown_path = output_dir / f"{schema['dataset_name']}-semireal-report.md"
    report["artifacts"] = {
        "json": str(json_path.resolve()),
        "markdown": str(markdown_path.resolve()),
    }
    write_eval_json_report(report, json_path)
    write_eval_markdown_report(report, markdown_path)
    return report



def run_eval_v1_semireal(
    *,
    cases_path: str | Path = DEFAULT_EVAL_CASES_PATH,
    schema_path: str | Path = DEFAULT_EVAL_SCHEMA_PATH,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> dict[str, Any]:
    """兼容旧命名的 semireal runner 别名。"""
    return run_eval_semireal(cases_path=cases_path, schema_path=schema_path, output_dir=output_dir)



def run_eval_semireal_suite(
    *,
    suite_path: str | Path = DEFAULT_LAYERED_SUITE_PATH,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> dict[str, Any]:
    """按 smoke/main/hard manifest 依次执行 semireal 评测并输出总览报告。"""
    manifest = load_eval_suite_manifest(suite_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    layer_summaries: list[dict[str, Any]] = []
    layer_reports: dict[str, dict[str, Any]] = {}
    for layer in manifest["layers"]:
        layer_name = str(layer["name"])
        layer_report = run_eval_semireal(
            cases_path=layer["cases_path"],
            schema_path=layer["schema_path"],
            output_dir=output_dir / layer_name,
        )
        layer_reports[layer_name] = {
            "dataset_name": layer_report.get("dataset_name"),
            "evaluation_mode": layer_report.get("evaluation_mode"),
            "run_passed": layer_report.get("run_passed"),
            "suite_summary": layer_report.get("suite_summary"),
            "run_gates": layer_report.get("run_gates"),
            "contract_gates": layer_report.get("contract_gates"),
            "diagnostic_summary": layer_report.get("diagnostic_summary"),
            "diagnostic_gates": layer_report.get("diagnostic_gates"),
            "artifacts": layer_report.get("artifacts"),
        }
        layer_summaries.append(build_eval_suite_layer_summary(layer, layer_report))

    total_target_cases = sum(int(item.get("target_case_count") or 0) for item in layer_summaries)
    total_cases = sum(int(item.get("actual_case_count") or 0) for item in layer_summaries)
    passed_cases = sum(int(item.get("passed_cases") or 0) for item in layer_summaries)
    failed_cases = sum(int(item.get("failed_cases") or 0) for item in layer_summaries)
    suite_report = {
        "suite_name": str(manifest.get("suite_name") or "chat_eval_suite"),
        "strategy": str(manifest.get("strategy") or ""),
        "suite_path": str(manifest.get("suite_path") or ""),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "suite_passed": all(bool(item.get("run_passed")) for item in layer_summaries),
        "totals": {
            "target_cases": total_target_cases,
            "actual_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "pass_rate": _safe_ratio(passed_cases, total_cases),
            "passed_layers": sum(1 for item in layer_summaries if item.get("run_passed")),
            "failed_layers": sum(1 for item in layer_summaries if not item.get("run_passed")),
        },
        "layer_summaries": layer_summaries,
        "layer_reports": layer_reports,
    }
    json_path = output_dir / f"{suite_report['suite_name']}-suite-report.json"
    markdown_path = output_dir / f"{suite_report['suite_name']}-suite-report.md"
    suite_report["artifacts"] = {
        "json": str(json_path.resolve()),
        "markdown": str(markdown_path.resolve()),
    }
    write_eval_json_report(suite_report, json_path)
    write_eval_suite_markdown_report(suite_report, markdown_path)
    return suite_report
