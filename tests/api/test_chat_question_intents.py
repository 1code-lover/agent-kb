"""chat_question_intents 的独立契约测试。"""

from __future__ import annotations

import re

from api.services import chat_question_intents


_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CJK_TOKEN_RE = re.compile(r"[一-鿿]+")


def _tokenize_text(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in _ASCII_TOKEN_RE.findall(str(text or "").lower()):
        token = raw.strip()
        if token:
            tokens.add(token)
    for block in _CJK_TOKEN_RE.findall(str(text or "")):
        token = block.strip()
        if len(token) >= 2:
            tokens.add(token)
    return tokens


def _build_source_text_blob(source: dict[str, str]) -> str:
    return " ".join(str(source.get(field) or "") for field in ("file", "title", "text", "excerpt"))


def test_question_benefits_from_brief_answer_expansion_skips_specialized_repairs():
    """preview / summary / multi-fact / targeted-fact 任一命中时，都不应走通用短答案扩写。"""
    assert (
        chat_question_intents.question_benefits_from_brief_answer_expansion(
            "What is the evidence preview for this file?",
            question_requests_preview_expansion=lambda question: True,
            question_requests_summary_answer=lambda question: False,
            question_requests_multi_fact_merge=lambda question: False,
            question_requests_targeted_fact_answer=lambda question: False,
        )
        is False
    )
    assert (
        chat_question_intents.question_benefits_from_brief_answer_expansion(
            "Compare the approval matrix and SLA: who is the approver and who is the on-call manager?",
            question_requests_preview_expansion=lambda question: False,
            question_requests_summary_answer=lambda question: False,
            question_requests_multi_fact_merge=lambda question: False,
            question_requests_targeted_fact_answer=lambda question: True,
        )
        is False
    )
    assert (
        chat_question_intents.question_benefits_from_brief_answer_expansion(
            "Who is the approver?",
            question_requests_preview_expansion=lambda question: False,
            question_requests_summary_answer=lambda question: False,
            question_requests_multi_fact_merge=lambda question: False,
            question_requests_targeted_fact_answer=lambda question: False,
        )
        is True
    )


def test_question_requests_exact_source_phrase_detects_precise_prompt():
    """精确原文类问题应走独立 classifier。"""
    assert chat_question_intents.question_requests_exact_source_phrase("这段规则的精确原文是什么？") is True
    assert chat_question_intents.question_requests_exact_source_phrase("Summarize the rule in one sentence.") is False


def test_question_may_need_exact_term_repair_prefers_preview_boundary_and_exact_questions():
    """preview / boundary / exact-source 题应直接命中 exact-term repair。"""
    assert (
        chat_question_intents.question_may_need_exact_term_repair(
            "What exact phrase should the evidence preview resolve back to?",
            question_requests_exact_source_phrase=chat_question_intents.question_requests_exact_source_phrase,
            question_requests_preview_expansion=chat_question_intents.question_requests_preview_expansion,
            question_requests_boundary_answer=chat_question_intents.question_requests_boundary_answer,
            question_requests_scope_definition=chat_question_intents.question_requests_scope_definition,
            question_requests_targeted_fact_answer=lambda question: False,
            question_requests_identifier_like_field=lambda question: False,
        )
        is True
    )



def test_question_may_need_exact_term_repair_keeps_plain_targeted_fact_out_but_accepts_field_like_targeted_prompts():
    """plain targeted-fact 不应默认叠加 exact repair；字段/echo 类 targeted 题仍应命中。"""
    assert (
        chat_question_intents.question_may_need_exact_term_repair(
            "Compare the approval matrix and SLA: who is the final approver and who is the on-call manager?",
            question_requests_exact_source_phrase=chat_question_intents.question_requests_exact_source_phrase,
            question_requests_preview_expansion=chat_question_intents.question_requests_preview_expansion,
            question_requests_boundary_answer=chat_question_intents.question_requests_boundary_answer,
            question_requests_scope_definition=chat_question_intents.question_requests_scope_definition,
            question_requests_targeted_fact_answer=chat_question_intents.question_requests_targeted_fact_answer,
            question_requests_identifier_like_field=lambda question: False,
        )
        is False
    )
    assert (
        chat_question_intents.question_may_need_exact_term_repair(
            "From the PDF preview guide, which response field should echo the active knowledge base and what must the preview excerpt resolve back to?",
            question_requests_exact_source_phrase=chat_question_intents.question_requests_exact_source_phrase,
            question_requests_preview_expansion=chat_question_intents.question_requests_preview_expansion,
            question_requests_boundary_answer=chat_question_intents.question_requests_boundary_answer,
            question_requests_scope_definition=chat_question_intents.question_requests_scope_definition,
            question_requests_targeted_fact_answer=chat_question_intents.question_requests_targeted_fact_answer,
            question_requests_identifier_like_field=lambda question: True,
        )
        is True
    )


def test_sources_support_identifier_like_field_requires_field_signal_not_topic_overlap():
    """war-room 主题词重叠不能替代 bridge URL 的字段证据。"""
    sources = [
        {
            "file": "handover-sla.md",
            "text": "War-room handover SLA: escalate P1 incidents to the on-call manager within 15 minutes.",
        }
    ]

    assert (
        chat_question_intents.sources_support_identifier_like_field(
            "What bridge URL is listed for the war-room handover?",
            sources,
            tokenize_text=_tokenize_text,
            build_source_text_blob=_build_source_text_blob,
        )
        is False
    )


def test_question_requests_identifier_like_field_detects_pager_rotation_id():
    """pager rotation id 这类问题不能因为 id 停用而漏检。"""
    assert (
        chat_question_intents.question_requests_identifier_like_field(
            "What pager rotation id is listed in the PDF war-room handover sheet?",
            tokenize_text=_tokenize_text,
        )
        is True
    )


def test_question_requests_negative_contract_detects_refusal_scope_contract():
    """negative-contract 问题应由独立 classifier 识别。"""
    assert chat_question_intents.question_requests_negative_contract(
        "When evidence is sparse, what no confirmable information anchor and active knowledge base boundary should the assistant keep?"
    ) is True
    assert chat_question_intents.question_requests_negative_contract(
        "Who is the final approver for the cutover?"
    ) is False



def test_question_requests_negative_contract_rejects_plain_active_pdf_scope_contract():
    """仅提到 active PDF knowledge base 的 scope-contract 问句，不应被误判为 negative-contract。"""
    assert chat_question_intents.question_requests_negative_contract(
        "In the PDF scope contract, which response field should echo the active PDF knowledge base, and what scope type must remain in force?"
    ) is False



def test_question_requests_negative_contract_accepts_missing_confirmable_evidence_wording():
    """missing/absent confirmable evidence 这类改写，仍应视为 negative-contract。"""
    assert chat_question_intents.question_requests_negative_contract(
        "If confirmable evidence is missing in the active PDF knowledge base, what should the assistant say and what must it avoid?"
    ) is True
    assert chat_question_intents.question_requests_negative_contract(
        "When confirmable information is absent, what should the assistant say and what must it avoid doing?"
    ) is True


def test_question_requests_negative_contract_accepts_chinese_refusal_scope_contract_wording():
    """中文“无可确认信息 + 不得编造/外部记忆”问句，也应命中 negative-contract classifier。"""
    assert chat_question_intents.question_requests_negative_contract(
        "如果当前知识库里没有可确认信息，助手应该怎么回答，并且不能从外部记忆编造什么？"
    ) is True
    assert chat_question_intents.question_requests_negative_contract(
        "当缺少可确认的证据时，回复必须留在当前知识库范围内吗？"
    ) is True


def test_question_requests_targeted_fact_answer_accepts_literal_boundary_contract():
    """带字面路径 + access-control 的复合问句，应识别为 targeted-fact。"""
    assert (
        chat_question_intents.question_requests_targeted_fact_answer(
            "For `ops/cutover/runbook/`, what remains the authorization boundary and what folder path is organization only?",
            extract_literal_question_terms=lambda question: ["ops/cutover/runbook/"],
        )
        is True
    )


def test_question_requests_targeted_fact_answer_rejects_single_question_cross_source_boundary_prompt():
    """跨 source 的单一 boundary 问句，不应仅因 source 名里出现 and 就误判成 targeted-fact。"""
    assert (
        chat_question_intents.question_requests_targeted_fact_answer(
            "Across the scope manual and the folder boundary note, what remains the authorization boundary rule?"
        )
        is False
    )



def test_question_requests_targeted_fact_answer_accepts_parallel_cjk_role_question():
    """中文“X 和 Y 分别是谁”这类并列角色问句，也应命中 targeted-fact。"""
    question = "最终审批人和 rollback owner 分别是谁？"

    assert chat_question_intents.question_requests_targeted_fact_answer(question) is True
    assert chat_question_intents.split_targeted_fact_question(
        question,
        question_requests_targeted_fact_answer=lambda raw: chat_question_intents.question_requests_targeted_fact_answer(raw),
    ) == ["最终审批人是谁", "rollback owner是谁"]


def test_split_targeted_fact_question_strips_shared_prefixes():
    """切分 targeted-fact 问句时应去掉 compare/across 共享前缀。"""
    question = (
        "Compare the payroll cutover approval matrix and the war-room handover SLA: "
        "who is the final approver and who is the on-call manager?"
    )

    parts = chat_question_intents.split_targeted_fact_question(
        question,
        question_requests_targeted_fact_answer=lambda raw: chat_question_intents.question_requests_targeted_fact_answer(raw),
    )

    assert parts == ["who is the final approver", "who is the on-call manager"]


def test_question_requests_scope_definition_requires_definition_shape_not_bare_which_or_scope_words():
    """scope-definition classifier 不应因为裸 which/scope 词面就误判 targeted-fact。"""
    assert chat_question_intents.question_requests_scope_definition(
        "Which field mirrors the chosen KB?"
    ) is False
    assert chat_question_intents.question_requests_scope_definition(
        "What scope type must remain in force?"
    ) is False
    assert chat_question_intents.question_requests_scope_definition(
        "In the PDF scope manual, which field mirrors the chosen KB, and what boundary acts as the real permission wall?"
    ) is False


def test_question_requests_scope_definition_still_accepts_true_definition_questions():
    """真正的适用范围/定义类问句仍应命中 classifier。"""
    assert chat_question_intents.question_requests_scope_definition(
        "What is the scope of the one-card system?"
    ) is True
    assert chat_question_intents.question_requests_scope_definition(
        "非直属企业“一卡通”系统适用于哪些收储库点？"
    ) is True


def test_question_requests_multi_fact_merge_rejects_targeted_and_what_question():
    """带 and what 的 targeted-fact 问句，不应再被粗暴归类为 multi-fact merge。"""
    assert chat_question_intents.question_requests_multi_fact_merge(
        "From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?"
    ) is False



def test_question_requests_multi_fact_merge_keeps_explicit_merge_prompt():
    """显式要求 one answer 的复合问题，仍应保留 multi-fact merge 信号。"""
    assert chat_question_intents.question_requests_multi_fact_merge(
        "In one answer, tell me who gives the final rollback approval and what every evidence preview should include."
    ) is True

def test_question_prefers_cross_source_fact_assembly_detects_compare_prompt():
    """compare/across 问句应显式标记为跨 source 组装。"""
    assert chat_question_intents.question_prefers_cross_source_fact_assembly(
        "Compare the approval matrix and SLA: who is the approver and who is the on-call manager?"
    ) is True
    assert chat_question_intents.question_prefers_cross_source_fact_assembly(
        "Who is the approver?"
    ) is False

def test_question_requests_negative_contract_accepts_mixed_language_refusal_contract_wording():
    """中英混排的 current KB / confirmable evidence / 外部记忆 问句，也应命中 negative-contract classifier。"""
    assert chat_question_intents.question_requests_negative_contract(
        "If 当前知识库 has no confirmable evidence, can the assistant fabricate from 外部记忆?"
    ) is True
    assert chat_question_intents.question_requests_negative_contract(
        "在 active KB 里如果 confirmable information is absent，助手是不是不能 fabricate?"
    ) is True


def test_question_requests_negative_contract_rejects_mixed_language_scope_only_wording():
    """仅讨论 current KB / active KB 的 scope 字段回显，不应因中英混排被误判成 negative-contract。"""
    assert chat_question_intents.question_requests_negative_contract(
        "Which response field should echo current KB / active KB, and what scope type should remain aligned?"
    ) is False
