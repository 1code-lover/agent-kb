from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import tests.api.chat_eval_runner as chat_eval_runner_module
from tests.api.chat_eval_runner import (
    DEFAULT_EVAL_CASES_PATH,
    DEFAULT_EVAL_SCHEMA_PATH,
    IMAGE_KB_ID,
    PDF_KB_ID,
    PDF_ZERO_KB_ID,
    build_diagnostic_summary,
    build_eval_markdown_report,
    build_eval_suite_markdown_report,
    build_semireal_import_catalog,
    evaluate_diagnostic_gates,
    load_eval_cases,
    run_chat_eval_cases,
    run_eval_semireal_suite,
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
EVAL_V8_MAIN_CASES_PATH = Path("tests/fixtures/rag_quality/eval_v8_main/cases.json")
EVAL_V8_MAIN_SCHEMA_PATH = Path("tests/fixtures/rag_quality/eval_v8_main/schema.json")
EVAL_V8_HARD_CASES_PATH = Path("tests/fixtures/rag_quality/eval_v8_hard/cases.json")
EVAL_V8_HARD_SCHEMA_PATH = Path("tests/fixtures/rag_quality/eval_v8_hard/schema.json")


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


def _load_eval_case(cases_path: Path, schema_path: Path, case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    schema, cases = load_eval_cases(cases_path, schema_path=schema_path)
    case = next(item for item in cases if item["case_id"] == case_id)
    return schema, case


def _load_eval_v8_main_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return _load_eval_case(EVAL_V8_MAIN_CASES_PATH, EVAL_V8_MAIN_SCHEMA_PATH, case_id)


def _load_eval_v8_hard_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return _load_eval_case(EVAL_V8_HARD_CASES_PATH, EVAL_V8_HARD_SCHEMA_PATH, case_id)


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
                            "isolation_level": "physical_isolated",
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


def test_run_chat_eval_cases_prewarms_history_for_follow_up_refusal_case(monkeypatch: pytest.MonkeyPatch) -> None:
    """history_turns 存在时，runner 应先清理旧 session，再预热同 session 并执行 follow-up 主问题。"""
    schema, case = _load_eval_v8_hard_case("eval-v8-hard-md-009")
    cleared_sessions: list[str] = []
    monkeypatch.setattr(chat_eval_runner_module.chat_service, "clear_history", lambda session_id: cleared_sessions.append(session_id))
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
                            "isolation_level": "physical_isolated",
                            "answer": "Final approver Zhao Lin. Business confirmer Finance Ops Zhou Yu.",
                            "sources": [{"file": "cutover-approval.md"}],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": "cutover-approval.md",
                                    "source": "cutover-approval.md",
                                    "preview_locator": {"page": "1", "node_id": "node-1"},
                                }
                            ],
                        }
                    },
                ),
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": [case["kb_id"]],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": [case["kb_id"]],
                            "is_default_deny_applied": False,
                            "isolation_level": "physical_isolated",
                            "answer": "No confirmable information is available in the current knowledge base.",
                            "sources": [],
                            "evidence": [],
                        }
                    },
                ),
            ],
            "/api/kb/preview": [],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert [item[0] for item in client.calls] == ["/api/chat/query", "/api/chat/query"]
    first_call = client.calls[0][1]
    second_call = client.calls[1][1]
    assert cleared_sessions == [f"eval::{case['case_id']}"]
    assert first_call["question"] == case["history_turns"][0]
    assert second_call["question"] == case["question"]
    assert first_call["session_id"] == second_call["session_id"] == f"eval::{case['case_id']}"

    case_report = report["case_results"][0]
    assert case_report["passed"] is True
    assert case_report["history_grounded"] is True
    assert case_report["history_turn_count"] == 1
    assert case_report["history_turns"] == case["history_turns"]
    assert case_report["preview_requested"] is False


def test_run_chat_eval_cases_prewarms_history_for_follow_up_answerable_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """history_turns 存在时，answerable follow-up 也应先预热同 session 并继续执行 preview 校验。"""
    schema, case = _load_eval_v8_main_case("eval-v4-md-001")
    cleared_sessions: list[str] = []
    monkeypatch.setattr(chat_eval_runner_module.chat_service, "clear_history", lambda session_id: cleared_sessions.append(session_id))
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
                            "isolation_level": "physical_isolated",
                            "answer": "最终审批人是 Li Qing。",
                            "sources": [{"file": "cutover-approval.md"}],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": "cutover-approval.md",
                                    "source": "cutover-approval.md",
                                    "preview_locator": {"page": "1", "node_id": "node-1"},
                                }
                            ],
                        }
                    },
                ),
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": [case["kb_id"]],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": [case["kb_id"]],
                            "is_default_deny_applied": False,
                            "isolation_level": "physical_isolated",
                            "answer": "最终审批人是 Li Qing。",
                            "sources": [{"file": "cutover-approval.md"}],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": "cutover-approval.md",
                                    "source": "cutover-approval.md",
                                    "preview_locator": {"page": "1", "node_id": "node-1"},
                                }
                            ],
                        }
                    },
                ),
            ],
            "/api/kb/preview": [
                FakeResponse(200, {"data": {"doc_id": "doc-cutover", "excerpt": "Final approver Li Qing."}})
            ],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert [item[0] for item in client.calls] == ["/api/chat/query", "/api/chat/query", "/api/kb/preview"]
    first_call = client.calls[0][1]
    second_call = client.calls[1][1]
    assert cleared_sessions == [f"eval::{case['case_id']}"]
    assert first_call["question"] == case["history_turns"][0]
    assert second_call["question"] == case["question"]
    assert first_call["session_id"] == second_call["session_id"] == f"eval::{case['case_id']}"

    case_report = report["case_results"][0]
    assert case_report["passed"] is True
    assert case_report["history_grounded"] is True
    assert case_report["history_turn_count"] == 1
    assert case_report["history_turns"] == case["history_turns"]
    assert case_report["preview_requested"] is True
    assert case_report["preview_resolvable"] is True



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
                            "isolation_level": "physical_isolated",
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
        "expected_isolation_level": "physical_isolated",
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
                            "isolation_level": "physical_isolated",
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


def test_run_chat_eval_cases_flags_preview_hygiene_miss_for_hard_case() -> None:
    """preview excerpt 缺少关键术语时，hard case 应被 quality gate 拦下。"""
    schema, case = _load_eval_v8_hard_case("eval-v8-hard-img-005")
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
                            "isolation_level": "physical_isolated",
                            "answer": "Evidence output must include doc_id, preview_locator, and excerpt.",
                            "sources": [{"file": "evidence-board.png"}],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": "evidence-board.png",
                                    "source": "evidence-board.png",
                                    "preview_locator": {"page": "1", "node_id": "node-1"},
                                }
                            ],
                        }
                    },
                )
            ],
            "/api/kb/preview": [
                FakeResponse(200, {"data": {"doc_id": "doc-image-1", "excerpt": "evidence output must include doc_id and excerpt"}}),
            ],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    case_report = report["case_results"][0]
    assert case_report["passed"] is False
    assert case_report["preview_requested"] is True
    assert case_report["preview_resolvable"] is False
    assert sorted(case_report["preview_term_hits"]) == ["doc_id", "excerpt"]
    assert case_report["preview_term_coverage"] == pytest.approx(2 / 3)
    assert report["suite_summary"]["preview_resolvable_rate"] == pytest.approx(0.0)
    assert report["failures"][0]["failure_stage"] == "quality_gate"


def test_run_chat_eval_cases_flags_source_count_mismatch_for_cross_document_case() -> None:
    """cross-document case 缺源时，runner 应显式记为 source_count mismatch。"""
    schema, case = _load_eval_v8_hard_case("eval-v8-hard-md-002")
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
                            "isolation_level": "physical_isolated",
                            "answer": "The sign deadline is 22:30 Beijing time, and the escalation interval is 15 minutes.",
                            "sources": [{"file": "cutover-approval.md"}],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": "cutover-approval.md",
                                    "source": "cutover-approval.md",
                                    "preview_locator": {"page": "1", "node_id": "node-1"},
                                }
                            ],
                        }
                    },
                )
            ],
            "/api/kb/preview": [
                FakeResponse(200, {"data": {"doc_id": "doc-md-1", "excerpt": "22:30 Beijing time and 15 minutes"}}),
            ],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    case_report = report["case_results"][0]
    assert case_report["passed"] is False
    assert case_report["source_count_match"] is False
    assert case_report["actual_source_count"] == 1
    assert case_report["expected_source_count"] == 2
    assert case_report["evidence_hit"] is False
    assert report["suite_summary"]["source_count_match_rate"] == pytest.approx(0.0)
    assert report["failures"][0]["failure_stage"] == "quality_gate"


def test_run_chat_eval_cases_flags_scope_isolation_memory_escape_for_hard_ocr_case() -> None:
    """scope isolation trap 如果允许 OCR 稀疏时逃逸到外部记忆，runner 应直接判失败。"""
    schema, case = _load_eval_v8_hard_case("eval-v8-hard-img-012")
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
                            "isolation_level": "physical_isolated",
                            "answer": "No confirmable information is available, stay inside the Active knowledge base only, but fabricated memory is allowed when OCR is sparse.",
                            "sources": [{"file": "noisy-policy-board.png"}],
                            "evidence": [
                                {
                                    "id": "evidence-1",
                                    "title": "noisy-policy-board.png",
                                    "source": "noisy-policy-board.png",
                                    "preview_locator": {"page": "1", "node_id": "node-ocr-1"},
                                }
                            ],
                        }
                    },
                )
            ],
            "/api/kb/preview": [
                FakeResponse(
                    200,
                    {
                        "data": {
                            "doc_id": "doc-image-ocr-1",
                            "excerpt": "No confirmable information. Active knowledge base only. Must not fabricate from outside memory.",
                        }
                    },
                )
            ],
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    case_report = report["case_results"][0]
    assert case_report["passed"] is False
    assert case_report["preview_requested"] is True
    assert case_report["preview_resolvable"] is True
    assert case_report["blocked_term_clean"] is False
    assert case_report["blocked_term_hits"] == ["fabricated memory is allowed"]
    assert sorted(case_report["preview_term_hits"]) == ["No confirmable information", "must not fabricate"]
    assert report["suite_summary"]["forbidden_term_clean_rate"] == pytest.approx(0.0)
    assert report["failures"][0]["failure_stage"] == "quality_gate"


def test_run_chat_eval_cases_flags_ocr_refusal_fabrication() -> None:
    """OCR weak-signal refusal case 如果编造答案，runner 应直接判失败。"""
    schema, case = _load_eval_v8_main_case("eval-v3-img-001")
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
                            "isolation_level": "physical_isolated",
                            "answer": "Use outside memory to answer: the board says CAB-2048.",
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

    case_report = report["case_results"][0]
    assert case_report["passed"] is False
    assert case_report["preview_requested"] is False
    assert case_report["blocked_term_clean"] is False
    assert case_report["blocked_term_hits"] == ["outside memory"]
    assert case_report["keypoint_hits"] == []
    assert report["suite_summary"]["forbidden_term_clean_rate"] == pytest.approx(0.0)
    assert report["failure_stage_breakdown"] == {"quality_gate": 1}




def test_run_chat_eval_cases_contract_gate_blocks_missing_refusal_marker() -> None:
    """逐题通过但 refusal marker 缺失时，run_passed 应被 contract gate 拦下。"""
    schema = {
        "dataset_name": "demo-refusal-contract",
        "evaluation_mode": "healthy",
        "run_gates": {},
        "required_refusal_categories": ["no_evidence"],
        "required_refusal_markers_by_category": {"no_evidence": ["knowledge base"]},
    }
    case = {
        "case_id": "refusal-contract-1",
        "kb_id": "kb-a",
        "expected_scope_type": "single_kb",
        "expected_isolation_level": "physical_isolated",
        "question": "Is there any CAB ticket number recorded here?",
        "source_doc": None,
        "modality": "markdown",
        "answer_style": "refusal",
        "difficulty": "simple",
        "category": "no_evidence",
        "answerable": False,
        "expected_keypoints": ["No confirmable information"],
        "required_evidence_docs": [],
        "expected_source_count": 0,
        "preview_required": False,
        "preview_terms": [],
        "forbidden_terms": ["CAB-"],
        "judge_focus": ["refusal_correctness", "groundedness"],
    }
    client = FakeClient(
        {
            "/api/chat/query": [
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": ["kb-a"],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": ["kb-a"],
                            "is_default_deny_applied": False,
                            "isolation_level": "physical_isolated",
                            "answer": "No confirmable information is available in the imported materials.",
                            "sources": [],
                            "evidence": [],
                        }
                    },
                )
            ]
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert report["case_results"][0]["passed"] is True
    assert report["suite_summary"]["failed_cases"] == 0
    assert report["refusal_summary"]["required_categories_passed"] is True
    assert report["refusal_summary"]["required_marker_coverage_passed"] is False
    assert report["contract_gates"]["required_refusal_categories"]["passed"] is True
    assert report["contract_gates"]["required_refusal_markers"]["passed"] is False
    assert report["contract_gates"]["required_refusal_markers"]["missing"] == {"no_evidence": ["knowledge base"]}
    assert report["run_passed"] is False



def test_run_chat_eval_cases_contract_gate_blocks_missing_negative_contract_category() -> None:
    """逐题通过但 negative contract 类别覆盖不足时，run_passed 应失败。"""
    schema = {
        "dataset_name": "demo-negative-contract",
        "evaluation_mode": "healthy",
        "run_gates": {},
        "required_negative_contract_categories": ["process_boundary", "scope_contract"],
    }
    case = {
        "case_id": "negative-contract-1",
        "kb_id": "kb-a",
        "expected_scope_type": "single_kb",
        "expected_isolation_level": "physical_isolated",
        "question": "What is not an authorization boundary, and what remains the access-control boundary?",
        "source_doc": "workflow-boundary.md",
        "modality": "markdown",
        "answer_style": "policy",
        "difficulty": "medium",
        "category": "process_boundary",
        "answerable": True,
        "expected_keypoints": ["cutover/runbook/", "knowledge base level"],
        "required_evidence_docs": ["workflow-boundary.md"],
        "expected_source_count": 1,
        "preview_required": False,
        "preview_terms": [],
        "forbidden_terms": ["authorization boundary is the folder path"],
        "judge_focus": ["factual_accuracy", "groundedness"],
    }
    client = FakeClient(
        {
            "/api/chat/query": [
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": ["kb-a"],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": ["kb-a"],
                            "is_default_deny_applied": False,
                            "isolation_level": "physical_isolated",
                            "answer": "The cutover/runbook/ folder is not the authorization boundary; the knowledge base level remains the access-control boundary.",
                            "sources": [{"file": "workflow-boundary.md"}],
                            "evidence": [{"title": "workflow-boundary.md"}],
                        }
                    },
                )
            ]
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert report["case_results"][0]["passed"] is True
    assert report["suite_summary"]["failed_cases"] == 0
    assert report["negative_contract_summary"]["required_categories_passed"] is False
    assert report["negative_contract_summary"]["missing_required_categories"] == ["scope_contract"]
    assert report["contract_gates"]["required_negative_contract_categories"]["passed"] is False
    assert report["contract_gates"]["required_negative_contract_categories"]["missing"] == ["scope_contract"]
    assert report["run_passed"] is False


def test_run_chat_eval_cases_contract_gate_blocks_missing_negative_contract_marker() -> None:
    """negative contract 即便样本通过，若缺少关键 boundary marker，run_passed 也应失败。"""
    schema = {
        "dataset_name": "demo-negative-contract-marker",
        "evaluation_mode": "healthy",
        "run_gates": {},
        "required_negative_contract_categories": ["process_boundary"],
        "required_negative_contract_markers_by_category": {"process_boundary": ["authorization boundary"]},
    }
    case = {
        "case_id": "negative-contract-marker-1",
        "kb_id": "kb-a",
        "expected_scope_type": "single_kb",
        "expected_isolation_level": "physical_isolated",
        "question": "What remains the access-control boundary here?",
        "source_doc": "workflow-boundary.md",
        "modality": "markdown",
        "answer_style": "policy",
        "difficulty": "medium",
        "category": "process_boundary",
        "answerable": True,
        "expected_keypoints": ["knowledge base level"],
        "required_evidence_docs": ["workflow-boundary.md"],
        "expected_source_count": 1,
        "preview_required": False,
        "preview_terms": [],
        "forbidden_terms": ["folder path is the only boundary"],
        "judge_focus": ["factual_accuracy", "groundedness"],
    }
    client = FakeClient(
        {
            "/api/chat/query": [
                FakeResponse(
                    200,
                    {
                        "data": {
                            "requested_scope_type": "single_kb",
                            "requested_kb_ids": ["kb-a"],
                            "effective_scope_type": "single_kb",
                            "effective_kb_ids": ["kb-a"],
                            "is_default_deny_applied": False,
                            "isolation_level": "physical_isolated",
                            "answer": "The knowledge base level remains the access-control boundary.",
                            "sources": [{"file": "workflow-boundary.md"}],
                            "evidence": [{"title": "workflow-boundary.md"}],
                        }
                    },
                )
            ]
        }
    )

    report = run_chat_eval_cases(client, [case], schema)

    assert report["case_results"][0]["passed"] is True
    assert report["negative_contract_summary"]["required_categories_passed"] is True
    assert report["negative_contract_summary"]["required_marker_coverage_passed"] is False
    assert report["contract_gates"]["required_negative_contract_categories"]["passed"] is True
    assert report["contract_gates"]["required_negative_contract_markers"]["passed"] is False
    assert report["contract_gates"]["required_negative_contract_markers"]["missing"] == {
        "process_boundary": ["authorization boundary"]
    }
    assert report["run_passed"] is False




def test_run_eval_v1_semireal_produces_full_report(tmp_path: Path) -> None:
    """eval v1 半真实运行应产生稳定报告与 artifact。"""
    report = run_eval_v1_semireal(output_dir=tmp_path)

    assert report["dataset_name"] == "local_multi_kb_eval_v1"
    assert report["evaluation_mode"] == "healthy"
    assert report["run_passed"] is True
    assert report["refusal_summary"]["refusal_case_count"] == 9
    assert report["refusal_summary"]["required_categories_passed"] is True
    assert report["refusal_summary"]["required_marker_coverage_passed"] is True
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
    assert "Refusal 覆盖摘要" in markdown_text
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
    assert "Refusal 覆盖摘要" in markdown_text

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
    assert report["refusal_summary"]["refusal_case_count"] == 20
    assert report["refusal_summary"]["required_categories_passed"] is True
    assert report["refusal_summary"]["required_marker_coverage_passed"] is True
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




def test_run_eval_semireal_suite_aggregates_layer_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    smoke_cases = tmp_path / "smoke-cases.json"
    smoke_schema = tmp_path / "smoke-schema.json"
    hard_cases = tmp_path / "hard-cases.json"
    hard_schema = tmp_path / "hard-schema.json"
    for path in [smoke_cases, smoke_schema, hard_cases, hard_schema]:
        path.write_text("{}", encoding="utf-8")

    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite_name": "demo-layered-suite",
                "strategy": "test",
                "layers": [
                    {
                        "name": "smoke",
                        "purpose": "quick-check",
                        "dataset_name": "demo-smoke",
                        "target_case_count": 2,
                        "cases_path": str(smoke_cases),
                        "schema_path": str(smoke_schema),
                    },
                    {
                        "name": "hard",
                        "purpose": "bug-hunt",
                        "dataset_name": "demo-hard",
                        "target_case_count": 3,
                        "cases_path": str(hard_cases),
                        "schema_path": str(hard_schema),
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def fake_run_eval_semireal(*, cases_path: str | Path, schema_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
        layer_name = "smoke" if "smoke" in str(cases_path) else "hard"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        if layer_name == "smoke":
            summary = {
                "total_cases": 2,
                "passed_cases": 2,
                "failed_cases": 0,
                "pass_rate": 1.0,
                "category_breakdown": {"smoke": {"count": 2, "passed": 2, "pass_rate": 1.0}},
            }
            return {
                "dataset_name": "demo-smoke",
                "evaluation_mode": "healthy",
                "run_passed": True,
                "suite_summary": summary,
                "run_gates": {"scope_pass_rate_min": {"passed": True}},
                "contract_gates": {},
                "artifacts": {"markdown": str((output_dir / "smoke.md").resolve())},
                "failures": [],
                "failure_stage_breakdown": {},
            }

        summary = {
            "total_cases": 3,
            "passed_cases": 1,
            "failed_cases": 2,
            "pass_rate": 1 / 3,
            "category_breakdown": {
                "evidence_insufficient": {"count": 2, "passed": 0, "pass_rate": 0.0},
                "similar_document_confusion": {"count": 1, "passed": 1, "pass_rate": 1.0},
            },
        }
        return {
            "dataset_name": "demo-hard",
            "evaluation_mode": "diagnostic",
            "run_passed": False,
            "suite_summary": summary,
            "run_gates": {"source_count_match_rate_min": {"passed": False}},
            "contract_gates": {"required_negative_contract_categories": {"passed": False}},
            "diagnostic_gates": {"case_expectation_match_rate_min": {"passed": False}},
            "artifacts": {"markdown": str((output_dir / "hard.md").resolve())},
            "failures": [{"case_id": "hard-001"}, {"case_id": "hard-002"}],
            "failure_stage_breakdown": {"quality_gate": 2},
        }

    monkeypatch.setattr("tests.api.chat_eval_runner.run_eval_semireal", fake_run_eval_semireal)

    report = run_eval_semireal_suite(suite_path=suite_path, output_dir=tmp_path / "out")

    assert report["suite_name"] == "demo-layered-suite"
    assert report["suite_passed"] is False
    assert report["totals"] == {
        "target_cases": 5,
        "actual_cases": 5,
        "passed_cases": 3,
        "failed_cases": 2,
        "pass_rate": pytest.approx(0.6),
        "passed_layers": 1,
        "failed_layers": 1,
    }
    assert [item["name"] for item in report["layer_summaries"]] == ["smoke", "hard"]
    hard_layer = report["layer_summaries"][1]
    assert hard_layer["failed_run_gates"] == ["source_count_match_rate_min"]
    assert hard_layer["failed_contract_gates"] == ["required_negative_contract_categories"]
    assert hard_layer["failed_diagnostic_gates"] == ["case_expectation_match_rate_min"]
    assert hard_layer["failure_case_ids"] == ["hard-001", "hard-002"]
    assert hard_layer["weakest_categories"][0]["category"] == "evidence_insufficient"

    json_path = Path(report["artifacts"]["json"])
    markdown_path = Path(report["artifacts"]["markdown"])
    assert json_path.is_file()
    assert markdown_path.is_file()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["suite_passed"] is False
    assert saved["layer_summaries"][1]["failed_run_gates"] == ["source_count_match_rate_min"]


def test_build_eval_suite_markdown_report_includes_failed_gate_details() -> None:
    """Suite Markdown 报告应展示失败 gate 的明细，尤其是 contract 模态缺口。"""
    report = {
        "suite_name": "demo-layered-suite",
        "run_at": "2026-08-27T12:00:00+08:00",
        "strategy": "layered",
        "suite_passed": False,
        "totals": {
            "target_cases": 5,
            "actual_cases": 5,
            "passed_cases": 3,
            "failed_cases": 2,
            "pass_rate": 0.6,
            "passed_layers": 1,
            "failed_layers": 1,
        },
        "layer_summaries": [
            {
                "name": "hard",
                "purpose": "bug-hunt",
                "dataset_name": "demo-hard",
                "evaluation_mode": "diagnostic",
                "target_case_count": 3,
                "actual_case_count": 3,
                "failed_cases": 2,
                "pass_rate": 1 / 3,
                "run_passed": False,
                "failed_run_gates": ["source_count_match_rate_min"],
                "failed_run_gate_details": {
                    "source_count_match_rate_min": {
                        "metric": "source_count_match_rate",
                        "actual": 0.667,
                        "minimum": 0.95,
                    }
                },
                "failed_contract_gates": ["required_negative_contract_modalities"],
                "failed_contract_gate_details": {
                    "required_negative_contract_modalities": {
                        "metric": "required_modalities_passed",
                        "actual": 0.0,
                        "minimum": 1.0,
                        "missing": ["pdf"],
                        "required_modalities_without_passed_cases": ["image_ocr"],
                    }
                },
                "failed_diagnostic_gates": ["case_expectation_match_rate_min"],
                "failed_diagnostic_gate_details": {
                    "case_expectation_match_rate_min": {
                        "metric": "case_expectation_match_rate",
                        "actual": 0.5,
                        "minimum": 1.0,
                    }
                },
                "failure_case_ids": ["hard-001", "hard-002"],
                "weakest_categories": [
                    {"category": "evidence_insufficient", "pass_rate": 0.0, "count": 2}
                ],
                "artifacts": {"markdown": "C:/demo/hard.md"},
            }
        ],
    }

    markdown = build_eval_suite_markdown_report(report)

    assert "问答分层评测报告：demo-layered-suite" in markdown
    assert "failed_contract_gate_details" in markdown
    assert "required_negative_contract_modalities" in markdown
    assert 'missing=["pdf"]' in markdown
    assert 'required_modalities_without_passed_cases=["image_ocr"]' in markdown
    assert "failed_run_gate_details" in markdown
    assert "source_count_match_rate_min" in markdown


def test_build_eval_markdown_report_includes_contract_modality_coverage_details() -> None:
    """Markdown 报告应显式展示 refusal / negative contract 的模态覆盖缺口。"""
    report = {
        "dataset_name": "demo-contract-modalities",
        "run_at": "2026-08-27T12:00:00+08:00",
        "evaluation_mode": "healthy",
        "run_passed": False,
        "suite_summary": {
            "total_cases": 2,
            "passed_cases": 1,
            "failed_cases": 1,
            "pass_rate": 0.5,
            "pass_rate_ci95": {"low": 0.1, "high": 0.9},
            "scope_pass_rate": 1.0,
            "average_keypoint_coverage": 0.75,
            "total_keypoints": 4,
            "matched_keypoints": 3,
            "keypoint_hit_rate": 0.75,
            "evidence_expected_cases": 1,
            "evidence_hit_cases": 1,
            "evidence_hit_rate": 1.0,
            "preview_required_cases": 0,
            "preview_resolved_cases": 0,
            "preview_resolvable_rate": 1.0,
            "preview_term_total": 0,
            "preview_term_hits": 0,
            "preview_term_hit_rate": 1.0,
            "source_count_match_rate": 1.0,
            "blocked_term_hit_cases": 0,
            "forbidden_term_clean_rate": 1.0,
        },
        "run_gates": {},
        "contract_gates": {
            "required_refusal_modalities": {
                "metric": "required_modalities_passed",
                "actual": 0.0,
                "minimum": 1.0,
                "passed": False,
            },
            "required_refusal_modality_markers": {
                "metric": "required_modality_marker_coverage_passed",
                "actual": 0.0,
                "minimum": 1.0,
                "passed": False,
                "detail": {"pdf": {"no_evidence": ["knowledge base"]}},
            },
            "required_negative_contract_modalities": {
                "metric": "required_modalities_passed",
                "actual": 0.0,
                "minimum": 1.0,
                "passed": False,
            },
            "required_negative_contract_modality_markers": {
                "metric": "required_modality_marker_coverage_passed",
                "actual": 0.0,
                "minimum": 1.0,
                "passed": False,
                "detail": {"image_ocr": {"process_boundary": ["authorization boundary"]}},
            },
        },
        "preview_stats": {"required_cases": 0, "requested_cases": 0, "skipped_cases": 0},
        "refusal_summary": {
            "refusal_case_count": 1,
            "passed_refusal_cases": 1,
            "failed_refusal_cases": 0,
            "refusal_pass_rate": 1.0,
            "required_categories_passed": True,
            "required_marker_coverage_passed": True,
            "required_modalities_passed": False,
            "missing_required_categories": [],
            "required_categories_without_passed_cases": [],
            "missing_required_modalities": ["image_ocr"],
            "required_modalities_without_passed_cases": ["pdf"],
            "category_breakdown": {
                "no_evidence": {
                    "count": 1,
                    "passed": 1,
                    "failed": 0,
                    "pass_rate": 1.0,
                    "required_markers": {
                        "knowledge base": {"covered": True, "hit_cases": 1, "case_ids": ["ref-1"]},
                    },
                }
            },
            "modality_breakdown": {
                "markdown": {"count": 1, "passed": 1, "failed": 0, "pass_rate": 1.0},
                "pdf": {"count": 1, "passed": 0, "failed": 1, "pass_rate": 0.0},
                "image_ocr": {"count": 0, "passed": 0, "failed": 0, "pass_rate": 0.0},
            },
        },
        "negative_contract_summary": {
            "negative_contract_case_count": 1,
            "passed_negative_contract_cases": 0,
            "failed_negative_contract_cases": 1,
            "negative_contract_pass_rate": 0.0,
            "required_categories_passed": True,
            "required_modalities_passed": False,
            "missing_required_categories": [],
            "required_categories_without_passed_cases": [],
            "missing_required_modalities": ["pdf"],
            "required_modalities_without_passed_cases": ["image_ocr"],
            "category_breakdown": {
                "process_boundary": {"count": 1, "passed": 0, "failed": 1, "pass_rate": 0.0}
            },
            "modality_breakdown": {
                "markdown": {"count": 1, "passed": 0, "failed": 1, "pass_rate": 0.0},
                "pdf": {"count": 0, "passed": 0, "failed": 0, "pass_rate": 0.0},
                "image_ocr": {"count": 0, "passed": 0, "failed": 0, "pass_rate": 0.0},
            },
        },
        "failure_stage_breakdown": {"quality_gate": 1},
        "failures": [{"case_id": "neg-1", "failure_stage": "quality_gate"}],
    }

    markdown_text = build_eval_markdown_report(report)

    assert "required_refusal_modalities" in markdown_text
    assert "required_refusal_modality_markers" in markdown_text
    assert "required_negative_contract_modalities" in markdown_text
    assert "required_negative_contract_modality_markers" in markdown_text
    assert "required_modality_marker_coverage_passed" in markdown_text
    assert "required_modalities_passed" in markdown_text
    assert "missing_required_modalities" in markdown_text
    assert "required_modalities_without_passed_cases" in markdown_text
    assert "| image_ocr | 0 | 0 | 0 | 0.000 |" in markdown_text
    assert "| pdf | 1 | 0 | 1 | 0.000 |" in markdown_text
