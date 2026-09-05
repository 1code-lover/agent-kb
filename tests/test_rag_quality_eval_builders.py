from __future__ import annotations

import json
from pathlib import Path

from scripts.build_eval_v7_holdout import build_cases as build_v7_cases, build_schema as build_v7_schema
from scripts.build_eval_v8_layered import (
    build_hard_cases,
    build_hard_schema,
    build_layered_suite,
    build_main_cases,
    build_main_schema,
)

FIXTURE_ROOT = Path("tests/fixtures/rag_quality")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_eval_v7_builder_matches_checked_in_fixture() -> None:
    assert build_v7_schema() == _read_json(FIXTURE_ROOT / "eval_v7" / "schema.json")
    assert build_v7_cases() == _read_json(FIXTURE_ROOT / "eval_v7" / "cases.json")


def test_eval_v8_builders_match_checked_in_fixtures() -> None:
    assert build_main_schema() == _read_json(FIXTURE_ROOT / "eval_v8_main" / "schema.json")
    assert build_main_cases() == _read_json(FIXTURE_ROOT / "eval_v8_main" / "cases.json")
    assert build_hard_schema() == _read_json(FIXTURE_ROOT / "eval_v8_hard" / "schema.json")
    assert build_hard_cases() == _read_json(FIXTURE_ROOT / "eval_v8_hard" / "cases.json")
    assert build_layered_suite() == _read_json(FIXTURE_ROOT / "eval_layered_suite.json")
