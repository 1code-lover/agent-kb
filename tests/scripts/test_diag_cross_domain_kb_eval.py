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


def test_evaluate_positive_case_accepts_any_expected_term_group(monkeypatch) -> None:
    """正向用例可用任一同义关键词组判定答案命中。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "The platform duty lead gives the final rollback approval.",
                "sources": [{"kb_id": "diag-mixed-batch", "file": "release.md"}],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "mixed-positive",
            "kind": "positive",
            "kb_ids": ["diag-mixed-batch"],
            "question": "Who approves rollback?",
            "expected_any_term_groups": [
                ["平台值班主管", "最终的回滚批准"],
                ["platform duty lead", "final rollback approval"],
            ],
            "allowed_source_kb_ids": ["diag-mixed-batch"],
            "required_source_kb_ids": ["diag-mixed-batch"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is True
    assert result["checks"]["expected_terms_hit"] is True
    assert result["expected_any_term_groups"][1] == ["platform duty lead", "final rollback approval"]


def test_evaluate_positive_case_checks_required_source_files(monkeypatch) -> None:
    """正向用例可要求来源文件名命中指定片段。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "安全储粮方针是预防为主、综合防治。",
                "sources": [
                    {
                        "kb_id": "grain-knowledge-base",
                        "file": "AAA粮油安全储存守则_0119014f.docx",
                    }
                ],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "grain-source-file",
            "kind": "positive",
            "kb_ids": ["grain-knowledge-base"],
            "question": "方针是什么？",
            "expected_terms": ["预防为主", "综合防治"],
            "allowed_source_kb_ids": ["grain-knowledge-base"],
            "required_source_files": ["AAA粮油安全储存守则"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is True
    assert result["checks"]["required_source_file_hit"] is True
    assert result["source_files"] == ["AAA粮油安全储存守则_0119014f.docx"]


def test_evaluate_case_fails_on_forbidden_source_files(monkeypatch) -> None:
    """来源文件命中禁止片段时必须失败。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "未找到相关信息。",
                "sources": [{"kb_id": "grain-knowledge-base", "file": "desktop-model-workflow.md"}],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "forbidden-source-file",
            "kind": "negative",
            "kb_ids": ["grain-knowledge-base"],
            "question": "desktop passcode?",
            "forbidden_source_files": ["desktop-model-workflow.md"],
            "allowed_source_kb_ids": ["grain-knowledge-base"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is False
    assert result["checks"]["forbidden_source_file_clean"] is False


def test_evaluate_positive_case_checks_required_source_text(monkeypatch) -> None:
    """正向用例可要求 evidence/source 正文命中依据片段。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "Evidence preview must resolve this file after chat returns sources.",
                "sources": [
                    {
                        "kb_id": "diag-desktop",
                        "file": "desktop-model-workflow.md",
                        "text": "Evidence preview must resolve this file after chat returns sources.",
                    }
                ],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "desktop-source-text",
            "kind": "positive",
            "kb_ids": ["diag-desktop"],
            "question": "What should evidence preview resolve?",
            "expected_terms": ["resolve this file after chat returns sources"],
            "required_source_text_terms": ["Evidence preview must resolve this file after chat returns sources."],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is True
    assert result["checks"]["required_source_text_hit"] is True
    assert "Evidence preview must resolve" in result["source_text_preview"]


def test_evaluate_case_fails_on_forbidden_source_text(monkeypatch) -> None:
    """来源正文包含禁止片段时必须失败，即使答案没有复述。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "未找到相关信息。",
                "sources": [
                    {
                        "kb_id": "grain-knowledge-base",
                        "file": "scope.md",
                        "text": "The unique desktop workflow passcode is northagent-desktop-e2e-1786353063.",
                    }
                ],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "forbidden-source-text",
            "kind": "negative",
            "kb_ids": ["grain-knowledge-base"],
            "question": "desktop passcode?",
            "forbidden_source_text_terms": ["northagent-desktop-e2e-1786353063"],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is False
    assert result["checks"]["forbidden_source_text_clean"] is False


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


def test_evaluate_multi_turn_case_reuses_session_and_aggregates_turns(monkeypatch) -> None:
    """多轮追问用例应按顺序复用同一 session 并汇总逐轮结果。"""

    requests = []

    def fake_post_json(_api_base, _path, payload, _timeout):
        requests.append(payload)
        if len(requests) == 1:
            return {
                "code": 0,
                "data": {
                    "answer": "The diagnostic passcode is northagent-desktop-e2e-1786353063.",
                    "sources": [{"kb_id": "diag-desktop-e2e-1786353063"}],
                },
            }
        return {
            "code": 0,
            "data": {
                "answer": "Evidence preview should resolve this file after chat returns sources.",
                "sources": [{"kb_id": "diag-desktop-e2e-1786353063"}],
            },
        }

    monkeypatch.setattr(cross_eval, "_post_json", fake_post_json)
    result = cross_eval.evaluate_case(
        {
            "id": "desktop-follow-up",
            "kind": "positive",
            "focus": "desktop",
            "tags": ["multi-turn"],
            "kb_ids": ["diag-desktop-e2e-1786353063"],
            "turns": [
                {
                    "id": "seed",
                    "question": "What is the unique desktop workflow passcode?",
                    "expected_terms": ["northagent-desktop-e2e-1786353063"],
                    "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
                    "required_source_kb_ids": ["diag-desktop-e2e-1786353063"],
                },
                {
                    "id": "follow-up",
                    "question": "And what should evidence preview resolve?",
                    "expected_terms": ["resolve this file after chat returns sources"],
                    "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
                    "required_source_kb_ids": ["diag-desktop-e2e-1786353063"],
                },
            ],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is True
    assert result["is_multi_turn"] is True
    assert result["turn_count"] == 2
    assert result["passed_turn_count"] == 2
    assert result["failed_turn_ids"] == []
    assert result["turns"][0]["turn_id"] == "seed"
    assert result["turns"][1]["turn_id"] == "follow-up"
    assert requests[0]["session_id"] == requests[1]["session_id"]
    assert requests[0]["session_id"].startswith("cross-domain-eval::desktop-follow-up::")


def test_evaluate_multi_turn_case_fails_when_any_turn_fails(monkeypatch) -> None:
    """任一追问轮次失败时，顶层多轮用例也应失败。"""

    monkeypatch.setattr(
        cross_eval,
        "_post_json",
        lambda *_args: {
            "code": 0,
            "data": {
                "answer": "没有命中目标关键词。",
                "sources": [{"kb_id": "grain-knowledge-base"}],
            },
        },
    )

    result = cross_eval.evaluate_case(
        {
            "id": "grain-follow-up",
            "kind": "positive",
            "kb_ids": ["grain-knowledge-base"],
            "turns": [
                {
                    "id": "follow-up",
                    "question": "这个方针是什么？",
                    "expected_terms": ["预防为主"],
                    "allowed_source_kb_ids": ["grain-knowledge-base"],
                }
            ],
        },
        api_base="http://127.0.0.1:18080",
        timeout=1.0,
    )

    assert result["passed"] is False
    assert result["checks"]["turns_passed"] is False
    assert result["failed_turn_ids"] == ["follow-up"]
    assert result["turns"][0]["checks"]["expected_terms_hit"] is False


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
    assert saved["cases"][0]["case_source"] == str(cases_path)


def test_load_cases_accepts_object_payload_and_extra_cases(tmp_path: Path) -> None:
    """外部真实样本可用 {cases: [...]} 格式追加到默认基线。"""

    extra_path = tmp_path / "extra-cases.json"
    extra_path.write_text(
        json.dumps(
            {
                "name": "extra business suite",
                "cases": [
                    {
                        "id": "external-positive",
                        "kind": "positive",
                        "kb_ids": ["external-kb"],
                        "question": "q",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = cross_eval.load_cases(extra_paths=[extra_path])
    external = [item for item in cases if item.get("id") == "external-positive"]

    assert len(cases) == len(cross_eval.DEFAULT_CASES) + 1
    assert external[0]["case_source"] == str(extra_path)


def test_load_cases_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    """追加真实样本时，重复 id 应直接失败，避免报告混淆。"""

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {"id": "dup", "kind": "positive", "kb_ids": ["a"], "question": "q1"},
                {"id": "dup", "kind": "positive", "kb_ids": ["b"], "question": "q2"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    try:
        cross_eval.load_cases(cases_path)
    except ValueError as exc:
        assert "duplicate cross-domain case ids" in str(exc)
    else:
        raise AssertionError("expected duplicate case ids to fail")


def test_summarize_includes_focus_groups() -> None:
    """汇总应按 focus、case_source 和 tags 统计不同领域。"""

    report = cross_eval.summarize(
        [
            {
                "id": "a",
                "kind": "positive",
                "focus": "grain",
                "tags": ["long-question", "multi-hop"],
                "case_source": "default",
                "passed": True,
                "turn_count": 1,
            },
            {
                "id": "b",
                "kind": "negative",
                "focus": "cross-domain",
                "tags": ["refusal", "long-question"],
                "case_source": "extra.json",
                "passed": False,
                "turn_count": 1,
            },
            {
                "id": "c",
                "kind": "contract",
                "focus": "contract",
                "tags": ["contract"],
                "case_source": "default",
                "passed": True,
                "is_multi_turn": True,
                "turn_count": 2,
                "passed_turn_count": 2,
            },
        ]
    )

    assert report["contract_total"] == 1
    assert report["focus_summary"]["grain"]["pass_rate"] == 1.0
    assert report["focus_summary"]["contract"]["passed"] == 1
    assert report["case_source_summary"]["default"]["total"] == 2
    assert report["case_source_summary"]["extra.json"]["failed"] == 1
    assert report["tag_summary"]["long-question"]["total"] == 2
    assert report["tag_summary"]["long-question"]["failed"] == 1
    assert report["tag_summary"]["multi-hop"]["passed"] == 1
    assert report["multi_turn_total"] == 1
    assert report["turn_total"] == 4
    assert report["turn_passed"] == 3


def test_summarize_includes_failed_check_diagnostics() -> None:
    """失败汇总应按检查项和 case/turn 归因。"""

    report = cross_eval.summarize(
        [
            {
                "id": "single-fail",
                "kind": "positive",
                "focus": "grain",
                "tags": ["source-grounding"],
                "case_source": "default",
                "passed": False,
                "checks": {
                    "expected_terms_hit": True,
                    "required_source_file_hit": False,
                },
            },
            {
                "id": "multi-fail",
                "kind": "positive",
                "focus": "desktop",
                "tags": ["multi-turn"],
                "case_source": "extra.json",
                "is_multi_turn": True,
                "turn_count": 2,
                "passed_turn_count": 1,
                "passed": False,
                "checks": {"turns_passed": False},
                "turns": [
                    {
                        "turn_id": "seed",
                        "passed": True,
                        "checks": {"expected_terms_hit": True},
                    },
                    {
                        "turn_id": "follow-up",
                        "passed": False,
                        "checks": {
                            "expected_terms_hit": False,
                            "required_source_text_hit": False,
                        },
                    },
                ],
            },
        ]
    )

    assert report["failed"] == 2
    assert report["failure_check_summary"]["required_source_file_hit"]["case_ids"] == ["single-fail"]
    assert report["failure_check_summary"]["expected_terms_hit"]["case_ids"] == ["multi-fail"]
    assert report["failure_check_summary"]["expected_terms_hit"]["turn_ids"] == ["follow-up"]
    assert report["failure_check_summary"]["required_source_text_hit"]["turn_ids"] == ["follow-up"]
    assert report["failure_case_summary"] == [
        {
            "id": "multi-fail",
            "failed_checks": ["expected_terms_hit", "required_source_text_hit"],
            "failed_turns": ["follow-up"],
        },
        {
            "id": "single-fail",
            "failed_checks": ["required_source_file_hit"],
            "failed_turns": [],
        },
    ]


def test_load_cases_default_suite_includes_extended_references() -> None:
    """默认跨域评测集应包含新增的桌面、粮仓和 UTF-16 参考样本。"""

    cases = cross_eval.load_cases()
    case_ids = {str(item.get("id")) for item in cases}

    assert "grain-positive-safety-production" in case_ids
    assert "desktop-positive-preview" in case_ids
    assert "desktop-positive-passcode-older" in case_ids
    assert "exttext-positive-extensionless-utf8-folder" in case_ids
    assert "utf16-positive-folder-boundary" in case_ids
    assert "desktop-negative-older-passcode" in case_ids


def test_default_negative_forbidden_terms_do_not_duplicate_question_text() -> None:
    """负向禁止词不应只是题目复述，否则拒答时可能误判泄漏。"""

    for case in cross_eval.load_cases():
        if case.get("kind") != "negative":
            continue
        question = str(case.get("question") or "")
        for term in case.get("forbidden_terms") or []:
            assert str(term) not in question, f"{case.get('id')} forbidden term repeats the question"
