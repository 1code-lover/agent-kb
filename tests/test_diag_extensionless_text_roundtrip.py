"""diag_extensionless_text_roundtrip 合同测试。"""

from __future__ import annotations

from scripts.diag_extensionless_text_roundtrip import _answer_meets_minimum_contract, _contains_terms



def test_contains_terms_is_case_insensitive() -> None:
    """关键词匹配应忽略大小写与多余空白。"""
    assert _contains_terms("Knowledge   Base remains the authorization boundary", ["knowledge base", "authorization boundary"])



def test_answer_meets_minimum_contract_accepts_grounded_concise_answer() -> None:
    """简短回答只要被 source/evidence 充分支撑，就应视为通过。"""
    assert _answer_meets_minimum_contract(
        "knowledge base",
        expected_terms=("knowledge base", "authorization boundary"),
        answer_anchor_terms=("knowledge base",),
        source_text="The authorization boundary remains the knowledge base.",
        evidence_excerpt="",
    )



def test_answer_meets_minimum_contract_rejects_ungrounded_anchor_only_answer() -> None:
    """只有锚点答案、但没有证据支撑时，不应误判为通过。"""
    assert not _answer_meets_minimum_contract(
        "knowledge base",
        expected_terms=("knowledge base", "authorization boundary"),
        answer_anchor_terms=("knowledge base",),
        source_text="Folder is only an organization object.",
        evidence_excerpt="",
    )
