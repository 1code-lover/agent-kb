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


def test_evaluate_case_uses_case_search_kb_ids(monkeypatch) -> None:
    """用例指定 search_kb_ids 时，查询和隔离判断都应使用它。"""
    captured_payload = {}

    def fake_post_json(api_base, path, payload, timeout):
        captured_payload.update(payload)
        return {
            "code": 0,
            "data": {
                "answer": "默认库回答",
                "sources": [
                    {
                        "file": "default-note.md",
                        "kb_id": "default",
                    }
                ],
            },
        }

    monkeypatch.setattr(grain_eval, "_post_json", fake_post_json)
    result = grain_eval.evaluate_case(
        {
            "id": "case-default",
            "query": "问题",
            "search_kb_ids": ["default"],
            "answerable": True,
            "relevant_documents": [{"file_name": "default-note.md"}],
        },
        api_base="http://127.0.0.1:18080",
        kb_id="grain-knowledge-base",
        timeout=1.0,
    )

    assert captured_payload["kb_ids"] == ["default"]
    assert result["requested_kb_ids"] == ["default"]
    assert result["kb_isolation"] == 1


def test_evaluate_case_counts_negative_cross_kb_answer_as_refusal(monkeypatch) -> None:
    """跨库隔离问题中，“不应返回”应计为正确边界回答。"""

    def fake_post_json(api_base, path, payload, timeout):
        return {
            "code": 0,
            "data": {
                "answer": "否。只搜索 default 知识库时，不应返回 grain-knowledge-base 的粮仓资料。",
                "sources": [
                    {
                        "file": "readme.md",
                        "kb_id": "grain-knowledge-base",
                    }
                ],
            },
        }

    monkeypatch.setattr(grain_eval, "_post_json", fake_post_json)
    result = grain_eval.evaluate_case(
        {
            "id": "case-cross-kb",
            "query": "只搜索 default 知识库时，是否应该返回 grain-knowledge-base 的粮仓资料？",
            "search_kb_ids": ["grain-knowledge-base"],
            "answerable": False,
            "relevant_documents": [{"file_name": "readme.md"}],
        },
        api_base="http://127.0.0.1:18080",
        kb_id="grain-knowledge-base",
        timeout=1.0,
    )

    assert result["refusal_correct"] == 1


def test_answer_is_refusal_like_accepts_empty_response() -> None:
    """无检索结果时的框架兜底文本应计为拒答。"""
    assert grain_eval._answer_is_refusal_like("Empty Response") is True


def test_answer_is_refusal_like_accepts_kb_missing_context_response() -> None:
    """知识库未覆盖的兜底长句也应计为拒答。"""
    answer = "粮仓知识库中未包含关于企业内部未公开合同条款的相关规定，因此无法根据现有信息提供具体回答。"

    assert grain_eval._answer_is_refusal_like(answer) is True


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


def test_classify_failure_groups_splits_rank_noise_and_ocr() -> None:
    """失败分组应能区分召回、排序、噪声和 OCR 类问题。"""
    rank_case = {
        "id": "rank",
        "answerable": True,
        "recall_at_5": 1,
        "mrr_at_5": 0.5,
        "kb_isolation": 1,
        "source_count": 1,
        "source_files_top5": ["a.docx"],
        "tags": [],
        "relevant_doc_types": [],
    }
    noise_case = {
        "id": "noise",
        "answerable": True,
        "recall_at_5": 0,
        "mrr_at_5": 0.0,
        "kb_isolation": 1,
        "source_count": 4,
        "source_files_top5": ["a.docx", "b.docx", "c.docx", "d.docx"],
        "tags": [],
        "relevant_doc_types": [],
    }
    ocr_case = {
        "id": "ocr",
        "answerable": True,
        "recall_at_5": 0,
        "mrr_at_5": 0.0,
        "kb_isolation": 1,
        "source_count": 0,
        "source_files_top5": [],
        "tags": ["pdf"],
        "relevant_doc_types": [".pdf"],
    }

    assert grain_eval.classify_failure_groups(rank_case) == ["rank_miss"]
    assert grain_eval.classify_failure_groups(noise_case) == ["retrieval_miss", "source_noise"]
    assert grain_eval.classify_failure_groups(ocr_case) == ["ocr_text_quality"]


def test_build_failure_groups_keeps_grouped_samples() -> None:
    """失败分组报告应保留每组样例。"""
    report = grain_eval.build_failure_groups(
        [
            {
                "id": "a",
                "query": "q1",
                "answerable": True,
                "recall_at_5": 0,
                "mrr_at_5": 0.0,
                "kb_isolation": 1,
                "source_count": 0,
                "source_files_top5": [],
                "tags": [],
                "relevant_doc_types": [],
            },
            {
                "id": "b",
                "query": "q2",
                "answerable": False,
                "refusal_correct": 0,
                "kb_isolation": 1,
                "source_count": 0,
                "source_files_top5": [],
                "tags": [],
                "relevant_doc_types": [],
            },
        ],
        limit=3,
    )

    assert report["retrieval_miss"]["count"] == 1
    assert report["retrieval_miss"]["samples"][0]["id"] == "a"
    assert report["refusal_miss"]["count"] == 1
    assert report["refusal_miss"]["samples"][0]["id"] == "b"
    assert report["duplicate_or_conflict"]["count"] == 0
    assert report["duplicate_or_conflict"]["samples"] == []
