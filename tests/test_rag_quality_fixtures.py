"""RAG QA fixture schema、半真实样本约束与防污染测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_rag_quality_fixtures import (
    summarize_eval_cases,
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


def test_eval_summary_flags_missing_required_refusal_category(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    cases_path = tmp_path / "cases.json"
    schema_path.write_text(
        json.dumps(
            {
                "dataset_name": "tmp_eval_dataset",
                "evaluation_mode": "healthy",
                "required_fields": [
                    "case_id",
                    "dataset",
                    "kb_id",
                    "question",
                    "source_doc",
                    "source_locator",
                    "expected_scope_type",
                    "expected_isolation_level",
                    "modality",
                    "answer_style",
                    "difficulty",
                    "category",
                    "answerable",
                    "expected_keypoints",
                    "required_evidence_docs",
                    "expected_source_count",
                    "preview_required",
                    "preview_terms",
                    "forbidden_terms",
                    "judge_focus",
                ],
                "allowed_modalities": ["markdown"],
                "allowed_answer_styles": ["fact", "refusal"],
                "allowed_difficulties": ["simple"],
                "allowed_categories": ["no_evidence", "scope_contract"],
                "allowed_scope_types": ["single_kb"],
                "allowed_isolation_levels": ["physical_isolated"],
                "allowed_judge_dimensions": ["groundedness", "refusal_correctness"],
                "required_refusal_categories": ["no_evidence", "scope_contract"],
                "quality_gates": {
                    "minimum_total_cases": 1,
                    "minimum_cases_per_modality": 1,
                    "minimum_cases_per_difficulty": 1,
                    "minimum_no_evidence_cases": 1,
                    "minimum_preview_required_cases": 1,
                },
                "run_gates": {"pass_rate_min": 0.0},
                "rubric_dimensions": {"groundedness": {"weight": 1.0}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "tmp-refusal-1",
                    "dataset": "tmp_eval_dataset",
                    "kb_id": "kb-a",
                    "question": "当前知识库里有 CAB ticket 吗？",
                    "source_doc": None,
                    "source_locator": None,
                    "expected_scope_type": "single_kb",
                    "expected_isolation_level": "physical_isolated",
                    "modality": "markdown",
                    "answer_style": "refusal",
                    "difficulty": "simple",
                    "category": "no_evidence",
                    "answerable": False,
                    "expected_keypoints": ["No confirmable information"],
                    "required_evidence_docs": [],
                    "expected_source_count": 0,
                    "preview_required": False,
                    "preview_terms": [],
                    "forbidden_terms": ["CAB-2048"],
                    "judge_focus": ["groundedness", "refusal_correctness"],
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = summarize_eval_cases(cases_path, schema_path=schema_path)

    assert summary["refusal_category_breakdown"] == {"no_evidence": 1}
    assert summary["gate_checks"]["required_refusal_categories"] is False





def test_eval_summary_flags_missing_required_negative_contract_category(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    cases_path = tmp_path / "cases.json"
    schema_path.write_text(
        json.dumps(
            {
                "dataset_name": "tmp_eval_dataset",
                "evaluation_mode": "healthy",
                "required_fields": [
                    "case_id",
                    "dataset",
                    "kb_id",
                    "question",
                    "source_doc",
                    "source_locator",
                    "expected_scope_type",
                    "expected_isolation_level",
                    "modality",
                    "answer_style",
                    "difficulty",
                    "category",
                    "answerable",
                    "expected_keypoints",
                    "required_evidence_docs",
                    "expected_source_count",
                    "preview_required",
                    "preview_terms",
                    "forbidden_terms",
                    "judge_focus",
                ],
                "allowed_modalities": ["markdown"],
                "allowed_answer_styles": ["policy"],
                "allowed_difficulties": ["simple"],
                "allowed_categories": ["process_boundary", "scope_contract"],
                "allowed_scope_types": ["single_kb"],
                "allowed_isolation_levels": ["physical_isolated"],
                "allowed_judge_dimensions": ["groundedness"],
                "required_negative_contract_categories": ["process_boundary", "scope_contract"],
                "quality_gates": {
                    "minimum_total_cases": 1,
                    "minimum_cases_per_modality": 1,
                    "minimum_cases_per_difficulty": 1,
                    "minimum_no_evidence_cases": 1,
                    "minimum_preview_required_cases": 1,
                    "minimum_negative_contract_cases_per_modality": 1,
                },
                "run_gates": {"pass_rate_min": 0.0},
                "rubric_dimensions": {"groundedness": {"weight": 1.0}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "tmp-negative-1",
                    "dataset": "tmp_eval_dataset",
                    "kb_id": "kb-a",
                    "question": "当前流程边界是什么？",
                    "source_doc": "boundary.md",
                    "source_locator": "chunk-1",
                    "expected_scope_type": "single_kb",
                    "expected_isolation_level": "physical_isolated",
                    "modality": "markdown",
                    "answer_style": "policy",
                    "difficulty": "simple",
                    "category": "process_boundary",
                    "answerable": True,
                    "expected_keypoints": ["boundary"],
                    "required_evidence_docs": ["boundary.md"],
                    "expected_source_count": 1,
                    "preview_required": False,
                    "preview_terms": [],
                    "forbidden_terms": [],
                    "judge_focus": ["groundedness"],
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = summarize_eval_cases(cases_path, schema_path=schema_path)

    assert summary["negative_contract_category_breakdown"] == {"process_boundary": 1}
    assert summary["gate_checks"]["required_negative_contract_categories"] is False
    assert summary["gate_checks"]["minimum_negative_contract_cases_per_modality"] is True

def test_eval_summary_flags_missing_required_refusal_marker_by_category(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    cases_path = tmp_path / "cases.json"
    schema_path.write_text(
        json.dumps(
            {
                "dataset_name": "tmp_eval_dataset",
                "evaluation_mode": "healthy",
                "required_fields": [
                    "case_id",
                    "dataset",
                    "kb_id",
                    "question",
                    "source_doc",
                    "source_locator",
                    "expected_scope_type",
                    "expected_isolation_level",
                    "modality",
                    "answer_style",
                    "difficulty",
                    "category",
                    "answerable",
                    "expected_keypoints",
                    "required_evidence_docs",
                    "expected_source_count",
                    "preview_required",
                    "preview_terms",
                    "forbidden_terms",
                    "judge_focus",
                ],
                "allowed_modalities": ["markdown"],
                "allowed_answer_styles": ["refusal"],
                "allowed_difficulties": ["simple"],
                "allowed_categories": ["no_evidence"],
                "allowed_scope_types": ["single_kb"],
                "allowed_isolation_levels": ["physical_isolated"],
                "allowed_judge_dimensions": ["groundedness", "refusal_correctness"],
                "required_refusal_markers_by_category": {
                    "no_evidence": ["knowledge base"],
                },
                "quality_gates": {
                    "minimum_total_cases": 1,
                    "minimum_cases_per_modality": 1,
                    "minimum_cases_per_difficulty": 1,
                    "minimum_no_evidence_cases": 1,
                    "minimum_preview_required_cases": 1,
                },
                "run_gates": {"pass_rate_min": 0.0},
                "rubric_dimensions": {"groundedness": {"weight": 1.0}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "tmp-refusal-1",
                    "dataset": "tmp_eval_dataset",
                    "kb_id": "kb-a",
                    "question": "当前知识库里有 CAB ticket 吗？",
                    "source_doc": None,
                    "source_locator": None,
                    "expected_scope_type": "single_kb",
                    "expected_isolation_level": "physical_isolated",
                    "modality": "markdown",
                    "answer_style": "refusal",
                    "difficulty": "simple",
                    "category": "no_evidence",
                    "answerable": False,
                    "expected_keypoints": ["No confirmable information"],
                    "required_evidence_docs": [],
                    "expected_source_count": 0,
                    "preview_required": False,
                    "preview_terms": [],
                    "forbidden_terms": ["CAB-2048"],
                    "judge_focus": ["groundedness", "refusal_correctness"],
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = summarize_eval_cases(cases_path, schema_path=schema_path)

    assert summary["refusal_marker_category_breakdown"] == {"no_evidence": {"knowledge base": 0}}
    assert summary["gate_checks"]["required_refusal_markers_by_category"] is False



def test_eval_summary_flags_missing_required_refusal_marker_in_required_modality(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    cases_path = tmp_path / "cases.json"
    schema_path.write_text(
        json.dumps(
            {
                "dataset_name": "tmp_eval_dataset",
                "evaluation_mode": "healthy",
                "required_fields": [
                    "case_id",
                    "dataset",
                    "kb_id",
                    "question",
                    "source_doc",
                    "source_locator",
                    "expected_scope_type",
                    "expected_isolation_level",
                    "modality",
                    "answer_style",
                    "difficulty",
                    "category",
                    "answerable",
                    "expected_keypoints",
                    "required_evidence_docs",
                    "expected_source_count",
                    "preview_required",
                    "preview_terms",
                    "forbidden_terms",
                    "judge_focus",
                ],
                "allowed_modalities": ["markdown", "pdf"],
                "allowed_answer_styles": ["refusal"],
                "allowed_difficulties": ["simple"],
                "allowed_categories": ["no_evidence"],
                "allowed_scope_types": ["single_kb"],
                "allowed_isolation_levels": ["physical_isolated"],
                "allowed_judge_dimensions": ["groundedness", "refusal_correctness"],
                "required_refusal_markers_by_category": {
                    "no_evidence": ["knowledge base"],
                },
                "quality_gates": {
                    "minimum_total_cases": 2,
                    "minimum_cases_per_modality": 1,
                    "minimum_cases_per_difficulty": 2,
                    "minimum_no_evidence_cases": 1,
                    "minimum_preview_required_cases": 1,
                    "minimum_refusal_cases_per_modality": 1,
                },
                "run_gates": {"pass_rate_min": 0.0},
                "rubric_dimensions": {"groundedness": {"weight": 1.0}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "tmp-refusal-md-1",
                    "dataset": "tmp_eval_dataset",
                    "kb_id": "kb-a",
                    "question": "markdown refusal",
                    "source_doc": None,
                    "source_locator": None,
                    "expected_scope_type": "single_kb",
                    "expected_isolation_level": "physical_isolated",
                    "modality": "markdown",
                    "answer_style": "refusal",
                    "difficulty": "simple",
                    "category": "no_evidence",
                    "answerable": False,
                    "expected_keypoints": ["No confirmable information", "knowledge base"],
                    "required_evidence_docs": [],
                    "expected_source_count": 0,
                    "preview_required": False,
                    "preview_terms": [],
                    "forbidden_terms": ["CAB-2048"],
                    "judge_focus": ["groundedness", "refusal_correctness"],
                },
                {
                    "case_id": "tmp-refusal-pdf-1",
                    "dataset": "tmp_eval_dataset",
                    "kb_id": "kb-a",
                    "question": "pdf refusal",
                    "source_doc": None,
                    "source_locator": None,
                    "expected_scope_type": "single_kb",
                    "expected_isolation_level": "physical_isolated",
                    "modality": "pdf",
                    "answer_style": "refusal",
                    "difficulty": "simple",
                    "category": "no_evidence",
                    "answerable": False,
                    "expected_keypoints": ["No confirmable information"],
                    "required_evidence_docs": [],
                    "expected_source_count": 0,
                    "preview_required": False,
                    "preview_terms": [],
                    "forbidden_terms": ["CAB-2048"],
                    "judge_focus": ["groundedness", "refusal_correctness"],
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = summarize_eval_cases(cases_path, schema_path=schema_path)

    assert summary["refusal_marker_category_breakdown"] == {"no_evidence": {"knowledge base": 1}}
    assert summary["refusal_modality_marker_category_breakdown"] == {
        "markdown": {"no_evidence": {"knowledge base": 1}},
        "pdf": {"no_evidence": {"knowledge base": 0}},
    }
    assert summary["gate_checks"]["required_refusal_markers_by_category"] is True
    assert summary["gate_checks"]["required_refusal_markers_by_category_per_modality"] is False



def test_eval_summary_flags_missing_required_negative_contract_marker_in_required_modality(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    cases_path = tmp_path / "cases.json"
    schema_path.write_text(
        json.dumps(
            {
                "dataset_name": "tmp_eval_dataset",
                "evaluation_mode": "healthy",
                "required_fields": [
                    "case_id",
                    "dataset",
                    "kb_id",
                    "question",
                    "source_doc",
                    "source_locator",
                    "expected_scope_type",
                    "expected_isolation_level",
                    "modality",
                    "answer_style",
                    "difficulty",
                    "category",
                    "answerable",
                    "expected_keypoints",
                    "required_evidence_docs",
                    "expected_source_count",
                    "preview_required",
                    "preview_terms",
                    "forbidden_terms",
                    "judge_focus",
                ],
                "allowed_modalities": ["markdown", "pdf"],
                "allowed_answer_styles": ["policy"],
                "allowed_difficulties": ["simple"],
                "allowed_categories": ["process_boundary", "scope_contract"],
                "allowed_scope_types": ["single_kb"],
                "allowed_isolation_levels": ["physical_isolated"],
                "allowed_judge_dimensions": ["groundedness"],
                "required_negative_contract_categories": ["process_boundary", "scope_contract"],
                "required_negative_contract_markers_by_category": {
                    "process_boundary": ["authorization boundary"],
                },
                "quality_gates": {
                    "minimum_total_cases": 2,
                    "minimum_cases_per_modality": 1,
                    "minimum_cases_per_difficulty": 2,
                    "minimum_no_evidence_cases": 1,
                    "minimum_preview_required_cases": 1,
                    "minimum_negative_contract_cases_per_modality": 1,
                },
                "run_gates": {"pass_rate_min": 0.0},
                "rubric_dimensions": {"groundedness": {"weight": 1.0}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "tmp-neg-md-1",
                    "dataset": "tmp_eval_dataset",
                    "kb_id": "kb-a",
                    "question": "markdown boundary",
                    "source_doc": "boundary.md",
                    "source_locator": "chunk-1",
                    "expected_scope_type": "single_kb",
                    "expected_isolation_level": "physical_isolated",
                    "modality": "markdown",
                    "answer_style": "policy",
                    "difficulty": "simple",
                    "category": "process_boundary",
                    "answerable": True,
                    "expected_keypoints": ["authorization boundary"],
                    "required_evidence_docs": ["boundary.md"],
                    "expected_source_count": 1,
                    "preview_required": True,
                    "preview_terms": ["authorization boundary"],
                    "forbidden_terms": [],
                    "judge_focus": ["groundedness"],
                },
                {
                    "case_id": "tmp-neg-pdf-1",
                    "dataset": "tmp_eval_dataset",
                    "kb_id": "kb-a",
                    "question": "pdf boundary",
                    "source_doc": "boundary.pdf",
                    "source_locator": "page-1",
                    "expected_scope_type": "single_kb",
                    "expected_isolation_level": "physical_isolated",
                    "modality": "pdf",
                    "answer_style": "policy",
                    "difficulty": "simple",
                    "category": "process_boundary",
                    "answerable": True,
                    "expected_keypoints": ["knowledge base"],
                    "required_evidence_docs": ["boundary.pdf"],
                    "expected_source_count": 1,
                    "preview_required": True,
                    "preview_terms": ["knowledge base"],
                    "forbidden_terms": [],
                    "judge_focus": ["groundedness"],
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = summarize_eval_cases(cases_path, schema_path=schema_path)

    assert summary["negative_contract_marker_category_breakdown"] == {
        "process_boundary": {"authorization boundary": 1}
    }
    assert summary["negative_contract_modality_marker_category_breakdown"] == {
        "markdown": {"process_boundary": {"authorization boundary": 1}},
        "pdf": {"process_boundary": {"authorization boundary": 0}},
    }
    assert summary["gate_checks"]["required_negative_contract_markers_by_category"] is True
    assert summary["gate_checks"]["required_negative_contract_markers_by_category_per_modality"] is False
