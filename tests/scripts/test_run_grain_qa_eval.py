"""粮仓知识库 QA 评测脚本回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

import scripts.run_grain_qa_eval as grain_eval


def test_evaluate_case_marks_missing_source_kb_id_as_isolation_failure(monkeypatch) -> None:
    """sources 有引用但缺少 kb_id 时，隔离校验必须失败。"""

    def fake_post_json(api_base, path, payload, timeout):
        return {
            "code": 0,
            "data": {
                "answer": "命中文档",
                "sources": [
                    {
                        "file": "policy.docx",
                    }
                ],
            },
        }

    monkeypatch.setattr(grain_eval, "_post_json", fake_post_json)
    result = grain_eval.evaluate_case(
        {
            "id": "case-1",
            "query": "问题",
            "answerable": True,
            "relevant_documents": [{"file_name": "policy.docx"}],
        },
        api_base="http://127.0.0.1:18080",
        kb_id="grain-knowledge-base",
        timeout=1.0,
    )

    assert result["recall_at_5"] == 1
    assert result["kb_isolation"] == 0
    assert result["source_count"] == 1
    assert result["source_kb_ids"] == []
    assert result["kb_id_missing_count"] == 1


def test_evaluate_case_accepts_all_sources_with_target_kb_id(monkeypatch) -> None:
    """所有引用来源都带目标 kb_id 时，隔离校验通过。"""

    def fake_post_json(api_base, path, payload, timeout):
        return {
            "code": 0,
            "data": {
                "answer": "命中文档",
                "sources": [
                    {
                        "file": "policy_ab12cd34.docx",
                        "kb_id": "grain-knowledge-base",
                    }
                ],
            },
        }

    monkeypatch.setattr(grain_eval, "_post_json", fake_post_json)
    result = grain_eval.evaluate_case(
        {
            "id": "case-2",
            "query": "问题",
            "answerable": True,
            "relevant_documents": [{"file_name": "policy.docx"}],
        },
        api_base="http://127.0.0.1:18080",
        kb_id="grain-knowledge-base",
        timeout=1.0,
    )

    assert result["recall_at_5"] == 1
    assert result["kb_isolation"] == 1
    assert result["source_kb_ids"] == ["grain-knowledge-base"]
    assert result["kb_id_missing_count"] == 0


def test_file_sha256_tracks_case_file_content(tmp_path: Path) -> None:
    """报告可通过 cases_sha256 追溯评测用例版本。"""
    cases = tmp_path / "verified.jsonl"
    cases.write_text(json.dumps({"id": "a"}, ensure_ascii=False) + "\n", encoding="utf-8")

    first_hash = grain_eval.file_sha256(cases)
    cases.write_text(json.dumps({"id": "b"}, ensure_ascii=False) + "\n", encoding="utf-8")
    second_hash = grain_eval.file_sha256(cases)

    assert len(first_hash) == 64
    assert len(second_hash) == 64
    assert first_hash != second_hash
