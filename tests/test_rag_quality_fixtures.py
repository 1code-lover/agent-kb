"""RAG QA fixture schema、半真实样本约束与防污染测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_rag_quality_fixtures import (
    summarize_semireal_cases,
    validate_files,
    validate_record,
    validate_semireal_cases_file,
)

FIXTURE_DIR = Path("tests/fixtures/rag_quality")
SEMIREAL_DIR = FIXTURE_DIR / "semireal_markdown"
SEMIREAL_CASES = SEMIREAL_DIR / "cases.json"


def test_default_fixture_files_are_not_under_data() -> None:
    for path in [FIXTURE_DIR / "draft.jsonl", FIXTURE_DIR / "verified.jsonl", FIXTURE_DIR / "schema.json"]:
        assert "data" not in path.parts


def test_draft_record_allows_missing_evidence() -> None:
    record = {
        "id": "qa-draft-1",
        "query": "测试问题",
        "expected_answer": "??",
        "status": "draft",
    }

    validate_record(record, source=Path("draft.jsonl"))


def test_verified_record_requires_evidence() -> None:
    record = {
        "id": "qa-verified-1",
        "query": "测试问题",
        "search_kb_ids": ["default"],
        "expected_answer": "??",
        "status": "verified",
        "relevant_documents": [],
    }

    with pytest.raises(ValueError, match="relevant_documents"):
        validate_record(record, source=Path("verified.jsonl"))


def test_duplicate_ids_fail(tmp_path: Path) -> None:
    fixture = tmp_path / "draft.jsonl"
    row = {"id": "qa-1", "query": "Q", "expected_answer": "A", "status": "draft"}
    fixture.write_text(json.dumps(row, ensure_ascii=False) + "\n" + json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        validate_files([fixture])


def test_verified_file_path_must_not_point_to_fixture_dir() -> None:
    record = {
        "id": "qa-verified-2",
        "query": "测试问题",
        "search_kb_ids": ["default"],
        "expected_answer": "??",
        "status": "verified",
        "relevant_documents": [
            {
                "kb_id": "default",
                "file_name": "draft.jsonl",
                "file_path": "tests/fixtures/rag_quality/draft.jsonl",
                "evidence": "??",
            }
        ],
    }

    with pytest.raises(ValueError, match="fixture"):
        validate_record(record, source=Path("verified.jsonl"))


def test_semireal_cases_file_passes_schema_validation() -> None:
    validate_semireal_cases_file(SEMIREAL_CASES, markdown_dir=SEMIREAL_DIR)



def test_semireal_cases_summary_matches_expected_distribution() -> None:
    summary = summarize_semireal_cases(SEMIREAL_CASES)

    assert summary["total_cases"] >= 6
    assert summary["expected_with_evidence"] >= 5
    assert summary["explicit_no_evidence"] >= 1
    assert summary["preview_required"] >= 5
    for category in ["fact", "summary", "policy", "architecture", "no-evidence"]:
        assert category in summary["category_breakdown"]



def test_semireal_case_without_expected_doc_requires_zero_sources(tmp_path: Path) -> None:
    fixture = tmp_path / "cases.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "case_id": "bad-no-evidence",
                    "question": "bad",
                    "expected_doc": None,
                    "expected_keypoints": ["No confirmable information"],
                    "must_not_contain": [],
                    "preview_terms": ["should-not-exist"],
                    "expected_source_count": 1,
                    "category": "no-evidence",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_source_count"):
        validate_semireal_cases_file(fixture, markdown_dir=SEMIREAL_DIR)
