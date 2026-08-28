from __future__ import annotations

import json
from pathlib import Path

from tests.api.chat_eval_suite_reporting import (
    build_eval_suite_layer_summary,
    load_eval_suite_manifest,
)


def test_load_eval_suite_manifest_normalizes_absolute_layer_paths(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    schema_path = tmp_path / "schema.json"
    suite_path = tmp_path / "suite.json"
    cases_path.write_text("[]", encoding="utf-8")
    schema_path.write_text("{}", encoding="utf-8")
    suite_path.write_text(
        json.dumps(
            {
                "suite_name": "demo-suite",
                "layers": [
                    {
                        "name": "smoke",
                        "cases_path": str(cases_path),
                        "schema_path": str(schema_path),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = load_eval_suite_manifest(suite_path)

    assert manifest["suite_name"] == "demo-suite"
    assert manifest["suite_path"] == str(suite_path.resolve())
    assert manifest["layers"][0]["cases_path"] == str(cases_path.resolve())
    assert manifest["layers"][0]["schema_path"] == str(schema_path.resolve())


def test_build_eval_suite_layer_summary_tracks_failed_gates_and_weakest_categories() -> None:
    layer = {
        "name": "hard",
        "purpose": "bug-hunt",
        "dataset_name": "demo-hard",
        "target_case_count": 3,
        "cases_path": "tests/fixtures/rag_quality/eval_v8_hard/cases.json",
        "schema_path": "tests/fixtures/rag_quality/eval_v8_hard/schema.json",
    }
    report = {
        "dataset_name": "demo-hard",
        "evaluation_mode": "diagnostic",
        "run_passed": False,
        "suite_summary": {
            "total_cases": 3,
            "passed_cases": 1,
            "failed_cases": 2,
            "pass_rate": 1 / 3,
            "category_breakdown": {
                "evidence_insufficient": {"count": 2, "passed": 0, "pass_rate": 0.0},
                "similar_document_confusion": {"count": 1, "passed": 1, "pass_rate": 1.0},
            },
        },
        "run_gates": {
            "source_count_match_rate_min": {
                "passed": False,
                "metric": "source_count_match_rate",
                "actual": 0.667,
                "minimum": 0.95,
            }
        },
        "contract_gates": {
            "required_negative_contract_modalities": {
                "passed": False,
                "metric": "required_modalities_passed",
                "actual": 0.0,
                "minimum": 1.0,
                "missing": ["pdf"],
                "required_modalities_without_passed_cases": ["image_ocr"],
                "detail": {
                    "missing": ["pdf"],
                    "required_modalities_without_passed_cases": ["image_ocr"],
                },
            }
        },
        "diagnostic_gates": {
            "case_expectation_match_rate_min": {
                "passed": False,
                "metric": "case_expectation_match_rate",
                "actual": 0.5,
                "minimum": 1.0,
            }
        },
        "failures": [{"case_id": "hard-001"}, {"case_id": "hard-002"}],
        "failure_stage_breakdown": {"quality_gate": 2},
        "artifacts": {"markdown": "C:/demo/hard.md"},
    }

    summary = build_eval_suite_layer_summary(layer, report)

    assert summary["name"] == "hard"
    assert summary["purpose"] == "bug-hunt"
    assert summary["dataset_name"] == "demo-hard"
    assert summary["evaluation_mode"] == "diagnostic"
    assert summary["target_case_count"] == 3
    assert summary["actual_case_count"] == 3
    assert summary["failed_cases"] == 2
    assert summary["failed_run_gates"] == ["source_count_match_rate_min"]
    assert summary["failed_run_gate_details"] == {
        "source_count_match_rate_min": {
            "metric": "source_count_match_rate",
            "actual": 0.667,
            "minimum": 0.95,
        }
    }
    assert summary["failed_contract_gates"] == ["required_negative_contract_modalities"]
    assert summary["failed_contract_gate_details"] == {
        "required_negative_contract_modalities": {
            "metric": "required_modalities_passed",
            "actual": 0.0,
            "minimum": 1.0,
            "missing": ["pdf"],
            "required_modalities_without_passed_cases": ["image_ocr"],
            "detail": {
                "missing": ["pdf"],
                "required_modalities_without_passed_cases": ["image_ocr"],
            },
        }
    }
    assert summary["failed_diagnostic_gates"] == ["case_expectation_match_rate_min"]
    assert summary["failed_diagnostic_gate_details"] == {
        "case_expectation_match_rate_min": {
            "metric": "case_expectation_match_rate",
            "actual": 0.5,
            "minimum": 1.0,
        }
    }
    assert summary["failure_case_ids"] == ["hard-001", "hard-002"]
    assert summary["weakest_categories"][0] == {
        "category": "evidence_insufficient",
        "count": 2,
        "passed": 0,
        "pass_rate": 0.0,
    }
