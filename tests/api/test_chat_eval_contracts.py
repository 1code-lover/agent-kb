from __future__ import annotations

import pytest

from tests.api.chat_eval_contracts import (
    build_negative_contract_summary,
    build_refusal_summary,
    evaluate_contract_gates,
    evaluate_report_run_passed,
)


def test_build_refusal_summary_tracks_required_categories_and_markers() -> None:
    """refusal 摘要应正确统计必需类别与 marker 覆盖。"""
    schema = {
        "required_refusal_categories": ["no_evidence", "scope_contract"],
        "required_refusal_markers_by_category": {
            "no_evidence": ["No confirmable information", "knowledge base"],
            "scope_contract": ["must not fabricate"],
        },
    }
    reports = [
        {
            "case_id": "ref-1",
            "answer_style": "refusal",
            "category": "no_evidence",
            "answer": "No confirmable information is available in the current knowledge base.",
            "passed": True,
        },
        {
            "case_id": "ref-2",
            "answer_style": "refusal",
            "category": "scope_contract",
            "answer": "You must not fabricate from outside memory.",
            "passed": True,
        },
    ]

    summary = build_refusal_summary(reports, schema)

    assert summary["refusal_case_count"] == 2
    assert summary["passed_refusal_cases"] == 2
    assert summary["required_categories_passed"] is True
    assert summary["required_marker_coverage_passed"] is True
    assert summary["missing_required_categories"] == []
    assert summary["required_categories_without_passed_cases"] == []
    assert summary["category_breakdown"]["no_evidence"]["required_markers"]["knowledge base"] == {
        "covered": True,
        "hit_cases": 1,
        "case_ids": ["ref-1"],
    }
    assert summary["category_breakdown"]["scope_contract"]["required_markers"]["must not fabricate"]["covered"] is True


def test_build_refusal_summary_requires_passed_cases_for_required_categories_and_markers() -> None:
    """required refusal category 若只有失败样本，不应被视作覆盖通过。"""
    schema = {
        "required_refusal_categories": ["no_evidence"],
        "required_refusal_markers_by_category": {
            "no_evidence": ["No confirmable information", "knowledge base"],
        },
    }
    reports = [
        {
            "case_id": "ref-1",
            "answer_style": "refusal",
            "category": "no_evidence",
            "answer": "No confirmable information is available in the current knowledge base.",
            "passed": False,
        }
    ]

    summary = build_refusal_summary(reports, schema)

    assert summary["refusal_case_count"] == 1
    assert summary["passed_refusal_cases"] == 0
    assert summary["missing_required_categories"] == []
    assert summary["required_categories_without_passed_cases"] == ["no_evidence"]
    assert summary["required_categories_passed"] is False
    assert summary["required_marker_coverage_passed"] is False
    assert summary["category_breakdown"]["no_evidence"] == {
        "count": 1,
        "passed": 0,
        "failed": 1,
        "pass_rate": 0.0,
        "required_markers": {
            "No confirmable information": {"covered": False, "hit_cases": 0, "case_ids": []},
            "knowledge base": {"covered": False, "hit_cases": 0, "case_ids": []},
        },
    }


def test_build_negative_contract_summary_tracks_required_categories_and_modalities() -> None:
    """negative contract 摘要应过滤非必需类别，并按 modality / marker 聚合。"""
    schema = {
        "required_negative_contract_categories": ["process_boundary", "scope_contract"],
        "required_negative_contract_markers_by_category": {
            "process_boundary": ["authorization boundary"],
            "scope_contract": ["must not fabricate"],
        },
    }
    reports = [
        {
            "case_id": "neg-1",
            "category": "process_boundary",
            "modality": "markdown",
            "answer": "The folder is not an authorization boundary; the knowledge base is.",
            "passed": True,
        },
        {
            "case_id": "neg-2",
            "category": "scope_contract",
            "modality": "image_ocr",
            "answer": "This failed run omitted the refusal contract.",
            "passed": False,
        },
        {
            "case_id": "neg-3",
            "category": "approval_summary",
            "modality": "pdf",
            "answer": "Irrelevant but passed.",
            "passed": True,
        },
    ]

    summary = build_negative_contract_summary(reports, schema)

    assert summary["negative_contract_case_count"] == 2
    assert summary["passed_negative_contract_cases"] == 1
    assert summary["failed_negative_contract_cases"] == 1
    assert summary["negative_contract_pass_rate"] == pytest.approx(0.5)
    assert summary["required_categories_passed"] is False
    assert summary["required_marker_coverage_passed"] is False
    assert summary["missing_required_categories"] == []
    assert summary["required_categories_without_passed_cases"] == ["scope_contract"]
    assert summary["category_breakdown"] == {
        "process_boundary": {
            "count": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
            "required_markers": {
                "authorization boundary": {"covered": True, "hit_cases": 1, "case_ids": ["neg-1"]},
            },
        },
        "scope_contract": {
            "count": 1,
            "passed": 0,
            "failed": 1,
            "pass_rate": 0.0,
            "required_markers": {
                "must not fabricate": {"covered": False, "hit_cases": 0, "case_ids": []},
            },
        },
    }
    assert summary["modality_breakdown"] == {
        "image_ocr": {"count": 1, "passed": 0, "failed": 1, "pass_rate": 0.0},
        "markdown": {"count": 1, "passed": 1, "failed": 0, "pass_rate": 1.0},
    }


def test_build_negative_contract_summary_requires_passed_case_for_required_category() -> None:
    """required negative contract category 若全失败，应标记为未覆盖通过。"""
    schema = {
        "required_negative_contract_categories": ["process_boundary"],
    }
    reports = [
        {
            "case_id": "neg-1",
            "category": "process_boundary",
            "modality": "markdown",
            "passed": False,
        }
    ]

    summary = build_negative_contract_summary(reports, schema)

    assert summary["negative_contract_case_count"] == 1
    assert summary["passed_negative_contract_cases"] == 0
    assert summary["missing_required_categories"] == []
    assert summary["required_categories_without_passed_cases"] == ["process_boundary"]
    assert summary["required_categories_passed"] is False


def test_evaluate_contract_gates_reports_missing_categories_and_markers() -> None:
    """contract gate 应把摘要中的缺口规整成统一的 gate 结果。"""
    refusal_summary = {
        "required_categories": ["no_evidence", "scope_contract"],
        "missing_required_categories": ["scope_contract"],
        "required_categories_without_passed_cases": [],
        "category_breakdown": {
            "no_evidence": {
                "required_markers": {
                    "knowledge base": {"covered": False},
                    "No confirmable information": {"covered": True},
                }
            }
        },
    }
    negative_contract_summary = {
        "required_categories": ["process_boundary", "scope_contract"],
        "missing_required_categories": ["scope_contract"],
        "required_categories_without_passed_cases": [],
        "category_breakdown": {
            "process_boundary": {
                "required_markers": {
                    "authorization boundary": {"covered": True},
                }
            },
            "scope_contract": {
                "required_markers": {
                    "must not fabricate": {"covered": False},
                }
            },
        },
    }

    gates = evaluate_contract_gates(refusal_summary, negative_contract_summary)

    assert gates["required_refusal_categories"] == {
        "metric": "required_categories_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 2,
        "covered_count": 1,
        "missing": ["scope_contract"],
        "required_categories_without_passed_cases": [],
        "detail": {
            "missing": ["scope_contract"],
            "required_categories_without_passed_cases": [],
        },
    }
    assert gates["required_refusal_markers"] == {
        "metric": "required_marker_coverage_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 2,
        "covered_count": 1,
        "missing": {"no_evidence": ["knowledge base"]},
        "detail": {"no_evidence": ["knowledge base"]},
    }
    assert gates["required_negative_contract_categories"] == {
        "metric": "required_categories_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 2,
        "covered_count": 1,
        "missing": ["scope_contract"],
        "required_categories_without_passed_cases": [],
        "detail": {
            "missing": ["scope_contract"],
            "required_categories_without_passed_cases": [],
        },
    }
    assert gates["required_negative_contract_markers"] == {
        "metric": "required_marker_coverage_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 2,
        "covered_count": 1,
        "missing": {"scope_contract": ["must not fabricate"]},
        "detail": {"scope_contract": ["must not fabricate"]},
    }


def test_evaluate_contract_gates_reports_categories_without_passed_cases() -> None:
    """contract gate 应区分“没测到”和“测到了但没有任何通过样本”。"""
    refusal_summary = {
        "required_categories": ["no_evidence"],
        "missing_required_categories": [],
        "required_categories_without_passed_cases": ["no_evidence"],
        "category_breakdown": {
            "no_evidence": {
                "required_markers": {
                    "No confirmable information": {"covered": False},
                }
            }
        },
    }
    negative_contract_summary = {
        "required_categories": ["process_boundary"],
        "missing_required_categories": [],
        "required_categories_without_passed_cases": ["process_boundary"],
        "category_breakdown": {
            "process_boundary": {
                "required_markers": {
                    "authorization boundary": {"covered": False},
                }
            }
        },
    }

    gates = evaluate_contract_gates(refusal_summary, negative_contract_summary)

    assert gates["required_refusal_categories"]["passed"] is False
    assert gates["required_refusal_categories"]["missing"] == []
    assert gates["required_refusal_categories"]["required_categories_without_passed_cases"] == ["no_evidence"]
    assert gates["required_refusal_categories"]["covered_count"] == 0
    assert gates["required_refusal_markers"]["passed"] is False
    assert gates["required_negative_contract_categories"]["passed"] is False
    assert gates["required_negative_contract_categories"]["missing"] == []
    assert gates["required_negative_contract_categories"]["required_categories_without_passed_cases"] == ["process_boundary"]
    assert gates["required_negative_contract_categories"]["covered_count"] == 0
    assert gates["required_negative_contract_markers"]["passed"] is False


def test_evaluate_report_run_passed_includes_contract_gates() -> None:
    """统一 run_passed 计算应在 healthy/diagnostic 模式都纳入 contract gate。"""
    healthy_result = evaluate_report_run_passed(
        evaluation_mode="healthy",
        suite_summary={"failed_cases": 0},
        run_gates={"pass_rate_min": {"passed": True}},
        contract_gates={"required_refusal_markers": {"passed": False}},
    )
    diagnostic_result = evaluate_report_run_passed(
        evaluation_mode="diagnostic",
        suite_summary={"failed_cases": 0},
        run_gates={"pass_rate_min": {"passed": True}},
        contract_gates={"required_negative_contract_categories": {"passed": False}},
        diagnostic_gates={"case_expectation_match_rate_min": {"passed": True}},
    )

    assert healthy_result is False
    assert diagnostic_result is False



def test_build_refusal_summary_tracks_required_modalities_when_schema_requires_per_modality() -> None:
    """refusal 摘要应在 schema 要求按模态覆盖时统计 passed 模态缺口。"""
    schema = {
        "allowed_modalities": ["markdown", "pdf", "image_ocr"],
        "quality_gates": {"minimum_refusal_cases_per_modality": 1},
        "required_refusal_categories": ["no_evidence"],
    }
    reports = [
        {
            "case_id": "ref-md-1",
            "answer_style": "refusal",
            "category": "no_evidence",
            "modality": "markdown",
            "answer": "No confirmable information is available in the current knowledge base.",
            "passed": True,
        },
        {
            "case_id": "ref-pdf-1",
            "answer_style": "refusal",
            "category": "no_evidence",
            "modality": "pdf",
            "answer": "This run missed the refusal contract.",
            "passed": False,
        },
    ]

    summary = build_refusal_summary(reports, schema)

    assert summary["required_modalities"] == ["markdown", "pdf", "image_ocr"]
    assert summary["missing_required_modalities"] == ["image_ocr"]
    assert summary["required_modalities_without_passed_cases"] == ["pdf"]
    assert summary["required_modalities_passed"] is False
    assert summary["modality_breakdown"] == {
        "image_ocr": {"count": 0, "passed": 0, "failed": 0, "pass_rate": 0.0},
        "markdown": {"count": 1, "passed": 1, "failed": 0, "pass_rate": 1.0},
        "pdf": {"count": 1, "passed": 0, "failed": 1, "pass_rate": 0.0},
    }


def test_build_negative_contract_summary_tracks_required_modalities_when_schema_requires_per_modality() -> None:
    """negative contract 摘要应把缺失或全失败的必需模态显式标出来。"""
    schema = {
        "allowed_modalities": ["markdown", "pdf", "image_ocr"],
        "quality_gates": {"minimum_negative_contract_cases_per_modality": 1},
        "required_negative_contract_categories": ["process_boundary"],
    }
    reports = [
        {
            "case_id": "neg-md-1",
            "category": "process_boundary",
            "modality": "markdown",
            "answer": "The folder is not the authorization boundary; the knowledge base is.",
            "passed": True,
        },
        {
            "case_id": "neg-pdf-1",
            "category": "process_boundary",
            "modality": "pdf",
            "answer": "This failed run omitted the boundary language.",
            "passed": False,
        },
    ]

    summary = build_negative_contract_summary(reports, schema)

    assert summary["required_modalities"] == ["markdown", "pdf", "image_ocr"]
    assert summary["missing_required_modalities"] == ["image_ocr"]
    assert summary["required_modalities_without_passed_cases"] == ["pdf"]
    assert summary["required_modalities_passed"] is False
    assert summary["modality_breakdown"] == {
        "image_ocr": {"count": 0, "passed": 0, "failed": 0, "pass_rate": 0.0},
        "markdown": {"count": 1, "passed": 1, "failed": 0, "pass_rate": 1.0},
        "pdf": {"count": 1, "passed": 0, "failed": 1, "pass_rate": 0.0},
    }


def test_evaluate_contract_gates_reports_required_modality_gaps() -> None:
    """contract gate 应把按模态的 refusal / negative contract 缺口提升为独立 gate。"""
    refusal_summary = {
        "required_modalities": ["markdown", "pdf", "image_ocr"],
        "missing_required_modalities": ["image_ocr"],
        "required_modalities_without_passed_cases": ["pdf"],
    }
    negative_contract_summary = {
        "required_modalities": ["markdown", "pdf", "image_ocr"],
        "missing_required_modalities": ["pdf"],
        "required_modalities_without_passed_cases": ["image_ocr"],
    }

    gates = evaluate_contract_gates(refusal_summary, negative_contract_summary)

    assert gates["required_refusal_modalities"] == {
        "metric": "required_modalities_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 3,
        "covered_count": 1,
        "missing": ["image_ocr"],
        "required_modalities_without_passed_cases": ["pdf"],
        "detail": {
            "missing": ["image_ocr"],
            "required_modalities_without_passed_cases": ["pdf"],
        },
    }
    assert gates["required_negative_contract_modalities"] == {
        "metric": "required_modalities_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 3,
        "covered_count": 1,
        "missing": ["pdf"],
        "required_modalities_without_passed_cases": ["image_ocr"],
        "detail": {
            "missing": ["pdf"],
            "required_modalities_without_passed_cases": ["image_ocr"],
        },
    }



def test_build_refusal_summary_tracks_marker_gaps_within_passed_modalities() -> None:
    """refusal 摘要应暴露“模态有通过样本但缺少必需 marker”的漂移。"""
    schema = {
        "allowed_modalities": ["markdown", "pdf"],
        "quality_gates": {"minimum_refusal_cases_per_modality": 1},
        "required_refusal_categories": ["no_evidence"],
        "required_refusal_markers_by_category": {
            "no_evidence": ["No confirmable information", "knowledge base"],
        },
    }
    reports = [
        {
            "case_id": "ref-md-1",
            "answer_style": "refusal",
            "category": "no_evidence",
            "modality": "markdown",
            "answer": "No confirmable information is available in the current knowledge base.",
            "passed": True,
        },
        {
            "case_id": "ref-pdf-1",
            "answer_style": "refusal",
            "category": "no_evidence",
            "modality": "pdf",
            "answer": "No confirmable information is available right now.",
            "passed": True,
        },
    ]

    summary = build_refusal_summary(reports, schema)

    assert summary["required_modality_marker_coverage_passed"] is False
    assert summary["required_modality_marker_required_count"] == 4
    assert summary["required_modality_marker_covered_count"] == 3
    assert summary["missing_required_markers_by_modality"] == {"pdf": {"no_evidence": ["knowledge base"]}}
    assert summary["modality_category_breakdown"]["pdf"]["no_evidence"]["required_markers"]["knowledge base"] == {
        "covered": False,
        "hit_cases": 0,
        "case_ids": [],
    }



def test_build_negative_contract_summary_tracks_marker_gaps_within_passed_modalities() -> None:
    """negative contract 摘要应暴露“模态通过但 boundary marker 缺失”的场景。"""
    schema = {
        "allowed_modalities": ["markdown", "pdf"],
        "quality_gates": {"minimum_negative_contract_cases_per_modality": 1},
        "required_negative_contract_categories": ["process_boundary"],
        "required_negative_contract_markers_by_category": {
            "process_boundary": ["authorization boundary", "knowledge base"],
        },
    }
    reports = [
        {
            "case_id": "neg-md-1",
            "category": "process_boundary",
            "modality": "markdown",
            "answer": "The knowledge base remains the authorization boundary.",
            "passed": True,
        },
        {
            "case_id": "neg-pdf-1",
            "category": "process_boundary",
            "modality": "pdf",
            "answer": "The authorization boundary remains unchanged.",
            "passed": True,
        },
    ]

    summary = build_negative_contract_summary(reports, schema)

    assert summary["required_modality_marker_coverage_passed"] is False
    assert summary["required_modality_marker_required_count"] == 4
    assert summary["required_modality_marker_covered_count"] == 3
    assert summary["missing_required_markers_by_modality"] == {
        "pdf": {"process_boundary": ["knowledge base"]}
    }
    assert summary["modality_category_breakdown"]["pdf"]["process_boundary"]["required_markers"]["knowledge base"] == {
        "covered": False,
        "hit_cases": 0,
        "case_ids": [],
    }



def test_evaluate_contract_gates_reports_required_modality_marker_gaps() -> None:
    """contract gate 应把“模态内 marker 缺失”提升为独立 gate。"""
    refusal_summary = {
        "required_modality_marker_required_count": 4,
        "required_modality_marker_covered_count": 3,
        "missing_required_markers_by_modality": {
            "pdf": {"no_evidence": ["knowledge base"]}
        },
    }
    negative_contract_summary = {
        "required_modality_marker_required_count": 2,
        "required_modality_marker_covered_count": 1,
        "missing_required_markers_by_modality": {
            "image_ocr": {"process_boundary": ["authorization boundary"]}
        },
    }

    gates = evaluate_contract_gates(refusal_summary, negative_contract_summary)

    assert gates["required_refusal_modality_markers"] == {
        "metric": "required_modality_marker_coverage_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 4,
        "covered_count": 3,
        "missing": {"pdf": {"no_evidence": ["knowledge base"]}},
        "detail": {"pdf": {"no_evidence": ["knowledge base"]}},
    }
    assert gates["required_negative_contract_modality_markers"] == {
        "metric": "required_modality_marker_coverage_passed",
        "actual": 0.0,
        "minimum": 1.0,
        "passed": False,
        "required_count": 2,
        "covered_count": 1,
        "missing": {"image_ocr": {"process_boundary": ["authorization boundary"]}},
        "detail": {"image_ocr": {"process_boundary": ["authorization boundary"]}},
    }
