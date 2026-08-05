"""问答准确性评测数据集的结构校验与分层统计测试。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from scripts.validate_rag_quality_fixtures import (
    load_eval_schema,
    summarize_eval_cases,
    validate_eval_case_record,
    validate_eval_cases_file,
)

EVAL_DIR = Path("tests/fixtures/rag_quality/eval_v1")
EVAL_SCHEMA = EVAL_DIR / "schema.json"
EVAL_CASES = EVAL_DIR / "cases.json"


@pytest.fixture(scope="module")
def eval_schema() -> dict[str, Any]:
    return load_eval_schema(EVAL_SCHEMA)


@pytest.fixture(scope="module")
def eval_cases() -> list[dict[str, Any]]:
    return json.loads(EVAL_CASES.read_text(encoding="utf-8"))


def _write_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")


def _clone_case(case: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(case)


def _build_invalid_case(
    eval_cases: list[dict[str, Any]],
    selector: Callable[[list[dict[str, Any]]], dict[str, Any]],
    mutator: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    case = _clone_case(selector(eval_cases))
    mutator(case)
    return case


def test_eval_schema_loads_successfully(eval_schema: dict[str, Any]) -> None:
    assert eval_schema["dataset_name"] == "local_multi_kb_eval_v1"
    assert eval_schema["quality_gates"]["minimum_total_cases"] == 50
    assert set(eval_schema["allowed_modalities"]) == {"markdown", "pdf", "image_ocr"}
    assert "refusal_correctness" in eval_schema["allowed_judge_dimensions"]


def test_eval_cases_file_passes_schema_validation() -> None:
    validate_eval_cases_file(EVAL_CASES, schema_path=EVAL_SCHEMA)


def test_eval_cases_summary_matches_expected_distribution(eval_schema: dict[str, Any]) -> None:
    summary = summarize_eval_cases(EVAL_CASES, schema_path=EVAL_SCHEMA)
    quality_gates = eval_schema["quality_gates"]

    assert summary["dataset_name"] == eval_schema["dataset_name"]
    assert summary["total_cases"] == 54
    assert summary["modality_breakdown"] == {"image_ocr": 18, "markdown": 18, "pdf": 18}
    assert summary["difficulty_breakdown"] == {"complex": 18, "medium": 18, "simple": 18}
    assert summary["answerable_breakdown"] == {"answerable": 45, "no_evidence": 9}
    assert summary["preview_required_cases"] == 45

    assert summary["total_cases"] >= quality_gates["minimum_total_cases"]
    for modality in eval_schema["allowed_modalities"]:
        assert summary["modality_breakdown"][modality] >= quality_gates["minimum_cases_per_modality"]
        assert set(summary["modality_difficulty_breakdown"][modality]) == set(eval_schema["allowed_difficulties"])
    for difficulty in eval_schema["allowed_difficulties"]:
        assert summary["difficulty_breakdown"][difficulty] >= quality_gates["minimum_cases_per_difficulty"]

    assert summary["answerable_breakdown"]["no_evidence"] >= quality_gates["minimum_no_evidence_cases"]
    assert summary["preview_required_cases"] >= quality_gates["minimum_preview_required_cases"]
    assert all(summary["gate_checks"].values())


def test_eval_case_rejects_invalid_judge_dimension(
    eval_schema: dict[str, Any],
    eval_cases: list[dict[str, Any]],
) -> None:
    invalid_case = _build_invalid_case(
        eval_cases,
        selector=lambda cases: next(case for case in cases if case["answerable"]),
        mutator=lambda case: case.__setitem__("judge_focus", ["factual_accuracy", "tool_efficiency"]),
    )

    with pytest.raises(ValueError, match="judge_focus"):
        validate_eval_case_record(invalid_case, source=EVAL_CASES, schema=eval_schema)


@pytest.mark.parametrize(
    ("name", "mutator", "match"),
    [
        (
            "invalid_modality",
            lambda case: case.__setitem__("modality", "audio"),
            "modality",
        ),
        (
            "answerable_zero_sources",
            lambda case: case.__setitem__("expected_source_count", 0),
            "expected_source_count",
        ),
        (
            "answerable_without_preview",
            lambda case: case.__setitem__("preview_required", False),
            "preview",
        ),
        (
            "answerable_missing_source_doc",
            lambda case: case.__setitem__("source_doc", ""),
            "source_doc",
        ),
    ],
)
def test_answerable_eval_case_negative_contracts(
    name: str,
    mutator: Callable[[dict[str, Any]], None],
    match: str,
    eval_schema: dict[str, Any],
    eval_cases: list[dict[str, Any]],
) -> None:
    invalid_case = _build_invalid_case(
        eval_cases,
        selector=lambda cases: next(case for case in cases if case["answerable"]),
        mutator=mutator,
    )

    with pytest.raises(ValueError, match=match):
        validate_eval_case_record(invalid_case, source=EVAL_CASES, schema=eval_schema)


@pytest.mark.parametrize(
    ("name", "mutator", "match"),
    [
        (
            "unexpected_source_doc",
            lambda case: case.__setitem__("source_doc", "fabricated.md"),
            "source_doc",
        ),
        (
            "unexpected_source_locator",
            lambda case: case.__setitem__("source_locator", "tests/fixtures/rag_quality/semireal_markdown/scope-contract.md"),
            "source_locator",
        ),
        (
            "nonzero_expected_sources",
            lambda case: case.__setitem__("expected_source_count", 1),
            "expected_source_count",
        ),
        (
            "missing_refusal_focus",
            lambda case: case.__setitem__("judge_focus", ["groundedness"]),
            "refusal_correctness",
        ),
    ],
)
def test_no_evidence_eval_case_negative_contracts(
    name: str,
    mutator: Callable[[dict[str, Any]], None],
    match: str,
    eval_schema: dict[str, Any],
    eval_cases: list[dict[str, Any]],
) -> None:
    invalid_case = _build_invalid_case(
        eval_cases,
        selector=lambda cases: next(case for case in cases if not case["answerable"]),
        mutator=mutator,
    )

    with pytest.raises(ValueError, match=match):
        validate_eval_case_record(invalid_case, source=EVAL_CASES, schema=eval_schema)


def test_eval_cases_file_rejects_duplicate_case_id(tmp_path: Path, eval_cases: list[dict[str, Any]]) -> None:
    duplicate = [_clone_case(eval_cases[0]), _clone_case(eval_cases[0])]
    path = tmp_path / "duplicate_cases.json"
    _write_cases(path, duplicate)

    with pytest.raises(ValueError, match="duplicate eval case id"):
        validate_eval_cases_file(path, schema_path=EVAL_SCHEMA)


def test_eval_cases_file_rejects_invalid_source_locator(tmp_path: Path, eval_cases: list[dict[str, Any]]) -> None:
    invalid_case = _clone_case(next(case for case in eval_cases if case["answerable"]))
    invalid_case["source_locator"] = "tests/fixtures/rag_quality/semireal_markdown/not-exist.md"
    path = tmp_path / "invalid_locator_cases.json"
    _write_cases(path, [invalid_case])

    with pytest.raises(ValueError, match="source_locator"):
        validate_eval_cases_file(path, schema_path=EVAL_SCHEMA)
