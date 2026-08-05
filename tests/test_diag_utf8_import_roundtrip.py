"""diag_utf8_import_roundtrip 诊断合同测试。"""

from __future__ import annotations

from scripts.diag_utf8_import_roundtrip import EXPECTED_SNIPPET, _answer_meets_minimum_contract


def test_answer_meets_minimum_contract_accepts_full_expected_snippet() -> None:
    """若 answer 已经包含完整证据短语，应直接判定为通过。"""
    assert _answer_meets_minimum_contract(EXPECTED_SNIPPET) is True


def test_answer_meets_minimum_contract_accepts_concise_answer_when_grounded() -> None:
    """回答只说“知识库”时，只要 source / evidence 能证明完整结论就应视为链路有效。"""
    assert (
        _answer_meets_minimum_contract(
            "知识库",
            source_text=f"明确说明：{EXPECTED_SNIPPET}，文件夹只承担组织作用。",
        )
        is True
    )


def test_answer_meets_minimum_contract_rejects_anchor_without_grounding() -> None:
    """只有锚点答案但没有证据支撑时，不应误判为通过。"""
    assert (
        _answer_meets_minimum_contract(
            "知识库",
            source_text="只提到文件夹组织结构，没有提到授权边界。",
            evidence_excerpt="",
        )
        is False
    )
