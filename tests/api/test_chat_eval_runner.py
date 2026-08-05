from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.api.chat_eval_runner import (
    DEFAULT_EVAL_CASES_PATH,
    DEFAULT_EVAL_SCHEMA_PATH,
    IMAGE_KB_ID,
    PDF_KB_ID,
    PDF_ZERO_KB_ID,
    build_diagnostic_summary,
    build_semireal_import_catalog,
    evaluate_diagnostic_gates,
    load_eval_cases,
    run_chat_eval_cases,
    run_eval_v1_semireal,
)


EVAL_V3_CASES_PATH = Path("tests/fixtures/rag_quality/eval_v3/cases.json")
EVAL_V3_SCHEMA_PATH = Path("tests/fixtures/rag_quality/eval_v3/schema.json")
EVAL_V4_CASES_PATH = Path("tests/fixtures/rag_quality/eval_v4/cases.json")
EVAL_V4_SCHEMA_PATH = Path("tests/fixtures/rag_quality/eval_v4/schema.json")
EVAL_V5_CASES_PATH = Path("tests/fixtures/rag_quality/eval_v5/cases.json")
EVAL_V5_SCHEMA_PATH = Path("tests/fixtures/rag_quality/eval_v5/schema.json")
EVAL_V6_CASES_PATH = Path("tests/fixtures/rag_quality/eval_v6/cases.json")
EVAL_V6_SCHEMA_PATH = Path("tests/fixtures/rag_quality/eval_v6/schema.json")


class FakeResponse:
    """用于模拟 TestClient 响应的轻量对象。"""

    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    """按预设响应顺序返回结果的假客户端。"""

    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        self.responses = {key: list(items) for key, items in responses.items()}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, path: str, json: dict[str, Any]) -> FakeResponse:
        self.calls.append((path, json))
        queue = self.responses[path]
        if not queue:
            raise AssertionError(f"unexpected extra call for {path}")
        return queue.pop(0)


def _load_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    schema, cases = load_eval_cases(DEFAULT_EVAL_CASES_PATH, schema_path=DEFAULT_EVAL_SCHEMA_PATH)
    case = next(item for item in cases if item["case_id"] == case_id)
    return schema, case


def _load_eval_v3_cases() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return load_eval_cases(EVAL_V3_CASES_PATH, schema_path=EVAL_V3_SCHEMA_PATH)


def test_run_chat_eval_cases_skips_preview_for_no_evidence_case() -> None:
    """无证据 case 不应触发 preview 请求。"""
    schema, case = _load_case("eval-md-016")
    client = FakeClient(
        {
            "/api/chat/query": [
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": [case["kb_id"]],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": [case["kb_id"]],
                            "is_default_deny_applied": False,
                            "isolation_level": "logical_filter_only",
                            "answer": "No confirmable information is available in the current knowledge base.",
                            "sources": [],
                            "evidence": [],
                        }
                    },
                )
            ],
            "/api/kb/preview": [],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert [item[0] for item in client.calls] == ["/api/chat/query"]
    assert report["suite_summary"]["total_cases"] == 1
    assert report["suite_summary"]["passed_cases"] == 1
    assert report["case_results"][0]["preview_requested"] is False
    assert report["case_results"][0]["preview_required"] is False
    assert report["preview_stats"] == {"requested_cases": 0, "required_cases": 0, "skipped_cases": 0}
    assert report["failure_stage_breakdown"] == {}
    assert report["failures"] == []


def test_run_chat_eval_cases_records_preview_transport_failure() -> None:
    """preview 返回传输错误时，runner 应记录为 preview stage 失败。"""
    schema, case = _load_case("eval-md-001")
    client = FakeClient(
        {
            "/api/chat/query": [
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": [case["kb_id"]],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": [case["kb_id"]],
                            "is_default_deny_applied": False,
                            "isolation_level": "logical_filter_only",
                            "answer": "requested_scope_type requested_kb_ids effective_kb_ids",
                            "sources": [{"file": case["source_doc"]}],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": case["source_doc"],
                                    "source": case["source_doc"],
                                    "preview_locator": {"page": "1", "node_id": "node-1"},
                                }
                            ],
                        }
                    },
                )
            ],
            "/api/kb/preview": [
                FakeResponse(503, {"detail": "preview backend unavailable"})
            ],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert [item[0] for item in client.calls] == ["/api/chat/query", "/api/kb/preview"]
    assert report["suite_summary"]["total_cases"] == 1
    assert report["suite_summary"]["failed_cases"] == 1
    assert report["failure_stage_breakdown"] == {"preview": 1}
    assert report["preview_stats"] == {"requested_cases": 1, "required_cases": 1, "skipped_cases": 0}
    case_report = report["case_results"][0]
    assert case_report["passed"] is False
    assert case_report["failure_stage"] == "preview"
    assert case_report["failure_message"] == "preview backend unavailable"
    assert case_report["preview_requested"] is True
    assert case_report["response_status_code"] == 503
    assert case_report["preview_status_code"] is None


def test_run_chat_eval_cases_merges_multi_source_previews() -> None:
    """跨文档 case 应聚合多条 evidence preview 再做统一校验。"""
    schema, _ = _load_case("eval-md-001")
    case = {
        "case_id": "cross-preview-aggregation",
        "kb_id": "kb-a",
        "expected_scope_type": "single_kb",
        "expected_isolation_level": "logical_filter_only",
        "question": "Compare the cutover note and the handover sheet: who gives rollback approval and who owns the handover shift?",
        "source_doc": "cutover.md",
        "modality": "markdown",
        "difficulty": "complex",
        "answer_style": "comparison",
        "category": "cross_document",
        "answerable": True,
        "expected_keypoints": ["platform duty lead", "handover manager"],
        "required_evidence_docs": ["cutover.md", "handover.md"],
        "expected_source_count": 2,
        "preview_required": True,
        "preview_terms": ["platform duty lead", "handover manager"],
        "judge_focus": ["factual_accuracy", "citation_accuracy"],
    }
    client = FakeClient(
        {
            "/api/chat/query": [
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": [case["kb_id"]],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": [case["kb_id"]],
                            "is_default_deny_applied": False,
                            "isolation_level": "logical_filter_only",
                            "answer": "cutover.md: platform duty lead. handover.md: handover manager.",
                            "sources": [
                                {"file": "cutover.md"},
                                {"file": "handover.md"},
                            ],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": "cutover.md",
                                    "source": "cutover.md",
                                    "preview_locator": {"page": "1", "node_id": "node-1"},
                                },
                                {
                                    "id": "evidence-2",
                                    "title": "handover.md",
                                    "source": "handover.md",
                                    "preview_locator": {"page": "1", "node_id": "node-2"},
                                },
                            ],
                        }
                    },
                )
            ],
            "/api/kb/preview": [
                FakeResponse(200, {"data": {"doc_id": "doc-cutover", "excerpt": "platform duty lead approves rollback"}}),
                FakeResponse(200, {"data": {"doc_id": "doc-handover", "excerpt": "handover manager owns the shift"}}),
            ],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert [item[0] for item in client.calls] == ["/api/chat/query", "/api/kb/preview", "/api/kb/preview"]
    case_report = report["case_results"][0]
    assert case_report["passed"] is True
    assert case_report["preview_requested"] is True
    assert case_report["preview_resolvable"] is True
    assert sorted(case_report["preview_term_hits"]) == ["handover manager", "platform duty lead"]
    assert case_report["preview_term_coverage"] == 1.0
    assert case_report["response_status_code"] == 200
    assert case_report["preview_status_code"] == 200
    assert report["preview_stats"] == {"requested_cases": 1, "required_cases": 1, "skipped_cases": 0}


def test_run_eval_v1_semireal_produces_full_report(tmp_path: Path) -> None:
    """eval v1 半真实运行应产生稳定报告与 artifact。"""
    report = run_eval_v1_semireal(output_dir=tmp_path)

    assert report["dataset_name"] == "local_multi_kb_eval_v1"
    assert report["evaluation_mode"] == "healthy"
    assert report["run_passed"] is True
    assert report["suite_summary"]["total_cases"] == 54
    assert report["suite_summary"]["passed_cases"] == 54
    assert report["suite_summary"]["failed_cases"] == 0
    assert report["breakdowns"]["difficulty"]["complex"]["pass_rate"] == 1.0
    assert report["preview_stats"] == {"requested_cases": 45, "required_cases": 45, "skipped_cases": 0}
    assert report["failure_stage_breakdown"] == {}

    import_summary = report["import_summary"]
    assert import_summary["total_kbs"] == 3
    assert import_summary["total_files"] == 14
    assert import_summary["total_success_count"] == 14
    assert import_summary["total_failed_count"] == 0
    assert import_summary["total_empty_count"] == 0
    assert import_summary["total_indexed_chunks"] == 14
    assert import_summary["total_document_count"] == 14
    assert import_summary["total_node_count"] == 14
    assert import_summary["total_input_text_chars"] > 0
    assert import_summary["total_ocr_success_count"] == 3
    assert import_summary["total_asset_registered_count"] == 3
    assert import_summary["kb_breakdown"]["eval-kb-markdown"]["headline"] == "成功导入 7 个文件"
    assert import_summary["kb_breakdown"]["eval-kb-pdf"]["headline"] == "成功导入 4 个文件"
    assert import_summary["kb_breakdown"]["eval-kb-image"]["headline"] == "成功导入 3 个文件"

    import_qa = report["import_qa_correlation"]
    assert import_qa["weak_signal_kb_count"] == 0
    assert import_qa["weak_signal_kb_ids"] == []
    assert import_qa["weak_signal_modality_count"] == 0
    assert import_qa["weak_signal_modalities"] == []
    assert import_qa["signal_breakdown"] == {}

    json_report = Path(report["artifacts"]["json"])
    markdown_report = Path(report["artifacts"]["markdown"])
    assert json_report.is_file()
    assert markdown_report.is_file()

    saved_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert saved_payload["suite_summary"]["passed_cases"] == 54
    assert saved_payload["import_summary"]["total_success_count"] == 14
    assert saved_payload["import_qa_correlation"]["signal_breakdown"] == {}

    markdown_text = markdown_report.read_text(encoding="utf-8")
    assert "问答评测报告" in markdown_text
    assert "评测模式：healthy" in markdown_text
    assert "Suite 摘要" in markdown_text
    assert "失败样本" in markdown_text


def test_build_semireal_import_catalog_includes_seed_docs_for_no_evidence_case() -> None:
    """seed_docs 应能为 no-evidence 诊断 case 预先装载弱信号文档。"""
    _, cases = _load_eval_v3_cases()

    catalog = build_semireal_import_catalog(cases)

    assert "zero-text-diagnostic.pdf" in catalog["pdf"]
    assert catalog["pdf"]["zero-text-diagnostic.pdf"]["kb_id"] == PDF_ZERO_KB_ID
    assert catalog["pdf"]["zero-text-diagnostic.pdf"]["force_empty_text_document"] is True


def test_build_diagnostic_summary_matches_expected_case_outcomes() -> None:
    """diagnostic 摘要应能对齐预期通过/失败与弱信号分布。"""
    _, cases = _load_eval_v3_cases()
    summary = build_diagnostic_summary(
        cases,
        [
            {"case_id": "eval-v3-img-001", "kb_id": IMAGE_KB_ID, "modality": "image_ocr", "passed": False, "failure_stage": "quality_gate"},
            {"case_id": "eval-v3-img-002", "kb_id": IMAGE_KB_ID, "modality": "image_ocr", "passed": False, "failure_stage": "quality_gate"},
            {"case_id": "eval-v3-img-003", "kb_id": IMAGE_KB_ID, "modality": "image_ocr", "passed": False, "failure_stage": "quality_gate"},
            {"case_id": "eval-v3-pdf-001", "kb_id": PDF_KB_ID, "modality": "pdf", "passed": True, "failure_stage": None},
            {"case_id": "eval-v3-pdf-002", "kb_id": PDF_ZERO_KB_ID, "modality": "pdf", "passed": True, "failure_stage": None},
            {"case_id": "eval-v3-pdf-003", "kb_id": PDF_KB_ID, "modality": "pdf", "passed": True, "failure_stage": None},
        ],
        {
            "weak_signal_kb_count": 3,
            "weak_signal_kb_ids": [IMAGE_KB_ID, PDF_KB_ID, PDF_ZERO_KB_ID],
            "weak_signal_modality_count": 2,
            "weak_signal_modalities": ["image_ocr", "pdf"],
            "signal_breakdown": {
                "asset_registered_without_index": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "dependency_missing": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "nodes_without_embedding": {"kb_count": 1, "kb_ids": [PDF_KB_ID]},
                "ocr_failed": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "ocr_no_text": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "zero_text_content": {"kb_count": 1, "kb_ids": [PDF_ZERO_KB_ID]},
            },
        },
    )

    assert summary["total_cases"] == 6
    assert summary["expected_failed_cases"] == 3
    assert summary["actual_failed_cases"] == 3
    assert summary["case_expectation_match_rate"] == pytest.approx(1.0)
    assert summary["weak_signal_case_count"] == 5
    assert summary["weak_signal_kb_count"] == 3
    assert summary["weak_signal_modality_count"] == 2
    assert summary["weak_signal_case_ids"] == [
        "eval-v3-img-001",
        "eval-v3-img-002",
        "eval-v3-img-003",
        "eval-v3-pdf-001",
        "eval-v3-pdf-002",
    ]
    assert summary["weak_signal_breakdown"] == {
        "asset_registered_without_index": 3,
        "dependency_missing": 1,
        "nodes_without_embedding": 1,
        "ocr_failed": 2,
        "ocr_no_text": 1,
        "zero_text_content": 1,
    }
    assert summary["mismatch_cases"] == []


def test_evaluate_diagnostic_gates_accepts_required_signal_tags() -> None:
    """diagnostic gates 应能接受扩展后的 6 类弱信号标签。"""
    schema, cases = _load_eval_v3_cases()
    summary = build_diagnostic_summary(
        cases,
        [
            {"case_id": "eval-v3-img-001", "kb_id": IMAGE_KB_ID, "modality": "image_ocr", "passed": False, "failure_stage": "quality_gate"},
            {"case_id": "eval-v3-img-002", "kb_id": IMAGE_KB_ID, "modality": "image_ocr", "passed": False, "failure_stage": "quality_gate"},
            {"case_id": "eval-v3-img-003", "kb_id": IMAGE_KB_ID, "modality": "image_ocr", "passed": False, "failure_stage": "quality_gate"},
            {"case_id": "eval-v3-pdf-001", "kb_id": PDF_KB_ID, "modality": "pdf", "passed": True, "failure_stage": None},
            {"case_id": "eval-v3-pdf-002", "kb_id": PDF_ZERO_KB_ID, "modality": "pdf", "passed": True, "failure_stage": None},
            {"case_id": "eval-v3-pdf-003", "kb_id": PDF_KB_ID, "modality": "pdf", "passed": True, "failure_stage": None},
        ],
        {
            "weak_signal_kb_count": 3,
            "weak_signal_kb_ids": [IMAGE_KB_ID, PDF_KB_ID, PDF_ZERO_KB_ID],
            "weak_signal_modality_count": 2,
            "weak_signal_modalities": ["image_ocr", "pdf"],
            "signal_breakdown": {
                "asset_registered_without_index": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "dependency_missing": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "nodes_without_embedding": {"kb_count": 1, "kb_ids": [PDF_KB_ID]},
                "ocr_failed": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "ocr_no_text": {"kb_count": 1, "kb_ids": [IMAGE_KB_ID]},
                "zero_text_content": {"kb_count": 1, "kb_ids": [PDF_ZERO_KB_ID]},
            },
        },
    )

    gates = evaluate_diagnostic_gates(summary, schema)

    assert set(gates) == {
        "case_expectation_match_rate_min",
        "minimum_weak_signal_kb_count",
        "minimum_weak_signal_modality_count",
        "required_signal_tags",
    }
    assert all(item["passed"] for item in gates.values())
    assert gates["required_signal_tags"]["metric"] == "signal_breakdown"
    assert gates["required_signal_tags"]["required"] == [
        "ocr_no_text",
        "ocr_failed",
        "dependency_missing",
        "nodes_without_embedding",
        "zero_text_content",
        "asset_registered_without_index",
    ]
    assert gates["required_signal_tags"]["actual"] == [
        "asset_registered_without_index",
        "dependency_missing",
        "nodes_without_embedding",
        "ocr_failed",
        "ocr_no_text",
        "zero_text_content",
    ]


def test_run_eval_v3_semireal_reports_weak_signal_diagnostics(tmp_path: Path) -> None:
    """eval v3 半真实运行应输出完整的弱信号诊断报告。"""
    report = run_eval_v1_semireal(
        cases_path=EVAL_V3_CASES_PATH,
        schema_path=EVAL_V3_SCHEMA_PATH,
        output_dir=tmp_path,
    )

    assert report["dataset_name"] == "local_multi_kb_eval_v3"
    assert report["evaluation_mode"] == "diagnostic"
    assert report["run_passed"] is True
    assert report["suite_summary"]["total_cases"] == 6
    assert report["suite_summary"]["passed_cases"] == 3
    assert report["suite_summary"]["failed_cases"] == 3
    assert report["diagnostic_summary"]["case_expectation_match_rate"] == pytest.approx(1.0)
    assert report["diagnostic_summary"]["weak_signal_case_count"] == 5
    assert report["diagnostic_summary"]["mismatch_cases"] == []
    assert report["import_qa_correlation"]["weak_signal_kb_count"] >= 3
    assert report["import_qa_correlation"]["weak_signal_modality_count"] >= 2
    assert set(report["import_qa_correlation"]["signal_breakdown"]) >= {
        "ocr_no_text",
        "ocr_failed",
        "dependency_missing",
        "nodes_without_embedding",
        "zero_text_content",
        "asset_registered_without_index",
    }
    assert all(item["passed"] for item in report["run_gates"].values())
    assert all(item["passed"] for item in report["diagnostic_gates"].values())

    json_report = Path(report["artifacts"]["json"])
    markdown_report = Path(report["artifacts"]["markdown"])
    assert json_report.is_file()
    assert markdown_report.is_file()

    saved_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert saved_payload["diagnostic_summary"]["case_expectation_match_rate"] == pytest.approx(1.0)
    assert saved_payload["diagnostic_summary"]["weak_signal_breakdown"] == {
        "asset_registered_without_index": 3,
        "dependency_missing": 1,
        "nodes_without_embedding": 1,
        "ocr_failed": 2,
        "ocr_no_text": 1,
        "zero_text_content": 1,
    }

    markdown_text = markdown_report.read_text(encoding="utf-8")
    assert "问答评测报告" in markdown_text
    assert "diagnostic" in markdown_text
    assert "诊断摘要" in markdown_text
    assert "Diagnostic Gate" in markdown_text
    assert "ocr_no_text" in markdown_text
    assert "ocr_failed" in markdown_text
    assert "dependency_missing" in markdown_text
    assert "nodes_without_embedding" in markdown_text
    assert "zero_text_content" in markdown_text
    assert "asset_registered_without_index" in markdown_text


def test_run_eval_v4_business_semireal_report(tmp_path: Path) -> None:
    """eval v4 业务化评测应输出扩容后的稳定报告。"""
    report = run_eval_v1_semireal(
        cases_path=EVAL_V4_CASES_PATH,
        schema_path=EVAL_V4_SCHEMA_PATH,
        output_dir=tmp_path,
    )

    assert report["dataset_name"] == "local_multi_kb_eval_v4_business"
    assert report["evaluation_mode"] == "healthy"
    assert report["run_passed"] is True
    assert report["suite_summary"]["total_cases"] == 54
    assert report["suite_summary"]["passed_cases"] == 54
    assert report["suite_summary"]["failed_cases"] == 0
    assert report["breakdowns"]["modality"]["markdown"]["count"] == 18
    assert report["breakdowns"]["modality"]["pdf"]["count"] == 18
    assert report["breakdowns"]["modality"]["image_ocr"]["count"] == 18
    assert report["breakdowns"]["difficulty"]["simple"]["count"] == 18
    assert report["breakdowns"]["difficulty"]["medium"]["count"] == 18
    assert report["breakdowns"]["difficulty"]["complex"]["count"] == 18
    assert report["breakdowns"]["answer_style"]["refusal"]["count"] == 12
    assert report["breakdowns"]["answer_style"]["fact"]["count"] == 18
    assert report["breakdowns"]["answer_style"]["summary"]["count"] == 11
    assert report["breakdowns"]["answer_style"]["policy"]["count"] == 9
    assert report["breakdowns"]["answer_style"]["comparison"]["count"] == 4
    assert report["preview_stats"]["required_cases"] == 42
    assert report["import_summary"]["total_kbs"] == 3
    assert report["import_summary"]["total_failed_count"] == 0
    assert report["import_qa_correlation"]["weak_signal_kb_count"] == 0
    assert report["import_qa_correlation"]["weak_signal_modality_count"] == 0
    assert all(item["passed"] for item in report["run_gates"].values())

    json_report = Path(report["artifacts"]["json"])
    markdown_report = Path(report["artifacts"]["markdown"])
    assert json_report.is_file()
    assert markdown_report.is_file()

    saved_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert saved_payload["suite_summary"]["passed_cases"] == 54
    assert saved_payload["suite_summary"]["failed_cases"] == 0

    markdown_text = markdown_report.read_text(encoding="utf-8")
    assert "local_multi_kb_eval_v4_business" in markdown_text
    assert "54" in markdown_text
    assert "healthy" in markdown_text

def test_run_eval_v5_business_plus_semireal_report(tmp_path: Path) -> None:
    report = run_eval_v1_semireal(
        cases_path=EVAL_V5_CASES_PATH,
        schema_path=EVAL_V5_SCHEMA_PATH,
        output_dir=tmp_path,
    )

    assert report["dataset_name"] == "local_multi_kb_eval_v5_business_plus"
    assert report["evaluation_mode"] == "healthy"
    assert report["run_passed"] is True
    assert report["suite_summary"]["total_cases"] == 72
    assert report["suite_summary"]["passed_cases"] == 72
    assert report["suite_summary"]["failed_cases"] == 0
    assert report["breakdowns"]["modality"]["markdown"]["count"] == 24
    assert report["breakdowns"]["modality"]["pdf"]["count"] == 24
    assert report["breakdowns"]["modality"]["image_ocr"]["count"] == 24
    assert report["breakdowns"]["difficulty"]["simple"]["count"] == 24
    assert report["breakdowns"]["difficulty"]["medium"]["count"] == 24
    assert report["breakdowns"]["difficulty"]["complex"]["count"] == 24
    assert report["breakdowns"]["answer_style"]["refusal"]["count"] == 15
    assert report["breakdowns"]["answer_style"]["fact"]["count"] == 24
    assert report["breakdowns"]["answer_style"]["summary"]["count"] == 17
    assert report["breakdowns"]["answer_style"]["policy"]["count"] == 9
    assert report["breakdowns"]["answer_style"]["comparison"]["count"] == 7
    assert report["breakdowns"]["category"]["cross_document"]["count"] == 6
    assert report["breakdowns"]["category"]["long_document"]["count"] == 4
    assert report["breakdowns"]["category"]["hard_refusal"]["count"] == 3
    assert report["breakdowns"]["category"]["approval_summary"]["count"] == 10
    assert report["breakdowns"]["category"]["process_boundary"]["count"] == 12
    assert report["preview_stats"]["required_cases"] == 57
    assert report["suite_summary"]["source_count_match_rate"] == pytest.approx(1.0)
    assert report["import_summary"]["total_kbs"] == 3
    assert report["import_summary"]["total_failed_count"] == 0
    assert report["import_qa_correlation"]["weak_signal_kb_count"] == 0
    assert report["import_qa_correlation"]["weak_signal_modality_count"] == 0
    assert all(item["passed"] for item in report["run_gates"].values())

    json_report = Path(report["artifacts"]["json"])
    markdown_report = Path(report["artifacts"]["markdown"])
    assert json_report.is_file()
    assert markdown_report.is_file()

    saved_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert saved_payload["suite_summary"]["passed_cases"] == 72
    assert saved_payload["suite_summary"]["failed_cases"] == 0

    markdown_text = markdown_report.read_text(encoding="utf-8")
    assert "local_multi_kb_eval_v5_business_plus" in markdown_text
    assert "72" in markdown_text
    assert "healthy" in markdown_text


def test_run_eval_v6_business_plus_diagnostic_semireal_report(tmp_path: Path) -> None:
    """eval v6 ??????? + ?????????????"""
    report = run_eval_v1_semireal(
        cases_path=EVAL_V6_CASES_PATH,
        schema_path=EVAL_V6_SCHEMA_PATH,
        output_dir=tmp_path,
    )

    assert report["dataset_name"] == "local_multi_kb_eval_v6_business_plus_diagnostic"
    assert report["evaluation_mode"] == "diagnostic"
    assert report["run_passed"] is True
    assert report["suite_summary"]["total_cases"] == 78
    assert report["suite_summary"]["passed_cases"] == 78
    assert report["suite_summary"]["failed_cases"] == 0
    assert report["suite_summary"]["evidence_hit_rate"] == pytest.approx(1.0)
    assert report["suite_summary"]["preview_resolvable_rate"] == pytest.approx(1.0)
    assert report["breakdowns"]["modality"]["markdown"]["count"] == 24
    assert report["breakdowns"]["modality"]["pdf"]["count"] == 27
    assert report["breakdowns"]["modality"]["image_ocr"]["count"] == 27
    assert report["breakdowns"]["difficulty"]["simple"]["count"] == 30
    assert report["breakdowns"]["difficulty"]["medium"]["count"] == 24
    assert report["breakdowns"]["difficulty"]["complex"]["count"] == 24
    assert report["breakdowns"]["category"]["scope_contract"]["count"] == 4
    assert report["breakdowns"]["category"]["scope_contract"]["passed"] == 4
    assert report["breakdowns"]["category"]["scope_contract"]["failed"] == 0
    assert report["preview_stats"]["required_cases"] == 58
    assert report["import_summary"]["total_kbs"] == 4
    assert report["import_summary"]["total_failed_count"] == 0
    assert report["diagnostic_summary"]["case_expectation_match_rate"] == pytest.approx(1.0)
    assert report["diagnostic_summary"]["weak_signal_case_count"] == 5
    assert report["diagnostic_summary"]["mismatch_cases"] == []
    assert report["diagnostic_summary"]["expected_passed_cases"] == 78
    assert report["diagnostic_summary"]["expected_failed_cases"] == 0
    assert report["diagnostic_summary"]["actual_passed_cases"] == 78
    assert report["diagnostic_summary"]["actual_failed_cases"] == 0
    assert report["diagnostic_summary"]["weak_signal_breakdown"] == {
        "asset_registered_without_index": 3,
        "dependency_missing": 1,
        "nodes_without_embedding": 1,
        "ocr_failed": 2,
        "ocr_no_text": 1,
        "zero_text_content": 1,
    }
    assert report["import_qa_correlation"]["weak_signal_kb_count"] == 3
    assert report["import_qa_correlation"]["weak_signal_modality_count"] == 2
    assert set(report["import_qa_correlation"]["signal_breakdown"]) >= {
        "ocr_no_text",
        "ocr_failed",
        "dependency_missing",
        "nodes_without_embedding",
        "zero_text_content",
        "asset_registered_without_index",
    }
    assert report["run_gates"]["evidence_hit_rate_min"]["passed"] is True
    assert report["run_gates"]["evidence_hit_rate_min"]["actual"] == pytest.approx(1.0)
    assert report["run_gates"]["evidence_hit_rate_min"]["minimum"] == pytest.approx(0.95)
    assert all(item["passed"] for item in report["run_gates"].values())
    assert all(item["passed"] for item in report["diagnostic_gates"].values())

    json_report = Path(report["artifacts"]["json"])
    markdown_report = Path(report["artifacts"]["markdown"])
    assert json_report.is_file()
    assert markdown_report.is_file()

    saved_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert saved_payload["run_passed"] is True
    assert saved_payload["suite_summary"]["passed_cases"] == 78
    assert saved_payload["suite_summary"]["failed_cases"] == 0
    assert saved_payload["diagnostic_summary"]["case_expectation_match_rate"] == pytest.approx(1.0)
    assert saved_payload["failures"] == []

    markdown_text = markdown_report.read_text(encoding="utf-8")
    assert "local_multi_kb_eval_v6_business_plus_diagnostic" in markdown_text
    assert "diagnostic" in markdown_text
    assert "Diagnostic Gate" in markdown_text
    assert "weak_signal_case_count | 5 |" in markdown_text
    assert "evidence_hit_rate | 1.000 |" in markdown_text
    assert "scope_contract | 4 | 4 | 0 | 1.000 |" in markdown_text

