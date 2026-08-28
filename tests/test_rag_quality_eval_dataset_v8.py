from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_rag_quality_fixtures import load_eval_schema, summarize_eval_cases, validate_eval_cases_file

SUITE_PATH = Path("tests/fixtures/rag_quality/eval_layered_suite.json")
SMOKE_DIR = Path("tests/fixtures/rag_quality/eval_v7")
MAIN_DIR = Path("tests/fixtures/rag_quality/eval_v8_main")
HARD_DIR = Path("tests/fixtures/rag_quality/eval_v8_hard")


@pytest.fixture(scope="module")
def suite_manifest() -> dict[str, Any]:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def main_schema() -> dict[str, Any]:
    return load_eval_schema(MAIN_DIR / "schema.json")


@pytest.fixture(scope="module")
def hard_schema() -> dict[str, Any]:
    return load_eval_schema(HARD_DIR / "schema.json")


@pytest.fixture(scope="module")
def main_cases() -> list[dict[str, Any]]:
    return json.loads((MAIN_DIR / "cases.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hard_cases() -> list[dict[str, Any]]:
    return json.loads((HARD_DIR / "cases.json").read_text(encoding="utf-8"))


def _collect_case_ids(cases: list[dict[str, Any]], predicate) -> list[str]:
    return [str(case["case_id"]) for case in cases if predicate(case)]


def test_layered_suite_manifest_points_to_expected_layers(suite_manifest: dict[str, Any]) -> None:
    assert suite_manifest["suite_name"] == "local_multi_kb_eval_v8_layered_suite"
    layers = suite_manifest["layers"]
    assert [layer["name"] for layer in layers] == ["smoke", "main", "hard"]
    assert [layer["target_case_count"] for layer in layers] == [24, 93, 39]

    for layer in layers:
        assert Path(layer["cases_path"]).exists()
        assert Path(layer["schema_path"]).exists()


def test_eval_v8_main_schema_loads_successfully(main_schema: dict[str, Any]) -> None:
    quality_gates = main_schema["quality_gates"]

    assert main_schema["dataset_name"] == "local_multi_kb_eval_v8_layered_main"
    assert main_schema["evaluation_mode"] == "diagnostic"
    assert quality_gates["minimum_total_cases"] == 93
    assert quality_gates["minimum_cases_per_modality"] == 28
    assert quality_gates["minimum_cases_per_difficulty"] == 24
    assert quality_gates["minimum_no_evidence_cases"] == 20
    assert quality_gates["minimum_preview_required_cases"] == 60
    assert quality_gates["minimum_refusal_cases_per_modality"] == 6
    assert quality_gates["minimum_cases_per_answer_style"] == 8
    assert quality_gates["minimum_cases_per_category"] == 5
    assert quality_gates["minimum_cases_per_judge_dimension"] == 20
    assert quality_gates["minimum_weak_signal_cases"] == 5
    assert quality_gates["minimum_negative_contract_cases_per_modality"] == 5
    assert quality_gates["minimum_history_grounded_cases"] == 6
    assert quality_gates["minimum_history_grounded_cases_per_modality"] == 2
    assert main_schema["required_refusal_categories"] == ["no_evidence", "hard_refusal", "scope_contract"]
    assert main_schema["required_negative_contract_categories"] == ["process_boundary", "scope_contract"]
    assert main_schema["required_refusal_markers_by_category"] == {
        "hard_refusal": ["No confirmable information", "knowledge base"],
        "no_evidence": ["No confirmable information", "knowledge base"],
        "scope_contract": ["must not fabricate", "knowledge base"],
    }
    assert main_schema["required_negative_contract_markers_by_category"] == {
        "process_boundary": ["authorization boundary", "knowledge base"],
        "scope_contract": ["must not fabricate", "effective_kb_ids"],
    }


def test_eval_v8_hard_schema_loads_successfully(hard_schema: dict[str, Any]) -> None:
    quality_gates = hard_schema["quality_gates"]

    assert hard_schema["dataset_name"] == "local_multi_kb_eval_v8_layered_hard"
    assert hard_schema["evaluation_mode"] == "healthy"
    assert hard_schema["allowed_difficulties"] == ["medium", "complex"]
    assert quality_gates["minimum_total_cases"] == 36
    assert quality_gates["minimum_cases_per_modality"] == 12
    assert quality_gates["minimum_cases_per_difficulty"] == 12
    assert quality_gates["minimum_no_evidence_cases"] == 6
    assert quality_gates["minimum_preview_required_cases"] == 30
    assert quality_gates["minimum_refusal_cases_per_modality"] == 2
    assert quality_gates["minimum_cases_per_answer_style"] == 6
    assert quality_gates["minimum_cases_per_category"] == 6
    assert quality_gates["minimum_cases_per_judge_dimension"] == 6
    assert quality_gates["minimum_negative_contract_cases_per_modality"] == 2
    assert quality_gates["minimum_history_grounded_cases"] == 6
    assert quality_gates["minimum_history_grounded_cases_per_modality"] == 2
    assert hard_schema["required_refusal_categories"] == ["evidence_insufficient"]
    assert hard_schema["required_negative_contract_categories"] == ["scope_isolation_trap"]
    assert hard_schema["required_refusal_markers_by_category"] == {
        "evidence_insufficient": ["No confirmable information", "knowledge base"],
    }
    assert hard_schema["required_negative_contract_markers_by_category"] == {
        "scope_isolation_trap": ["authorization boundary", "must not fabricate", "effective_kb_ids"],
    }


def test_eval_v8_main_cases_file_passes_schema_validation() -> None:
    validate_eval_cases_file(MAIN_DIR / "cases.json", schema_path=MAIN_DIR / "schema.json")



def test_eval_v8_main_dataset_directory_is_supported() -> None:
    validate_eval_cases_file(MAIN_DIR)
    summary = summarize_eval_cases(MAIN_DIR)

    assert summary["dataset_name"] == "local_multi_kb_eval_v8_layered_main"
    assert summary["total_cases"] == 93



def test_eval_v8_main_history_grounded_answerable_cases_are_distributed_across_modalities(
    main_cases: list[dict[str, Any]]
) -> None:
    history_answerable_case_ids = {
        modality: _collect_case_ids(
            main_cases,
            lambda case, modality=modality: case["modality"] == modality
            and case["answerable"] is True
            and bool(case.get("history_turns")),
        )
        for modality in ["markdown", "pdf", "image_ocr"]
    }

    assert history_answerable_case_ids == {
        "markdown": ["eval-v4-md-001", "eval-v5-md-002"],
        "pdf": ["eval-v4-pdf-001", "eval-v5-pdf-002"],
        "image_ocr": ["eval-v4-img-001", "eval-v5-img-002"],
    }

    summary = summarize_eval_cases(MAIN_DIR)
    assert summary["history_grounded_case_count"] == 6
    assert summary["history_grounded_modality_breakdown"] == {"image_ocr": 2, "markdown": 2, "pdf": 2}
    assert summary["gate_checks"]["minimum_history_grounded_cases"] is True
    assert summary["gate_checks"]["minimum_history_grounded_cases_per_modality"] is True



def test_eval_v8_main_history_grounded_gates_fail_when_answerable_followup_context_is_removed(
    tmp_path: Path, main_cases: list[dict[str, Any]]
) -> None:
    mutated_cases: list[dict[str, Any]] = []
    for case in main_cases:
        copied = dict(case)
        copied.pop("history_turns", None)
        mutated_cases.append(copied)

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(mutated_cases, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = summarize_eval_cases(cases_path, schema_path=MAIN_DIR / "schema.json")

    assert summary["history_grounded_case_count"] == 0
    assert summary["history_grounded_modality_breakdown"] == {}
    assert summary["gate_checks"]["minimum_history_grounded_cases"] is False
    assert summary["gate_checks"]["minimum_history_grounded_cases_per_modality"] is False



def test_eval_v8_hard_cases_file_passes_schema_validation() -> None:
    validate_eval_cases_file(HARD_DIR / "cases.json", schema_path=HARD_DIR / "schema.json")



def test_eval_v8_hard_dataset_directory_is_supported() -> None:
    validate_eval_cases_file(HARD_DIR)
    summary = summarize_eval_cases(HARD_DIR)

    assert summary["dataset_name"] == "local_multi_kb_eval_v8_layered_hard"
    assert summary["total_cases"] == 39



def test_eval_v8_main_includes_ocr_weak_signal_refusal_cases(main_cases: list[dict[str, Any]]) -> None:
    ocr_refusal_case_ids = _collect_case_ids(
        main_cases,
        lambda case: case["modality"] == "image_ocr"
        and case["answerable"] is False
        and "refusal_correctness" in case["judge_focus"]
        and bool(case.get("weak_signal_tags")),
    )

    assert ocr_refusal_case_ids == ["eval-v3-img-001", "eval-v3-img-002", "eval-v3-img-003"]



def test_eval_v8_main_includes_negative_contract_drift_cases_for_all_modalities(main_cases: list[dict[str, Any]]) -> None:
    drift_cases = {
        case["case_id"]: case
        for case in main_cases
        if case["case_id"] in {"eval-v8-main-md-019", "eval-v8-main-pdf-019", "eval-v8-main-img-019"}
    }

    assert sorted(drift_cases) == ["eval-v8-main-img-019", "eval-v8-main-md-019", "eval-v8-main-pdf-019"]
    assert drift_cases["eval-v8-main-md-019"]["expected_keypoints"] == [
        "No confirmable information",
        "current knowledge base",
        "must not fabricate from outside memory",
    ]
    assert drift_cases["eval-v8-main-pdf-019"]["expected_keypoints"] == [
        "must not fabricate from outside memory",
    ]
    assert drift_cases["eval-v8-main-img-019"]["expected_keypoints"] == [
        "not an authorization boundary",
        "knowledge base",
        "authorization boundary",
    ]



def test_eval_v8_hard_includes_preview_hygiene_cases_for_each_modality(hard_cases: list[dict[str, Any]]) -> None:
    preview_hygiene_counts = {
        modality: len(
            _collect_case_ids(
                hard_cases,
                lambda case, modality=modality: case["modality"] == modality
                and case["answerable"] is True
                and case["preview_required"] is True
                and bool(case.get("preview_terms")),
            )
        )
        for modality in ["markdown", "pdf", "image_ocr"]
    }

    assert preview_hygiene_counts == {"markdown": 11, "pdf": 11, "image_ocr": 11}



def test_eval_v8_hard_preserves_negative_coverage_triplets_per_modality(hard_cases: list[dict[str, Any]]) -> None:
    coverage = {
        modality: {
            "refusal": len(
                _collect_case_ids(
                    hard_cases,
                    lambda case, modality=modality: case["modality"] == modality
                    and case["answer_style"] == "refusal"
                    and case["category"] == "evidence_insufficient",
                )
            ),
            "scope_isolation_trap": len(
                _collect_case_ids(
                    hard_cases,
                    lambda case, modality=modality: case["modality"] == modality
                    and case["category"] == "scope_isolation_trap"
                    and case["answerable"] is True,
                )
            ),
            "multi_source_preview": len(
                _collect_case_ids(
                    hard_cases,
                    lambda case, modality=modality: case["modality"] == modality
                    and case["answerable"] is True
                    and case["expected_source_count"] >= 2
                    and case["preview_required"] is True,
                )
            ),
        }
        for modality in ["markdown", "pdf", "image_ocr"]
    }

    assert coverage == {
        "markdown": {"refusal": 2, "scope_isolation_trap": 2, "multi_source_preview": 2},
        "pdf": {"refusal": 2, "scope_isolation_trap": 2, "multi_source_preview": 3},
        "image_ocr": {"refusal": 2, "scope_isolation_trap": 2, "multi_source_preview": 2},
    }


def test_eval_v8_hard_includes_history_grounded_refusal_cases_for_each_modality(
    hard_cases: list[dict[str, Any]], hard_schema: dict[str, Any]
) -> None:
    history_refusal_case_ids = {
        modality: _collect_case_ids(
            hard_cases,
            lambda case, modality=modality: case["modality"] == modality
            and case["answer_style"] == "refusal"
            and case["category"] in set(hard_schema["required_refusal_categories"])
            and bool(case.get("history_turns")),
        )
        for modality in ["markdown", "pdf", "image_ocr"]
    }

    assert history_refusal_case_ids == {
        "markdown": ["eval-v8-hard-md-009", "eval-v8-hard-md-010"],
        "pdf": ["eval-v8-hard-pdf-009", "eval-v8-hard-pdf-010"],
        "image_ocr": ["eval-v8-hard-img-009", "eval-v8-hard-img-010"],
    }

    summary = summarize_eval_cases(HARD_DIR)
    assert summary["history_grounded_case_count"] == 9
    assert summary["history_grounded_modality_breakdown"] == {"image_ocr": 3, "markdown": 3, "pdf": 3}
    assert summary["gate_checks"]["minimum_history_grounded_cases"] is True
    assert summary["gate_checks"]["minimum_history_grounded_cases_per_modality"] is True


def test_eval_v8_hard_history_grounded_gates_fail_when_followup_context_is_removed(
    tmp_path: Path, hard_cases: list[dict[str, Any]]
) -> None:
    mutated_cases: list[dict[str, Any]] = []
    for case in hard_cases:
        copied = dict(case)
        copied.pop("history_turns", None)
        mutated_cases.append(copied)

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(mutated_cases, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = summarize_eval_cases(cases_path, schema_path=HARD_DIR / "schema.json")

    assert summary["history_grounded_case_count"] == 0
    assert summary["history_grounded_modality_breakdown"] == {}
    assert summary["gate_checks"]["minimum_history_grounded_cases"] is False
    assert summary["gate_checks"]["minimum_history_grounded_cases_per_modality"] is False


def test_eval_v8_layered_cases_include_multi_source_source_count_guards(
    main_cases: list[dict[str, Any]], hard_cases: list[dict[str, Any]]
) -> None:
    all_cases = list(main_cases) + list(hard_cases)
    multi_source_case_ids = {
        modality: _collect_case_ids(
            all_cases,
            lambda case, modality=modality: case["modality"] == modality
            and case["answerable"] is True
            and case["expected_source_count"] >= 2
            and case["preview_required"] is True,
        )
        for modality in ["markdown", "pdf", "image_ocr"]
    }

    assert all(multi_source_case_ids.values())
    assert multi_source_case_ids["markdown"] == [
        "eval-v5-md-002",
        "eval-v5-md-003",
        "eval-v8-main-md-002",
        "eval-v8-main-md-019",
        "eval-v8-hard-md-002",
        "eval-v8-hard-md-013",
    ]
    assert multi_source_case_ids["pdf"] == [
        "eval-v5-pdf-002",
        "eval-v5-pdf-003",
        "eval-v8-main-pdf-002",
        "eval-v8-hard-pdf-002",
        "eval-v8-hard-pdf-011",
        "eval-v8-hard-pdf-013",
    ]
    assert multi_source_case_ids["image_ocr"] == [
        "eval-v5-img-002",
        "eval-v5-img-003",
        "eval-v8-main-img-002",
        "eval-v8-main-img-004",
        "eval-v8-hard-img-002",
        "eval-v8-hard-img-011",
    ]



def test_eval_v8_main_summary_matches_expected_distribution(main_schema: dict[str, Any], main_cases: list[dict[str, Any]]) -> None:
    summary = summarize_eval_cases(MAIN_DIR / "cases.json", schema_path=MAIN_DIR / "schema.json")
    quality_gates = main_schema["quality_gates"]

    assert len(main_cases) == 93
    assert summary["dataset_name"] == main_schema["dataset_name"]
    assert summary["total_cases"] == 93
    assert summary["modality_breakdown"] == {"image_ocr": 32, "markdown": 29, "pdf": 32}
    assert summary["difficulty_breakdown"] == {"complex": 31, "medium": 31, "simple": 31}
    assert summary["answer_style_breakdown"] == {
        "comparison": 13,
        "fact": 24,
        "policy": 15,
        "refusal": 23,
        "summary": 18,
    }
    assert summary["category_breakdown"] == {
        "approval_summary": 10,
        "cross_document": 9,
        "evidence_operation": 9,
        "hard_refusal": 6,
        "long_document": 7,
        "no_evidence": 14,
        "process_boundary": 13,
        "role_lookup": 8,
        "scope_contract": 9,
        "timeline_sla": 8,
    }
    assert summary["judge_dimension_breakdown"] == {
        "citation_accuracy": 69,
        "completeness": 69,
        "factual_accuracy": 69,
        "groundedness": 91,
        "refusal_correctness": 23,
    }
    assert summary["answerable_breakdown"] == {"answerable": 70, "no_evidence": 23}
    assert summary["refusal_case_count"] == 23
    assert summary["refusal_modality_breakdown"] == {"image_ocr": 9, "markdown": 6, "pdf": 8}
    assert summary["refusal_category_breakdown"] == {"hard_refusal": 6, "no_evidence": 14, "scope_contract": 3}
    assert summary["refusal_marker_category_breakdown"] == {
        "hard_refusal": {"No confirmable information": 6, "knowledge base": 6},
        "no_evidence": {"No confirmable information": 14, "knowledge base": 12},
        "scope_contract": {"must not fabricate": 2, "knowledge base": 2},
    }
    assert summary["negative_contract_case_count"] == 22
    assert summary["negative_contract_modality_breakdown"] == {"image_ocr": 11, "markdown": 6, "pdf": 5}
    assert summary["negative_contract_category_breakdown"] == {"process_boundary": 13, "scope_contract": 9}
    assert summary["negative_contract_marker_category_breakdown"] == {
        "process_boundary": {"authorization boundary": 9, "knowledge base": 10},
        "scope_contract": {"must not fabricate": 4, "effective_kb_ids": 3},
    }
    assert summary["history_grounded_case_count"] == 6
    assert summary["history_grounded_modality_breakdown"] == {"image_ocr": 2, "markdown": 2, "pdf": 2}
    assert summary["preview_required_cases"] == 70
    assert summary["modality_judge_dimension_breakdown"] == {
        "image_ocr": {
            "citation_accuracy": 23,
            "completeness": 23,
            "factual_accuracy": 23,
            "groundedness": 32,
            "refusal_correctness": 9,
        },
        "markdown": {
            "citation_accuracy": 23,
            "completeness": 23,
            "factual_accuracy": 23,
            "groundedness": 29,
            "refusal_correctness": 6,
        },
        "pdf": {
            "citation_accuracy": 23,
            "completeness": 23,
            "factual_accuracy": 23,
            "groundedness": 30,
            "refusal_correctness": 8,
        },
    }
    assert summary["weak_signal_case_count"] == 5
    assert summary["gate_checks"] == {
        "minimum_total_cases": True,
        "minimum_cases_per_modality": True,
        "minimum_cases_per_difficulty": True,
        "minimum_no_evidence_cases": True,
        "minimum_preview_required_cases": True,
        "minimum_cases_per_answer_style": True,
        "minimum_cases_per_category": True,
        "minimum_cases_per_judge_dimension": True,
        "minimum_cjk_cases": True,
        "minimum_cjk_cases_per_modality": True,
        "minimum_weak_signal_cases": True,
        "minimum_refusal_cases_per_modality": True,
        "minimum_negative_contract_cases_per_modality": True,
        "minimum_history_grounded_cases": True,
        "minimum_history_grounded_cases_per_modality": True,
        "required_weak_signal_tags": True,
        "required_refusal_categories": True,
        "required_refusal_markers_by_category": True,
        "required_refusal_markers_by_category_per_modality": True,
        "required_negative_contract_categories": True,
        "required_negative_contract_markers_by_category": True,
        "required_negative_contract_markers_by_category_per_modality": True,
    }

    assert summary["total_cases"] >= quality_gates["minimum_total_cases"]
    assert summary["preview_required_cases"] >= quality_gates["minimum_preview_required_cases"]



def test_eval_v8_hard_summary_matches_expected_distribution(hard_schema: dict[str, Any], hard_cases: list[dict[str, Any]]) -> None:
    summary = summarize_eval_cases(HARD_DIR / "cases.json", schema_path=HARD_DIR / "schema.json")
    quality_gates = hard_schema["quality_gates"]

    assert len(hard_cases) == 39
    assert summary["dataset_name"] == hard_schema["dataset_name"]
    assert summary["total_cases"] == 39
    assert summary["modality_breakdown"] == {"image_ocr": 13, "markdown": 13, "pdf": 13}
    assert summary["difficulty_breakdown"] == {"complex": 24, "medium": 15}
    assert summary["answer_style_breakdown"] == {
        "comparison": 16,
        "policy": 17,
        "refusal": 6,
    }
    assert summary["category_breakdown"] == {
        "chunk_boundary": 6,
        "evidence_insufficient": 6,
        "paraphrase_rewrite": 7,
        "scope_isolation_trap": 6,
        "similar_document_confusion": 8,
        "stale_version_conflict": 6,
    }
    assert summary["judge_dimension_breakdown"] == {
        "citation_accuracy": 33,
        "completeness": 33,
        "factual_accuracy": 33,
        "groundedness": 39,
        "refusal_correctness": 6,
    }
    assert summary["answerable_breakdown"] == {"answerable": 33, "no_evidence": 6}
    assert summary["refusal_case_count"] == 6
    assert summary["refusal_modality_breakdown"] == {"image_ocr": 2, "markdown": 2, "pdf": 2}
    assert summary["refusal_category_breakdown"] == {"evidence_insufficient": 6}
    assert summary["refusal_marker_category_breakdown"] == {
        "evidence_insufficient": {"No confirmable information": 6, "knowledge base": 6},
    }
    assert summary["negative_contract_case_count"] == 6
    assert summary["negative_contract_modality_breakdown"] == {"image_ocr": 2, "markdown": 2, "pdf": 2}
    assert summary["negative_contract_category_breakdown"] == {"scope_isolation_trap": 6}
    assert summary["negative_contract_marker_category_breakdown"] == {
        "scope_isolation_trap": {"authorization boundary": 3, "must not fabricate": 3, "effective_kb_ids": 3},
    }
    assert summary["preview_required_cases"] == 33
    assert summary["modality_judge_dimension_breakdown"] == {
        "image_ocr": {
            "citation_accuracy": 11,
            "completeness": 11,
            "factual_accuracy": 11,
            "groundedness": 13,
            "refusal_correctness": 2,
        },
        "markdown": {
            "citation_accuracy": 11,
            "completeness": 11,
            "factual_accuracy": 11,
            "groundedness": 13,
            "refusal_correctness": 2,
        },
        "pdf": {
            "citation_accuracy": 11,
            "completeness": 11,
            "factual_accuracy": 11,
            "groundedness": 13,
            "refusal_correctness": 2,
        },
    }
    assert summary["weak_signal_case_count"] == 0
    assert summary["gate_checks"] == {
        "minimum_total_cases": True,
        "minimum_cases_per_modality": True,
        "minimum_cases_per_difficulty": True,
        "minimum_no_evidence_cases": True,
        "minimum_preview_required_cases": True,
        "minimum_cases_per_answer_style": True,
        "minimum_refusal_cases_per_modality": True,
        "minimum_negative_contract_cases_per_modality": True,
        "minimum_history_grounded_cases": True,
        "minimum_history_grounded_cases_per_modality": True,
        "minimum_cases_per_category": True,
        "minimum_cases_per_judge_dimension": True,
        "required_refusal_categories": True,
        "required_refusal_markers_by_category": True,
        "required_refusal_markers_by_category_per_modality": True,
        "required_negative_contract_categories": True,
        "required_negative_contract_markers_by_category": True,
        "required_negative_contract_markers_by_category_per_modality": True,
    }

    assert summary["total_cases"] >= quality_gates["minimum_total_cases"]
    assert summary["preview_required_cases"] >= quality_gates["minimum_preview_required_cases"]

