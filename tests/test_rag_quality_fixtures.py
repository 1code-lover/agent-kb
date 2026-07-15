"""RAG QA fixture schema 与防污染测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_rag_quality_fixtures import validate_files, validate_record

FIXTURE_DIR = Path("tests/fixtures/rag_quality")


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
