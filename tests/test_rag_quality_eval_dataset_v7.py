from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_rag_quality_fixtures import load_eval_schema, summarize_eval_cases, validate_eval_cases_file

EVAL_DIR = Path("tests/fixtures/rag_quality/eval_v7")
EVAL_SCHEMA = EVAL_DIR / "schema.json"
EVAL_CASES = EVAL_DIR / "cases.json"


@pytest.fixture(scope="module")
def eval_schema() -> dict[str, Any]:
    return load_eval_schema(EVAL_SCHEMA)


@pytest.fixture(scope="module")
def eval_cases() -> list[dict[str, Any]]:
    return json.loads(EVAL_CASES.read_text(encoding="utf-8"))


def test_eval_v7_schema_loads_successfully(eval_schema: dict[str, Any]) -> None:
    quality_gates = eval_schema["quality_gates"]

    assert eval_schema["dataset_name"] == "local_multi_kb_eval_v7_holdout_regression"
    assert eval_schema["evaluation_mode"] == "healthy"
    assert quality_gates["minimum_total_cases"] == 24
    assert quality_gates["minimum_cases_per_modality"] == 8
    assert quality_gates["minimum_cases_per_difficulty"] == 6
    assert quality_gates["minimum_no_evidence_cases"] == 3
    assert quality_gates["minimum_preview_required_cases"] == 21
    assert quality_gates["minimum_refusal_cases_per_modality"] == 1
    assert quality_gates["minimum_cases_per_answer_style"] == 3
    assert quality_gates["minimum_cases_per_category"] == 1
    assert quality_gates["minimum_cases_per_judge_dimension"] == 3
    assert quality_gates["minimum_negative_contract_cases_per_modality"] == 2
    assert eval_schema["required_refusal_categories"] == ["no_evidence"]
    assert eval_schema["required_negative_contract_categories"] == ["process_boundary", "scope_contract"]
    assert eval_schema["required_refusal_markers_by_category"] == {
        "no_evidence": ["No confirmable information", "knowledge base"],
    }
    assert eval_schema["required_negative_contract_markers_by_category"] == {
        "process_boundary": ["folder", "knowledge base"],
        "scope_contract": ["effective_kb_ids", "single_kb"],
    }


def test_eval_v7_cases_file_passes_schema_validation() -> None:
    validate_eval_cases_file(EVAL_CASES, schema_path=EVAL_SCHEMA)


def test_eval_v7_cases_summary_matches_expected_distribution(eval_schema: dict[str, Any]) -> None:
    summary = summarize_eval_cases(EVAL_CASES, schema_path=EVAL_SCHEMA)
    quality_gates = eval_schema["quality_gates"]

    assert summary["dataset_name"] == eval_schema["dataset_name"]
    assert summary["total_cases"] == 24
    assert summary["modality_breakdown"] == {"image_ocr": 8, "markdown": 8, "pdf": 8}
    assert summary["difficulty_breakdown"] == {"complex": 9, "medium": 9, "simple": 6}
    assert summary["answer_style_breakdown"] == {
        "comparison": 3,
        "fact": 9,
        "policy": 9,
        "refusal": 3,
    }
    assert summary["category_breakdown"] == {
        "cross_document": 3,
        "evidence_operation": 3,
        "long_document": 3,
        "no_evidence": 3,
        "process_boundary": 3,
        "role_lookup": 3,
        "scope_contract": 3,
        "timeline_sla": 3,
    }
    assert summary["judge_dimension_breakdown"] == {
        "citation_accuracy": 21,
        "completeness": 21,
        "factual_accuracy": 21,
        "groundedness": 24,
        "refusal_correctness": 3,
    }
    assert summary["answerable_breakdown"] == {"answerable": 21, "no_evidence": 3}
    assert summary["refusal_case_count"] == 3
    assert summary["refusal_modality_breakdown"] == {"image_ocr": 1, "markdown": 1, "pdf": 1}
    assert summary["refusal_category_breakdown"] == {"no_evidence": 3}
    assert summary["refusal_marker_category_breakdown"] == {
        "no_evidence": {"No confirmable information": 3, "knowledge base": 3},
    }
    assert summary["negative_contract_case_count"] == 6
    assert summary["negative_contract_modality_breakdown"] == {"image_ocr": 2, "markdown": 2, "pdf": 2}
    assert summary["negative_contract_category_breakdown"] == {"process_boundary": 3, "scope_contract": 3}
    assert summary["negative_contract_marker_category_breakdown"] == {
        "process_boundary": {"folder": 2, "knowledge base": 3},
        "scope_contract": {"effective_kb_ids": 1, "single_kb": 2},
    }
    assert summary["preview_required_cases"] == 21
    assert summary["modality_judge_dimension_breakdown"] == {
        "image_ocr": {
            "citation_accuracy": 7,
            "completeness": 7,
            "factual_accuracy": 7,
            "groundedness": 8,
            "refusal_correctness": 1,
        },
        "markdown": {
            "citation_accuracy": 7,
            "completeness": 7,
            "factual_accuracy": 7,
            "groundedness": 8,
            "refusal_correctness": 1,
        },
        "pdf": {
            "citation_accuracy": 7,
            "completeness": 7,
            "factual_accuracy": 7,
            "groundedness": 8,
            "refusal_correctness": 1,
        },
    }
    assert summary["weak_signal_case_count"] == 0
    assert summary["gate_checks"] == {
        "minimum_total_cases": True,
        "minimum_cases_per_modality": True,
        "minimum_cases_per_difficulty": True,
        "minimum_no_evidence_cases": True,
        "minimum_preview_required_cases": True,
        "minimum_refusal_cases_per_modality": True,
        "minimum_cases_per_answer_style": True,
        "minimum_cases_per_category": True,
        "minimum_cases_per_judge_dimension": True,
        "minimum_negative_contract_cases_per_modality": True,
        "required_refusal_categories": True,
        "required_refusal_markers_by_category": True,
        "required_negative_contract_categories": True,
        "required_negative_contract_markers_by_category": True,
    }

    assert summary["total_cases"] >= quality_gates["minimum_total_cases"]
    for modality in eval_schema["allowed_modalities"]:
        assert summary["modality_breakdown"][modality] >= quality_gates["minimum_cases_per_modality"]
    for difficulty in eval_schema["allowed_difficulties"]:
        assert summary["difficulty_breakdown"][difficulty] >= quality_gates["minimum_cases_per_difficulty"]
    for answer_style in eval_schema["allowed_answer_styles"]:
        assert summary["answer_style_breakdown"][answer_style] >= quality_gates["minimum_cases_per_answer_style"]
    for category in eval_schema["allowed_categories"]:
        assert summary["category_breakdown"][category] >= quality_gates["minimum_cases_per_category"]

    assert summary["answerable_breakdown"]["no_evidence"] >= quality_gates["minimum_no_evidence_cases"]
    assert summary["preview_required_cases"] >= quality_gates["minimum_preview_required_cases"]
