"""单知识库问答 smoke 评测测试。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import app
from server.kb_registry import KBRegistry
from tests.api.chat_qa_metrics import build_chat_case_report, summarize_chat_case_reports

client = TestClient(app)
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "rag_quality" / "single_kb_smoke_cases.json"
_REQUIRED_CASE_FIELDS = {
    "case_id",
    "kb_id",
    "question",
    "mock_answer",
    "expected_keypoints",
    "expected_evidence",
    "must_not_contain",
    "source_doc",
    "source_nodes",
}


def _load_smoke_cases() -> list[dict]:
    if not FIXTURE_PATH.exists():
        return []
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


_SMOKE_CASES = _load_smoke_cases()


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """隔离 KB registry，并屏蔽会话落盘副作用。"""
    monkeypatch.chdir(tmp_path)

    import api.services.chat_service as chat_service
    import api.services.kb_service as kb_service

    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    kb_service._registry = registry
    monkeypatch.setattr(chat_service, "append_chat_message", lambda *args, **kwargs: None)
    yield registry
    kb_service._registry = None



def _make_source_node(payload: dict) -> SimpleNamespace:
    """把 fixture 中的 source_nodes 样本转成 chat runtime 可消费的节点。"""
    metadata = {
        "kb_id": payload["kb_id"],
        "file_name": payload["title"],
        "title": payload["title"],
        "page_label": payload.get("page", "1"),
        "doc_id": payload["doc_id"],
    }
    content_node = SimpleNamespace(
        metadata=metadata,
        text=payload.get("text", ""),
        ref_doc_id=payload["doc_id"],
        node_id=payload.get("node_id", f"node-{payload['doc_id']}"),
    )
    return SimpleNamespace(node=content_node, score=payload.get("score", 0.9))



def _stub_chat_runtime(monkeypatch, case: dict) -> MagicMock:
    """为单条 smoke case 注入确定性 query engine 返回值。"""
    import api.services.chat_service as chat_service

    source_nodes = [_make_source_node(item) for item in case.get("source_nodes", [])]
    mock_engine = MagicMock()
    mock_engine.query.return_value = SimpleNamespace(response=case["mock_answer"], source_nodes=source_nodes)

    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    mock_build = MagicMock(return_value=mock_engine)
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", mock_build)
    return mock_build



def _run_smoke_case(case: dict, *, monkeypatch, isolated_registry) -> tuple[dict, MagicMock]:
    """执行单条 smoke case，并返回 payload 与构建器 mock。"""
    if isolated_registry.get_kb(case["kb_id"]) is None:
        isolated_registry.create_kb(case["kb_id"], case.get("kb_name", case["kb_id"]))
    mock_build = _stub_chat_runtime(monkeypatch, case)

    resp = client.post(
        "/api/chat/query",
        json={
            "question": case["question"],
            "session_id": case["case_id"],
            "kb_ids": [case["kb_id"]],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    return body["data"], mock_build



def test_single_kb_smoke_fixture_file_exists() -> None:
    """问答 smoke 评测样本必须落盘，避免测试集只存在于文档描述里。"""
    assert FIXTURE_PATH.exists(), f"missing fixture file: {FIXTURE_PATH}"



def test_single_kb_smoke_fixture_has_required_fields() -> None:
    """结构化问答样本必须具备最小字段集。"""
    assert _SMOKE_CASES, "single_kb_smoke_cases.json should not be empty"

    for case in _SMOKE_CASES:
        missing = _REQUIRED_CASE_FIELDS - set(case.keys())
        assert not missing, f"case {case.get('case_id', '<unknown>')} missing fields: {sorted(missing)}"
        assert case["kb_id"].strip()
        assert case["question"].strip()
        assert case["source_doc"].strip()
        assert isinstance(case["expected_keypoints"], list) and case["expected_keypoints"]
        assert isinstance(case["expected_evidence"], list) and case["expected_evidence"]
        assert isinstance(case["must_not_contain"], list)
        assert isinstance(case["source_nodes"], list) and case["source_nodes"]



def test_single_kb_smoke_fixture_covers_multiple_question_types() -> None:
    """smoke 样本应至少覆盖契约、证据、拒答、边界/指标等不同题型。"""
    types = {str(case.get("type", "")) for case in _SMOKE_CASES}
    assert {"positive", "negative-policy", "architecture", "metrics"}.issubset(types)
    assert len(_SMOKE_CASES) >= 6


@pytest.mark.parametrize("case", _SMOKE_CASES, ids=[case.get("case_id", "case") for case in _SMOKE_CASES])
def test_single_kb_qa_smoke_contract(case, monkeypatch, isolated_registry):
    """用结构化问答样本验证单库主链路的 scope / answer / evidence 基线。"""
    data, mock_build = _run_smoke_case(case, monkeypatch=monkeypatch, isolated_registry=isolated_registry)

    assert data["requested_scope_type"] == "single_kb"
    assert data["requested_kb_ids"] == [case["kb_id"]]
    assert data["effective_scope_type"] == "single_kb"
    assert data["effective_kb_ids"] == [case["kb_id"]]
    assert data["is_default_deny_applied"] is False
    assert data["isolation_level"] == "logical_filter_only"

    answer = data["answer"]
    for keypoint in case["expected_keypoints"]:
        assert keypoint in answer
    for blocked in case["must_not_contain"]:
        assert blocked not in answer

    returned_titles = {item["file"] for item in data["sources"]}
    returned_titles.update(item["title"] for item in data["evidence"])
    returned_titles.update(item["source"] for item in data["evidence"])
    for expected_title in case["expected_evidence"]:
        assert expected_title in returned_titles

    assert len(data["sources"]) == len(case["source_nodes"])
    assert len(data["evidence"]) == len(case["source_nodes"])

    report = build_chat_case_report(
        {
            "case_id": case["case_id"],
            "category": case.get("type", "positive"),
            "expected_doc": case["source_doc"],
            "expected_keypoints": case["expected_keypoints"],
            "must_not_contain": case["must_not_contain"],
            "expected_source_count": len(case["source_nodes"]),
            "preview_terms": [],
        },
        data,
        expected_kb_ids=[case["kb_id"]],
        expected_isolation_level="logical_filter_only",
    )
    assert report["passed"] is True
    assert report["keypoint_coverage"] == 1.0
    assert report["evidence_hit"] is True
    assert report["source_count_match"] is True
    mock_build.assert_called_once_with(kb_ids=[case["kb_id"]])



def test_single_kb_smoke_suite_metrics(monkeypatch, isolated_registry) -> None:
    """smoke 层也应输出统一 suite 指标，避免只有 case 级断言没有总览。"""
    reports = []
    for case in _SMOKE_CASES:
        data, _ = _run_smoke_case(case, monkeypatch=monkeypatch, isolated_registry=isolated_registry)
        reports.append(
            build_chat_case_report(
                {
                    "case_id": case["case_id"],
                    "category": case.get("type", "positive"),
                    "expected_doc": case["source_doc"],
                    "expected_keypoints": case["expected_keypoints"],
                    "must_not_contain": case["must_not_contain"],
                    "expected_source_count": len(case["source_nodes"]),
                    "preview_terms": [],
                },
                data,
                expected_kb_ids=[case["kb_id"]],
                expected_isolation_level="logical_filter_only",
            )
        )

    summary = summarize_chat_case_reports(reports)
    assert summary["total_cases"] == len(_SMOKE_CASES)
    assert summary["passed_cases"] == len(_SMOKE_CASES)
    assert summary["pass_rate"] == 1.0
    assert summary["scope_pass_rate"] == 1.0
    assert summary["average_keypoint_coverage"] == 1.0
    assert summary["evidence_hit_rate"] == 1.0
    assert summary["source_count_match_rate"] == 1.0
    assert summary["forbidden_term_clean_rate"] == 1.0
