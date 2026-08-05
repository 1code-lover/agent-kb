"""校验 eval v2 问答数据集的分布、坏样本与中文覆盖门槛。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_rag_quality_fixtures import (
    load_eval_schema,
    summarize_eval_cases,
    validate_eval_cases_file,
)

EVAL_DIR = Path("tests/fixtures/rag_quality/eval_v2")
EVAL_SCHEMA = EVAL_DIR / "schema.json"
EVAL_CASES = EVAL_DIR / "cases.json"


@pytest.fixture(scope="module")
def eval_schema() -> dict[str, Any]:
    return load_eval_schema(EVAL_SCHEMA)


@pytest.fixture(scope="module")
def eval_cases() -> list[dict[str, Any]]:
    return json.loads(EVAL_CASES.read_text(encoding="utf-8"))


def test_eval_v2_schema_loads_successfully(eval_schema: dict[str, Any]) -> None:
    quality_gates = eval_schema["quality_gates"]

    assert eval_schema["dataset_name"] == "local_multi_kb_eval_v2"
    assert quality_gates["minimum_total_cases"] == 117
    assert quality_gates["minimum_cases_per_modality"] == 39
    assert quality_gates["minimum_cases_per_difficulty"] == 39
    assert quality_gates["minimum_no_evidence_cases"] == 21
    assert quality_gates["minimum_preview_required_cases"] == 96
    assert quality_gates["minimum_cases_per_answer_style"] == 14
    assert quality_gates["minimum_cases_per_category"] == 5
    assert quality_gates["minimum_cjk_cases"] == 12
    assert quality_gates["minimum_cjk_cases_per_modality"] == 4


def test_eval_v2_cases_file_passes_schema_validation() -> None:
    validate_eval_cases_file(EVAL_CASES, schema_path=EVAL_SCHEMA)


def test_eval_v2_cases_summary_matches_expected_distribution(eval_schema: dict[str, Any]) -> None:
    summary = summarize_eval_cases(EVAL_CASES, schema_path=EVAL_SCHEMA)
    quality_gates = eval_schema["quality_gates"]

    assert summary["dataset_name"] == eval_schema["dataset_name"]
    assert summary["total_cases"] == 117
    assert summary["modality_breakdown"] == {"image_ocr": 39, "markdown": 39, "pdf": 39}
    assert summary["difficulty_breakdown"] == {"complex": 39, "medium": 39, "simple": 39}
    assert summary["answer_style_breakdown"] == {
        "comparison": 15,
        "fact": 31,
        "metrics": 14,
        "policy": 15,
        "refusal": 21,
        "summary": 21,
    }
    assert summary["category_breakdown"] == {
        "evidence_preview": 18,
        "folder_model": 20,
        "ingestion_priority": 9,
        "no_evidence": 21,
        "per_case_metrics": 5,
        "refusal_policy": 11,
        "scope_contract": 20,
        "suite_metrics": 13,
    }
    assert summary["answerable_breakdown"] == {"answerable": 96, "no_evidence": 21}
    assert summary["preview_required_cases"] == 96
    assert summary["cjk_case_count"] == 13
    assert summary["cjk_modality_breakdown"] == {"image_ocr": 4, "markdown": 4, "pdf": 5}
    assert summary["modality_difficulty_breakdown"] == {
        "image_ocr": {"complex": 13, "medium": 13, "simple": 13},
        "markdown": {"complex": 13, "medium": 13, "simple": 13},
        "pdf": {"complex": 13, "medium": 13, "simple": 13},
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
    assert summary["cjk_case_count"] >= quality_gates["minimum_cjk_cases"]
    for modality in eval_schema["allowed_modalities"]:
        assert summary["cjk_modality_breakdown"][modality] >= quality_gates["minimum_cjk_cases_per_modality"]

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
    }


def test_eval_v2_summary_marks_optional_gate_failure_when_threshold_too_high(
    tmp_path: Path,
    eval_schema: dict[str, Any],
    eval_cases: list[dict[str, Any]],
) -> None:
    schema = copy.deepcopy(eval_schema)
    schema["quality_gates"]["minimum_cases_per_answer_style"] = 15
    schema["quality_gates"]["minimum_cases_per_category"] = 6
    schema["quality_gates"]["minimum_cjk_cases"] = 14
    schema["quality_gates"]["minimum_cjk_cases_per_modality"] = 5

    schema_path = tmp_path / "schema.json"
    cases_path = tmp_path / "cases.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    cases_path.write_text(json.dumps(eval_cases, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = summarize_eval_cases(cases_path, schema_path=schema_path)

    assert summary["gate_checks"]["minimum_cases_per_answer_style"] is False
    assert summary["gate_checks"]["minimum_cases_per_category"] is False
    assert summary["gate_checks"]["minimum_cjk_cases"] is False
    assert summary["gate_checks"]["minimum_cjk_cases_per_modality"] is False


def test_eval_v2_contains_realish_ocr_stress_cases(eval_cases: list[dict[str, Any]]) -> None:
    """v2 保留扫描 PDF 与低对比度 OCR 的真实压力样本。"""
    cases_by_id = {case["case_id"]: case for case in eval_cases}

    assert cases_by_id["eval-pdf-027"]["source_doc"] == "scan-fallback.pdf"
    assert "handover window" in cases_by_id["eval-pdf-027"]["question"]
    assert any("searchable evidence" in keypoint for keypoint in cases_by_id["eval-pdf-027"]["expected_keypoints"])
    assert cases_by_id["eval-pdf-033"]["source_doc"] == "ocr-readiness.pdf"
    assert "generic failures" in cases_by_id["eval-pdf-033"]["question"]
    assert cases_by_id["eval-pdf-036"]["source_doc"] == "ocr-readiness.pdf"
    assert "what comes before OCR fallback" in cases_by_id["eval-pdf-036"]["question"]
    assert cases_by_id["eval-img-026"]["source_doc"] == "noisy-policy-board.png"
    assert "low-contrast OCR board" in cases_by_id["eval-img-026"]["question"]
    assert cases_by_id["eval-img-033"]["source_doc"] == "noisy-policy-board.png"
    assert "knowledge boundary applies" in cases_by_id["eval-img-033"]["question"]
    assert cases_by_id["eval-img-039"]["source_doc"] == "noisy-policy-board.png"
    assert "low contrast OCR fallback" in cases_by_id["eval-img-039"]["question"]
    assert cases_by_id["eval-md-032"]["source_doc"] == "refusal-guideline.md"
    assert "outside memory" in cases_by_id["eval-md-032"]["question"]


def test_eval_v2_seeds_balanced_cjk_questions_for_each_modality(eval_cases: list[dict[str, Any]]) -> None:
    """v2 为 markdown/pdf/image_ocr 都补足了中文问答覆盖。"""
    cases_by_id = {case["case_id"]: case for case in eval_cases}

    assert cases_by_id["eval-md-003"]["question"] == "请用中文概括单库回复的范围回显契约。"
    assert cases_by_id["eval-md-011"]["question"] == "在这个模型里，文件夹和知识库应该是什么关系？"
    assert cases_by_id["eval-md-036"]["question"] == "请说明 aurora ledger annex zx-73 的审批窗口规则。"
    assert cases_by_id["eval-md-038"]["question"] == "请用中文说明：文件夹为什么只是组织对象，而知识库为什么仍然是查询与访问控制边界？"
    assert cases_by_id["eval-pdf-005"]["question"] == "根据 preview guide，每条 PDF 回答都必须携带哪两个字段？"
    assert cases_by_id["eval-pdf-034"]["question"] == "根据 preview guide，PDF 证据预览至少要带哪两个字段，才能回跳原始片段？"
    assert cases_by_id["eval-pdf-038"]["question"] == "请根据 PDF folder boundary note 说明：Folder is an organization object、not an authorization boundary，以及 Knowledge Base remains the range and authorization boundary 分别意味着什么？"
    assert cases_by_id["eval-pdf-039"]["question"] == "请用中文概括 PDF scope manual：requested_scope_type、effective_kb_ids 和 isolation_level 分别有什么要求？"
    assert cases_by_id["eval-img-007"]["question"] == "图片 OCR 回答的授权边界是什么？"
    assert cases_by_id["eval-img-011"]["question"] == "根据 evidence board，证据结果至少要包含哪两个字段？"
    assert cases_by_id["eval-img-037"]["question"] == "请说明图片 scope board 的范围契约：requested_scope_type 和 effective_kb_ids 应该怎么回显？"
    assert cases_by_id["eval-img-039"]["question"] == "请用中文总结 low contrast OCR fallback：当 sparse OCR 命中不足时，为什么要说 no confirmable information，并保持 active knowledge base only 与 no fabricated memory？"
