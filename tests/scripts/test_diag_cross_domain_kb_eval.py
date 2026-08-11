"""跨知识库泛化诊断脚本回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

import scripts.diag_cross_domain_kb_eval as cross_eval


def test_evaluate_positive_case_requires_expected_terms_and_source_kb(monkeypatch) -> None:
    """正向用例应同时命中答案关键词和目标 KB 来源。"""

    def fake_post_json(_api_base, _path, payload, _timeout):
        assert payload["kb_ids"] == ["grain-knowledge-base"]
        return {
            "code": 0,
            "data": {
                "answer": "安全储粮方针是预防为主、综合防治。",
                "sources": [{"kb_id": "grain-knowledge-base", "file": "AAA粮油安全储存守则.docx"}],
            },
        }

    monkeypatch.setattr(cross_eval, "_post_json", fake_post_json)
    result = cross_eval.evaluate_case(
        {
            "id": "grain-positive",
            "kind": "positive",
            "kb_ids": ["grain-knowledge-base"],
            "question": "方针是什么？",
            "expected_terms": ["预防为主", "综合防治"],
            "allowed_source_kb_ids": ["grain-knowledge-base"],
            "required_source_kb_ids": ["grain-knowledge-base"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is True
    assert result["checks"]["expected_terms_hit"] is True
    assert result["checks"]["required_source_kb_hit"] is True


def test_evaluate_negative_case_fails_on_exact_forbidden_evidence_leak(monkeypatch) -> None:
    """负向隔离用例中，evidence 泄漏精确禁止词必须失败。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "未找到相关信息。",
                "sources": [],
                "evidence": [{"kb_id": "diag-kb-utf8-1785505921", "excerpt": "文件夹只承担组织作用"}],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "leak",
            "kind": "negative",
            "kb_ids": ["grain-knowledge-base"],
            "question": "UTF-8 边界？",
            "forbidden_terms": ["文件夹只承担组织作用"],
            "forbidden_source_kb_ids": ["diag-kb-utf8-1785505921"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is False
    assert result["checks"]["forbidden_terms_clean"] is False
    assert result["checks"]["forbidden_source_kb_clean"] is False


def test_evaluate_negative_case_allows_similar_target_kb_content(monkeypatch) -> None:
    """目标 KB 的相似边界概念不应被误判为跨库泄漏。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "当前资料说明知识库是授权边界，文件夹用于组织材料。",
                "sources": [{"kb_id": "grain-knowledge-base", "file": "scope.md"}],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "similar",
            "kind": "negative",
            "kb_ids": ["grain-knowledge-base"],
            "question": "UTF-8 边界？",
            "forbidden_terms": ["文件夹只承担组织作用", "不承担权限隔离"],
            "allowed_source_kb_ids": ["grain-knowledge-base"],
            "forbidden_source_kb_ids": ["diag-kb-utf8-1785505921"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is True
    assert result["checks"]["forbidden_terms_clean"] is True
    assert result["checks"]["source_kb_allowed"] is True


def test_evaluate_case_marks_missing_source_kb_id_as_failure(monkeypatch) -> None:
    """有来源但缺 kb_id 时，不能证明来源隔离。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "安全储粮方针是预防为主、综合防治。",
                "sources": [{"file": "AAA粮油安全储存守则.docx"}],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "missing-kb",
            "kind": "positive",
            "kb_ids": ["grain-knowledge-base"],
            "question": "方针是什么？",
            "expected_terms": ["预防为主", "综合防治"],
            "allowed_source_kb_ids": ["grain-knowledge-base"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is False
    assert result["source_kb_id_missing_count"] == 1
    assert result["checks"]["source_kb_known"] is False
    assert result["checks"]["source_kb_allowed"] is False


def test_evaluate_contract_case_accepts_expected_http_error(monkeypatch) -> None:
    """多知识库契约拒绝应按预期 HTTP 状态通过。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 400,
            "_http_status": 400,
            "message": "不支持多知识库查询",
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "multi-kb-contract",
            "kind": "contract",
            "focus": "contract",
            "kb_ids": ["kb-a", "kb-b"],
            "question": "compare",
            "expected_http_status": 400,
            "expected_error_terms": ["不支持多知识库查询"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is True
    assert result["http_status"] == 400
    assert result["checks"]["http_status_ok"] is True
    assert result["checks"]["expected_error_terms_hit"] is True


def test_run_evaluation_writes_report_and_returns_nonzero_on_failure(tmp_path: Path, monkeypatch) -> None:
    """失败用例应写入报告，并返回非 0。"""

    cases_path = tmp_path / "cases.json"
    output_path = tmp_path / "report.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "fail",
                    "kind": "positive",
                    "kb_ids": ["kb-a"],
                    "question": "q",
                    "expected_terms": ["needle"],
                    "allowed_source_kb_ids": ["kb-a"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {"code": 0, "data": {"answer": "no hit", "sources": [{"kb_id": "kb-a"}]}},
    )

    report, exit_code = cross_eval.run_evaluation(
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
        output=str(output_path),
        cases_path=str(cases_path),
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["summary"]["failed"] == 1
    assert saved["cases"][0]["id"] == "fail"


def test_summarize_includes_focus_groups() -> None:
    """汇总应按 focus 统计不同领域。"""

    report = cross_eval.summarize(
        [
            {"id": "a", "kind": "positive", "focus": "grain", "passed": True},
            {"id": "b", "kind": "negative", "focus": "cross-domain", "passed": False},
            {"id": "c", "kind": "contract", "focus": "contract", "passed": True},
        ]
    )

    assert report["contract_total"] == 1
    assert report["focus_summary"]["grain"]["pass_rate"] == 1.0
    assert report["focus_summary"]["contract"]["passed"] == 1
