"""验证 eval v6 数据集与统一业务加诊断评测配置。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_rag_quality_fixtures import (
    load_eval_schema,
    summarize_eval_cases,
    validate_eval_cases_file,
)

EVAL_DIR = Path("tests/fixtures/rag_quality/eval_v6")
EVAL_SCHEMA = EVAL_DIR / "schema.json"
EVAL_CASES = EVAL_DIR / "cases.json"


@pytest.fixture(scope="module")
def eval_schema() -> dict[str, Any]:
    return load_eval_schema(EVAL_SCHEMA)


@pytest.fixture(scope="module")
def eval_cases() -> list[dict[str, Any]]:
    return json.loads(EVAL_CASES.read_text(encoding="utf-8"))


def test_eval_v6_schema_loads_successfully(eval_schema: dict[str, Any]) -> None:
    """验证 eval v6 schema 已声明 diagnostic 所需的关键门槛。"""
    quality_gates = eval_schema["quality_gates"]
    diagnostic_gates = eval_schema["diagnostic_gates"]

    assert eval_schema["dataset_name"] == "local_multi_kb_eval_v6_business_plus_diagnostic"
    assert eval_schema["evaluation_mode"] == "diagnostic"
    assert eval_schema["required_weak_signal_tags"] == [
        "ocr_no_text",
        "ocr_failed",
        "dependency_missing",
        "nodes_without_embedding",
        "zero_text_content",
        "asset_registered_without_index",
    ]
    assert quality_gates["minimum_total_cases"] == 78
    assert quality_gates["minimum_cases_per_modality"] == 24
    assert quality_gates["minimum_cases_per_difficulty"] == 24
    assert quality_gates["minimum_no_evidence_cases"] == 17
    assert quality_gates["minimum_preview_required_cases"] == 58
    assert quality_gates["minimum_cases_per_answer_style"] == 7
    assert quality_gates["minimum_cases_per_category"] == 3
    assert quality_gates["minimum_cjk_cases"] == 54
    assert quality_gates["minimum_cjk_cases_per_modality"] == 18
    assert quality_gates["minimum_weak_signal_cases"] == 5
    assert diagnostic_gates["case_expectation_match_rate_min"] == 1.0
    assert diagnostic_gates["minimum_weak_signal_kb_count"] == 3
    assert diagnostic_gates["minimum_weak_signal_modality_count"] == 2
    assert diagnostic_gates["required_signal_tags"] == eval_schema["required_weak_signal_tags"]


def test_eval_v6_cases_file_passes_schema_validation() -> None:
    """验证 eval v6 cases 文件可以通过 schema 校验。"""
    validate_eval_cases_file(EVAL_CASES, schema_path=EVAL_SCHEMA)


def test_eval_v6_cases_summary_matches_expected_distribution(eval_schema: dict[str, Any]) -> None:
    """验证 eval v6 的样本分布与弱信号覆盖符合预期。"""
    summary = summarize_eval_cases(EVAL_CASES, schema_path=EVAL_SCHEMA)
    quality_gates = eval_schema["quality_gates"]

    assert summary["dataset_name"] == eval_schema["dataset_name"]
    assert summary["total_cases"] == 78
    assert summary["modality_breakdown"] == {"image_ocr": 27, "markdown": 24, "pdf": 27}
    assert summary["difficulty_breakdown"] == {"complex": 24, "medium": 24, "simple": 30}
    assert summary["answer_style_breakdown"] == {
        "comparison": 7,
        "fact": 24,
        "policy": 10,
        "refusal": 20,
        "summary": 17,
    }
    assert summary["category_breakdown"] == {
        "approval_summary": 10,
        "cross_document": 6,
        "evidence_operation": 9,
        "hard_refusal": 3,
        "long_document": 4,
        "no_evidence": 14,
        "process_boundary": 12,
        "role_lookup": 8,
        "scope_contract": 4,
        "timeline_sla": 8,
    }
    assert summary["answerable_breakdown"] == {"answerable": 58, "no_evidence": 20}
    assert summary["preview_required_cases"] == 58
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
    assert summary["cjk_case_count"] == 54
    assert summary["cjk_modality_breakdown"] == {"image_ocr": 18, "markdown": 18, "pdf": 18}
    assert summary["modality_difficulty_breakdown"] == {
        "image_ocr": {"complex": 7, "medium": 9, "simple": 11},
        "markdown": {"complex": 9, "medium": 6, "simple": 9},
        "pdf": {"complex": 8, "medium": 9, "simple": 10},
    }

    assert summary["total_cases"] >= quality_gates["minimum_total_cases"]
    for modality in eval_schema["allowed_modalities"]:
        assert summary["modality_breakdown"][modality] >= quality_gates["minimum_cases_per_modality"]
        assert summary["cjk_modality_breakdown"][modality] >= quality_gates["minimum_cjk_cases_per_modality"]
    for difficulty in eval_schema["allowed_difficulties"]:
        assert summary["difficulty_breakdown"][difficulty] >= quality_gates["minimum_cases_per_difficulty"]
    for answer_style in eval_schema["allowed_answer_styles"]:
        assert summary["answer_style_breakdown"][answer_style] >= quality_gates["minimum_cases_per_answer_style"]
    for category in eval_schema["allowed_categories"]:
        assert summary["category_breakdown"][category] >= quality_gates["minimum_cases_per_category"]

    assert summary["answerable_breakdown"]["no_evidence"] >= quality_gates["minimum_no_evidence_cases"]
    assert summary["preview_required_cases"] >= quality_gates["minimum_preview_required_cases"]
    assert summary["weak_signal_case_count"] >= quality_gates["minimum_weak_signal_cases"]
    assert summary["cjk_case_count"] >= quality_gates["minimum_cjk_cases"]
    assert summary["gate_checks"] == {
        "minimum_total_cases": True,
        "minimum_cases_per_modality": True,
        "minimum_cases_per_difficulty": True,
        "minimum_no_evidence_cases": True,
        "minimum_preview_required_cases": True,
        "minimum_cases_per_answer_style": True,
        "minimum_cases_per_category": True,
        "minimum_cjk_cases": True,
        "minimum_cjk_cases_per_modality": True,
        "minimum_weak_signal_cases": True,
        "required_weak_signal_tags": True,
    }
