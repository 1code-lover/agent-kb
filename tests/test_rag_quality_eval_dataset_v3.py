"""?? eval v3 ???????????????"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.validate_rag_quality_fixtures import (
    load_eval_schema,
    summarize_eval_cases,
    validate_eval_cases_file,
)

EVAL_DIR = Path("tests/fixtures/rag_quality/eval_v3")
EVAL_SCHEMA = EVAL_DIR / "schema.json"
EVAL_CASES = EVAL_DIR / "cases.json"


@pytest.fixture(scope="module")
def eval_schema() -> dict[str, Any]:
    return load_eval_schema(EVAL_SCHEMA)


def test_eval_v3_schema_loads_successfully(eval_schema: dict[str, Any]) -> None:
    """eval v3 schema ??? diagnostic ???????? gate?"""
    quality_gates = eval_schema["quality_gates"]
    diagnostic_gates = eval_schema["diagnostic_gates"]

    assert eval_schema["dataset_name"] == "local_multi_kb_eval_v3"
    assert eval_schema["evaluation_mode"] == "diagnostic"
    assert eval_schema["required_weak_signal_tags"] == [
        "ocr_no_text",
        "ocr_failed",
        "dependency_missing",
        "nodes_without_embedding",
        "zero_text_content",
        "asset_registered_without_index",
    ]
    assert quality_gates["minimum_total_cases"] == 6
    assert quality_gates["minimum_cases_per_modality"] == 3
    assert quality_gates["minimum_weak_signal_cases"] == 5
    assert diagnostic_gates["case_expectation_match_rate_min"] == 1.0
    assert diagnostic_gates["minimum_weak_signal_kb_count"] == 2
    assert diagnostic_gates["minimum_weak_signal_modality_count"] == 2
    assert diagnostic_gates["required_signal_tags"] == [
        "ocr_no_text",
        "ocr_failed",
        "dependency_missing",
        "nodes_without_embedding",
        "zero_text_content",
        "asset_registered_without_index",
    ]


def test_eval_v3_cases_file_passes_schema_validation() -> None:
    """eval v3 cases ????? schema ???"""
    validate_eval_cases_file(EVAL_CASES, schema_path=EVAL_SCHEMA)


def test_eval_v3_cases_summary_matches_expected_distribution(eval_schema: dict[str, Any]) -> None:
    """eval v3 ??? 6 ??????? 2 ???? 3 ???????"""
    summary = summarize_eval_cases(EVAL_CASES, schema_path=EVAL_SCHEMA)

    assert summary["dataset_name"] == "local_multi_kb_eval_v3"
    assert summary["total_cases"] == 6
    assert summary["modality_breakdown"] == {"image_ocr": 3, "pdf": 3}
    assert summary["difficulty_breakdown"] == {"simple": 6}
    assert summary["answer_style_breakdown"] == {"policy": 4, "refusal": 2}
    assert summary["category_breakdown"] == {"no_evidence": 2, "scope_contract": 4}
    assert summary["answerable_breakdown"] == {"answerable": 4, "no_evidence": 2}
    assert summary["preview_required_cases"] == 4
    assert summary["weak_signal_case_count"] == 5
    assert summary["weak_signal_breakdown"] == {
        "asset_registered_without_index": 3,
        "dependency_missing": 1,
        "nodes_without_embedding": 1,
        "ocr_failed": 2,
        "ocr_no_text": 1,
        "zero_text_content": 1,
    }
    assert summary["weak_signal_modality_breakdown"] == {"image_ocr": 3, "pdf": 2}
    assert summary["gate_checks"] == {
        "minimum_total_cases": True,
        "minimum_cases_per_modality": True,
        "minimum_cases_per_difficulty": True,
        "minimum_no_evidence_cases": True,
        "minimum_preview_required_cases": True,
        "minimum_cases_per_answer_style": True,
        "minimum_cases_per_category": True,
        "minimum_weak_signal_cases": True,
        "required_weak_signal_tags": True,
    }
