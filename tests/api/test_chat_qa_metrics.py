"""问答 QA 指标工具测试。"""

from __future__ import annotations

import pytest

from tests.api.chat_qa_metrics import build_chat_case_report, summarize_chat_case_reports


def test_build_chat_case_report_marks_positive_case_as_passed() -> None:
    case = {
        "case_id": "case-1",
        "category": "fact",
        "expected_doc": "scope-contract.md",
        "expected_keypoints": ["requested_scope_type", "effective_kb_ids"],
        "must_not_contain": ["kb-b"],
        "preview_terms": ["requested_kb_ids", "isolation_level"],
        "expected_source_count": 1,
    }
    payload = {
        "requested_scope_type": "single_kb",
        "requested_kb_ids": ["kb-a"],
        "effective_scope_type": "single_kb",
        "effective_kb_ids": ["kb-a"],
        "is_default_deny_applied": False,
        "isolation_level": "physical_isolated",
        "answer": "requested_scope_type effective_kb_ids requested_kb_ids isolation_level",
        "sources": [{"file": "scope-contract.md"}],
        "evidence": [{"title": "scope-contract.md", "source": "scope-contract.md"}],
    }
    preview = {"excerpt": "requested_kb_ids and isolation_level are required"}

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=["kb-a"],
        expected_isolation_level="physical_isolated",
        preview_payload=preview,
    )

    assert report["passed"] is True
    assert report["answer"] == payload["answer"]
    assert report["preview_excerpt"] == preview["excerpt"]
    assert report["scope_passed"] is True
    assert report["keypoint_coverage"] == 1.0
    assert report["blocked_term_clean"] is True
    assert report["evidence_hit"] is True
    assert report["preview_resolvable"] is True
    assert report["source_count_match"] is True


def test_build_chat_case_report_marks_no_evidence_case_as_passed() -> None:
    case = {
        "case_id": "case-2",
        "category": "no-evidence",
        "expected_doc": None,
        "expected_keypoints": ["No confirmable information"],
        "must_not_contain": ["preview_locator"],
        "preview_terms": [],
        "expected_source_count": 0,
    }
    payload = {
        "requested_scope_type": "single_kb",
        "requested_kb_ids": ["kb-a"],
        "effective_scope_type": "single_kb",
        "effective_kb_ids": ["kb-a"],
        "is_default_deny_applied": False,
        "isolation_level": "physical_isolated",
        "answer": "No confirmable information is available in the current knowledge base.",
        "sources": [],
        "evidence": [],
    }

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=["kb-a"],
        expected_isolation_level="physical_isolated",
    )

    assert report["passed"] is True
    assert report["evidence_hit"] is True
    assert report["preview_required"] is False
    assert report["preview_resolvable"] is True


def test_build_chat_case_report_avoids_substring_false_positive_for_blocked_term() -> None:
    case = {
        "case_id": "case-3b",
        "category": "comparison",
        "expected_doc": "handover-sla.md",
        "expected_keypoints": ["15 minutes"],
        "must_not_contain": ["5 minutes"],
        "preview_terms": [],
        "expected_source_count": 1,
    }
    payload = {
        "requested_scope_type": "single_kb",
        "requested_kb_ids": ["kb-a"],
        "effective_scope_type": "single_kb",
        "effective_kb_ids": ["kb-a"],
        "is_default_deny_applied": False,
        "isolation_level": "physical_isolated",
        "answer": "P1 cutover incident must be escalated within 15 minutes.",
        "sources": [{"file": "handover-sla.md"}],
        "evidence": [{"title": "handover-sla.md", "source": "handover-sla.md"}],
    }

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=["kb-a"],
        expected_isolation_level="physical_isolated",
    )

    assert report["passed"] is True
    assert report["blocked_term_clean"] is True
    assert report["blocked_term_hits"] == []


def test_build_chat_case_report_detects_blocked_term_and_preview_failure() -> None:
    case = {
        "case_id": "case-3",
        "category": "policy",
        "expected_doc": "refusal-guideline.md",
        "expected_keypoints": ["must not fabricate"],
        "must_not_contain": ["kb-b"],
        "preview_terms": ["outside memory"],
        "expected_source_count": 1,
    }
    payload = {
        "requested_scope_type": "single_kb",
        "requested_kb_ids": ["kb-a"],
        "effective_scope_type": "single_kb",
        "effective_kb_ids": ["kb-a"],
        "is_default_deny_applied": False,
        "isolation_level": "physical_isolated",
        "answer": "must not fabricate, but kb-b is mentioned here",
        "sources": [{"file": "refusal-guideline.md"}],
        "evidence": [{"title": "refusal-guideline.md", "source": "refusal-guideline.md"}],
    }
    preview = {"excerpt": "active knowledge base only"}

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=["kb-a"],
        expected_isolation_level="physical_isolated",
        preview_payload=preview,
    )

    assert report["passed"] is False
    assert report["blocked_term_clean"] is False
    assert report["blocked_term_hits"] == ["kb-b"]
    assert report["preview_resolvable"] is False
    assert report["preview_term_coverage"] == 0.0


def test_build_chat_case_report_allows_contextual_negation_of_blocked_term() -> None:
    case = {
        "case_id": "case-3c",
        "category": "comparison",
        "expected_doc": "long-cutover-handbook-board.png",
        "expected_keypoints": ["preview_locator", "21:50 Beijing time"],
        "must_not_contain": ["18:20"],
        "preview_terms": [],
        "expected_source_count": 1,
    }
    payload = {
        "requested_scope_type": "single_kb",
        "requested_kb_ids": ["kb-a"],
        "effective_scope_type": "single_kb",
        "effective_kb_ids": ["kb-a"],
        "is_default_deny_applied": False,
        "isolation_level": "physical_isolated",
        "answer": "preview_locator must stay aligned with the cited evidence. Legacy rehearsal 18:20 is retired and must not be used for the live answer. The live checkpoint is 21:50 Beijing time.",
        "sources": [{"file": "long-cutover-handbook-board.png"}],
        "evidence": [{"title": "long-cutover-handbook-board.png", "source": "long-cutover-handbook-board.png"}],
    }

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=["kb-a"],
        expected_isolation_level="physical_isolated",
    )

    assert report["passed"] is True
    assert report["blocked_term_clean"] is True
    assert report["blocked_term_hits"] == []


def test_build_chat_case_report_still_flags_positive_blocked_term_usage() -> None:
    case = {
        "case_id": "case-3d",
        "category": "comparison",
        "expected_doc": "long-cutover-handbook-board.png",
        "expected_keypoints": ["18:20"],
        "must_not_contain": ["18:20"],
        "preview_terms": [],
        "expected_source_count": 1,
    }
    payload = {
        "requested_scope_type": "single_kb",
        "requested_kb_ids": ["kb-a"],
        "effective_scope_type": "single_kb",
        "effective_kb_ids": ["kb-a"],
        "is_default_deny_applied": False,
        "isolation_level": "physical_isolated",
        "answer": "The live checkpoint is 18:20 Beijing time.",
        "sources": [{"file": "long-cutover-handbook-board.png"}],
        "evidence": [{"title": "long-cutover-handbook-board.png", "source": "long-cutover-handbook-board.png"}],
    }

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=["kb-a"],
        expected_isolation_level="physical_isolated",
    )

    assert report["passed"] is False
    assert report["blocked_term_clean"] is False
    assert report["blocked_term_hits"] == ["18:20"]


def test_summarize_chat_case_reports_calculates_suite_metrics() -> None:
    reports = [
        {
            "case_id": "a",
            "category": "fact",
            "passed": True,
            "scope_passed": True,
            "keypoint_total": 2,
            "keypoint_hits": ["kp-1", "kp-2"],
            "keypoint_coverage": 1.0,
            "expected_doc": "a.md",
            "required_evidence_docs": [],
            "expected_source_count": 1,
            "evidence_hit": True,
            "preview_required": True,
            "preview_resolvable": True,
            "preview_term_total": 2,
            "preview_term_hits": ["term-1", "term-2"],
            "source_count_match": True,
            "blocked_term_clean": True,
        },
        {
            "case_id": "b",
            "category": "policy",
            "passed": False,
            "scope_passed": True,
            "keypoint_total": 2,
            "keypoint_hits": ["kp-1"],
            "keypoint_coverage": 0.5,
            "expected_doc": "b.md",
            "required_evidence_docs": [],
            "expected_source_count": 1,
            "evidence_hit": False,
            "preview_required": False,
            "preview_resolvable": True,
            "preview_term_total": 0,
            "preview_term_hits": [],
            "source_count_match": False,
            "blocked_term_clean": True,
        },
    ]

    summary = summarize_chat_case_reports(reports)

    assert summary["total_cases"] == 2
    assert summary["passed_cases"] == 1
    assert summary["failed_cases"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["pass_rate_ci95"]["low"] == pytest.approx(0.0945286548)
    assert summary["pass_rate_ci95"]["high"] == pytest.approx(0.9054713452)
    assert summary["scope_pass_rate"] == 1.0
    assert summary["average_keypoint_coverage"] == 0.75
    assert summary["total_keypoints"] == 4
    assert summary["matched_keypoints"] == 3
    assert summary["missing_keypoints"] == 1
    assert summary["keypoint_hit_rate"] == 0.75
    assert summary["evidence_expected_cases"] == 2
    assert summary["evidence_hit_cases"] == 1
    assert summary["evidence_hit_rate"] == 0.5
    assert summary["preview_required_cases"] == 1
    assert summary["preview_resolved_cases"] == 1
    assert summary["preview_resolvable_rate"] == 1.0
    assert summary["preview_term_total"] == 2
    assert summary["preview_term_hits"] == 2
    assert summary["preview_term_hit_rate"] == 1.0
    assert summary["source_count_match_rate"] == 0.5
    assert summary["blocked_term_hit_cases"] == 0
    assert summary["forbidden_term_clean_rate"] == 1.0
    assert summary["category_breakdown"]["fact"]["pass_rate"] == 1.0
    assert summary["category_breakdown"]["fact"]["pass_rate_ci95"]["low"] == pytest.approx(0.2065432915)
    assert summary["category_breakdown"]["fact"]["pass_rate_ci95"]["high"] == 1.0
    assert summary["category_breakdown"]["policy"]["pass_rate"] == 0.0
    assert summary["category_breakdown"]["policy"]["pass_rate_ci95"]["low"] == 0.0
    assert summary["category_breakdown"]["policy"]["pass_rate_ci95"]["high"] == pytest.approx(0.7934567085)


def test_summarize_chat_case_reports_handles_empty_input() -> None:
    summary = summarize_chat_case_reports([])

    assert summary["total_cases"] == 0
    assert summary["pass_rate"] == 0.0
    assert summary["pass_rate_ci95"] == {"low": 0.0, "high": 0.0}
    assert summary["total_keypoints"] == 0
    assert summary["preview_required_cases"] == 0
    assert summary["category_breakdown"] == {}
