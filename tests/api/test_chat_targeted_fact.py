"""chat_targeted_fact 的独立契约测试。"""

from __future__ import annotations

import re

from api.services import chat_question_intents, chat_targeted_fact


_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CJK_TOKEN_RE = re.compile(r"[一-鿿]+")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?;\n]+|(?<=\.)\s+")
_CLAUSE_SPLIT_RE = re.compile(r"[，,]+|(?<!\d)[：:]+(?!\d)")
_TIME_VALUE_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_LITERAL_PATH_RE = re.compile(r"`?([a-z0-9_.-]+(?:/[a-z0-9_.-]+)+/?)`?", re.IGNORECASE)


def _iter_boundary_support_texts(source: dict[str, str]) -> list[str]:
    texts: list[str] = []
    for field in ("text", "excerpt"):
        value = str(source.get(field) or "").strip()
        if value:
            texts.append(value)
    return texts


def _normalize_expanded_answer(text: str) -> str:
    return str(text or "").strip()


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


def _extract_literal_question_terms(question: str) -> list[str]:
    return [
        match.group(1)
        for match in _LITERAL_PATH_RE.finditer(str(question or ""))
        if match.group(1)
    ]


def _dedupe_sources_by_file(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        kb_id = str(source.get("kb_id") or "default").strip() or "default"
        file_name = str(source.get("file") or source.get("title") or "").strip()
        if not file_name:
            deduped.append(source)
            continue
        key = (kb_id, file_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _build_hooks() -> chat_targeted_fact.TargetedFactHooks:
    hooks: chat_targeted_fact.TargetedFactHooks | None = None

    def _iter_targeted(source: dict[str, str]) -> list[str]:
        return chat_targeted_fact.iter_targeted_answer_candidates(source, hooks=hooks)

    hooks = chat_targeted_fact.TargetedFactHooks(
        iter_boundary_support_texts=_iter_boundary_support_texts,
        normalize_expanded_answer=_normalize_expanded_answer,
        tokenize_text=_tokenize_text,
        normalize_targeted_subquestion=chat_question_intents.normalize_targeted_subquestion,
        extract_literal_question_terms=_extract_literal_question_terms,
        question_requests_negative_contract=chat_question_intents.question_requests_negative_contract,
        question_requests_summary_answer=chat_question_intents.question_requests_summary_answer,
        question_prefers_cross_source_fact_assembly=chat_question_intents.question_prefers_cross_source_fact_assembly,
        split_targeted_fact_question=lambda question: chat_question_intents.split_targeted_fact_question(
            question,
            question_requests_targeted_fact_answer=chat_question_intents.question_requests_targeted_fact_answer,
        ),
        dedupe_sources_by_file=_dedupe_sources_by_file,
        iter_targeted_answer_candidates=_iter_targeted,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        clause_split_re=_CLAUSE_SPLIT_RE,
        time_value_re=_TIME_VALUE_RE,
        literal_path_re=_LITERAL_PATH_RE,
    )
    return hooks


def test_iter_targeted_answer_candidates_splits_lines_sentences_and_clauses():
    hooks = _build_hooks()
    source = {
        "text": "Final approver: Li Qing. Rollback owner: Zhou Yu\nPreview fields: doc_id, preview_locator"
    }

    candidates = chat_targeted_fact.iter_targeted_answer_candidates(source, hooks=hooks)

    assert "Final approver: Li Qing. Rollback owner: Zhou Yu" in candidates
    assert "Final approver: Li Qing" in candidates
    assert "Rollback owner: Zhou Yu" in candidates
    assert "Preview fields: doc_id, preview_locator" in candidates


def test_score_targeted_answer_candidate_prefers_role_clause():
    hooks = _build_hooks()
    question = "Compare the payroll cutover approval matrix and the war-room handover SLA: who is the final approver and who is the on-call manager?"

    score = chat_targeted_fact.score_targeted_answer_candidate(
        question,
        "who is the final approver",
        "Final approver: Release Manager Li Qing.",
        hooks=hooks,
    )

    assert score is not None


def test_build_targeted_question_signals_groups_role_scope_preview_and_negative_contract():
    hooks = _build_hooks()
    question = (
        "Under the evidence board, if confirmable evidence is missing in the active knowledge base, "
        "who signs the final rollback approval, what scope type remains in force, and what should the preview excerpt resolve back to?"
    )
    subquestion = (
        "who signs the final rollback approval, what scope type remains in force, "
        "and what should the preview excerpt resolve back to if confirmable evidence is missing in the active knowledge base"
    )
    context = chat_targeted_fact._build_targeted_question_context(
        question,
        subquestion,
        "Single-kb responses should carry doc_id and preview_locator.",
        hooks=hooks,
    )

    assert context is not None
    signals = chat_targeted_fact._build_targeted_question_signals(context, hooks=hooks)

    assert signals["asks_sign_role"] is True
    assert signals["asks_role"] is True
    assert signals["asks_scope_type"] is True
    assert signals["asks_preview_contract"] is True
    assert signals["asks_preview_resolution"] is True
    assert signals["asks_negative_contract"] is True


def test_compute_targeted_structural_bonuses_gates_preview_scope_and_negative_signals():
    hooks = _build_hooks()
    question = (
        "Under the single KB scope contract, if confirmable evidence is missing in the active knowledge base, "
        "can the effective scope expand beyond the requested knowledge base, what scope type remains in force, "
        "which fields must every answer carry, and what should the preview excerpt resolve back to?"
    )
    subquestion = question
    candidate = (
        "Single-kb responses must echo requested_scope_type, requested_kb_ids, effective_scope_type, effective_kb_ids, doc_id, preview_locator, excerpt. "
        "The scope type should remain single_kb. "
        "The effective scope must stay inside the explicitly requested knowledge base. "
        "Every preview excerpt must resolve back to the original PDF chunk. "
        "No confirmable information is available in the current knowledge base. "
        "Stay inside the active knowledge base. "
        "The assistant must not fabricate an answer from outside memory."
    )

    context = chat_targeted_fact._build_targeted_question_context(
        question, subquestion, candidate, hooks=hooks
    )

    assert context is not None
    signals = chat_targeted_fact._build_targeted_question_signals(context, hooks=hooks)
    features = chat_targeted_fact._extract_targeted_candidate_features(
        context, hooks=hooks
    )
    bonuses = chat_targeted_fact._compute_targeted_structural_bonuses(
        context, signals, features
    )

    assert bonuses["field_bonus"] == 7
    assert bonuses["recognized_field_count"] == 7
    assert bonuses["scope_type_bonus"] == 2
    assert bonuses["effective_scope_type_bonus"] == 2
    assert bonuses["scope_boundary_bonus"] == 1
    assert bonuses["effective_scope_boundary_bonus"] == 1
    assert bonuses["preview_bonus"] == 4
    assert bonuses["effective_preview_bonus"] == 1
    assert bonuses["negative_bonus"] == 3
    assert bonuses["effective_negative_bonus"] == 3


def test_best_single_source_negative_contract_answer_compacts_three_required_segments():
    hooks = _build_hooks()
    source = {
        "file": "scope-guard.md",
        "text": "No confirmable information is available in the current knowledge base.\nStay inside the active knowledge base.\nThe assistant must not fabricate outside memory.",
    }

    result = chat_targeted_fact.best_single_source_negative_contract_answer(
        "When evidence is sparse, what no confirmable information anchor and active knowledge base boundary should the assistant keep, and how should it avoid fabricated memory?",
        [source],
        hooks=hooks,
    )

    assert result is not None
    answer, used_sources = result
    assert "No confirmable information" in answer
    assert "active knowledge base" in answer
    assert "must not fabricate" in answer
    assert used_sources == [source]


def test_best_single_source_negative_contract_answer_accepts_missing_confirmable_evidence_wording():
    hooks = _build_hooks()
    source = {
        "file": "pdf-refusal.md",
        "text": "No confirmable information is available in the current knowledge base.\nStay inside the active PDF knowledge base.\nThe assistant must not fabricate an answer from outside memory.",
    }

    result = chat_targeted_fact.best_single_source_negative_contract_answer(
        "If confirmable evidence is missing in the active PDF knowledge base, what should the assistant say and what must it avoid?",
        [source],
        hooks=hooks,
    )

    assert result is not None
    answer, used_sources = result
    assert "No confirmable information" in answer
    assert "active PDF knowledge base" in answer
    assert "must not fabricate" in answer
    assert used_sources == [source]


def test_expand_targeted_source_segments_with_local_context_keeps_adjacent_narrative_line():
    hooks = _build_hooks()
    source = {
        "text": "Final approver: Release Manager Li Qing\nThis approval is required before rollout.\nRollback owner: Platform SRE Wang Lei"
    }

    expanded = chat_targeted_fact.expand_targeted_source_segments_with_local_context(
        source,
        [
            "Final approver: Release Manager Li Qing",
            "Rollback owner: Platform SRE Wang Lei",
        ],
        hooks=hooks,
    )

    assert expanded == [
        "Final approver: Release Manager Li Qing",
        "This approval is required before rollout.",
        "Rollback owner: Platform SRE Wang Lei",
    ]


def test_expand_targeted_source_segments_with_local_context_tolerates_cjk_terminal_punctuation_mismatch():
    hooks = _build_hooks()
    source = {
        "text": (
            "handover window 扫描页没有文字层时，OCR fallback must merge every predict batch for the same page.\n"
            "中文流程说明也要写回当前知识库，避免导入后只剩图片像素。\n"
            "Scanned PDF content should still become searchable evidence in the active knowledge base."
        )
    }

    expanded = chat_targeted_fact.expand_targeted_source_segments_with_local_context(
        source,
        [
            "handover window 扫描页没有文字层时，OCR fallback must merge every predict batch for the same page。",
            "Scanned PDF content should still become searchable evidence in the active knowledge base.",
        ],
        hooks=hooks,
    )

    assert expanded == [
        "handover window 扫描页没有文字层时，OCR fallback must merge every predict batch for the same page.",
        "中文流程说明也要写回当前知识库，避免导入后只剩图片像素。",
        "Scanned PDF content should still become searchable evidence in the active knowledge base.",
    ]


def test_maybe_answer_targeted_fact_question_from_sources_uses_answer_text_negative_contract_without_sources():
    hooks = _build_hooks()

    answer, used_sources = (
        chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(
            "If confirmable evidence is missing in the active knowledge base, what should the assistant say and what must it avoid?",
            (
                "No confirmable information is available in the current knowledge base.\n"
                "Stay inside the active knowledge base.\n"
                "The assistant must not fabricate an answer from outside memory."
            ),
            [],
            hooks=hooks,
        )
    )

    assert "No confirmable information" in answer
    assert "active knowledge base" in answer
    assert "must not fabricate" in answer
    assert used_sources == []


def test_maybe_answer_targeted_fact_question_from_sources_supports_chinese_negative_contract_source():
    hooks = _build_hooks()

    answer, used_sources = (
        chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(
            "如果当前知识库里没有可确认信息，助手应该怎么回答，并且不能从外部记忆编造什么？",
            "",
            [
                {
                    "file": "zh-refusal-guide.md",
                    "text": (
                        "当前知识库中没有可确认的信息。\n"
                        "请留在当前知识库范围内。\n"
                        "助手不得从外部记忆编造答案。"
                    ),
                }
            ],
            hooks=hooks,
        )
    )

    assert "当前知识库中没有可确认的信息" in answer
    assert "当前知识库范围内" in answer
    assert "不得从外部记忆编造答案" in answer
    assert [source["file"] for source in used_sources] == ["zh-refusal-guide.md"]

def test_maybe_answer_targeted_fact_question_from_sources_collects_alignment_fields_and_boundary():
    hooks = _build_hooks()

    answer, used_sources = (
        chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(
            "Under the single KB scope contract, can the effective scope expand beyond the requested KB, and which two id fields should stay aligned with the request?",
            "The effective scope must stay inside the explicitly requested knowledge base.\nSingle-kb chat responses must echo the following fields exactly.",
            [
                {
                    "file": "scope-contract.md",
                    "text": (
                        "Single-kb chat responses must echo the following fields exactly:\n"
                        "- requested_scope_type\n"
                        "- requested_kb_ids\n"
                        "- effective_scope_type\n"
                        "- effective_kb_ids\n"
                        "- is_default_deny_applied\n"
                        "- isolation_level\n\n"
                        "The effective scope must stay inside the explicitly requested knowledge base."
                    ),
                }
            ],
            hooks=hooks,
        )
    )

    assert "explicitly requested knowledge base" in answer
    assert "requested_kb_ids" in answer
    assert "effective_kb_ids" in answer
    assert [source["file"] for source in used_sources] == ["scope-contract.md"]


def test_maybe_answer_targeted_fact_question_from_sources_supports_parallel_cjk_role_question():
    hooks = _build_hooks()

    answer, used_sources = (
        chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(
            "最终审批人和 rollback owner 分别是谁？",
            "Li Qing",
            [
                {
                    "file": "cutover-roles.md",
                    "text": ("Final approver: Li Qing.\nRollback owner: Wang Lei."),
                }
            ],
            hooks=hooks,
        )
    )

    assert "Final approver: Li Qing" in answer
    assert "Rollback owner: Wang Lei" in answer
    assert [source["file"] for source in used_sources] == ["cutover-roles.md"]


def test_maybe_answer_targeted_fact_question_from_sources_prefers_distinct_cross_source_values():
    hooks = _build_hooks()

    answer, used_sources = (
        chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(
            "Across the payroll cutover approval matrix and the war-room handover SLA, when is the checklist deadline and what is the escalation interval?",
            "",
            [
                {
                    "file": "cutover-approval.md",
                    "text": (
                        "Payroll cutover approval matrix.\n"
                        "Checklist must be signed before 22:30 Beijing time.\n"
                        "Rollback owner: Platform SRE Wang Lei."
                    ),
                },
                {
                    "file": "handover-sla.md",
                    "text": (
                        "War-room handover SLA.\n"
                        "P1 cutover incident must be escalated to on-call manager Zhao Lin within 15 minutes.\n"
                        "Service desk first-ack SLA is 5 minutes."
                    ),
                },
            ],
            hooks=hooks,
        )
    )

    assert "22:30 Beijing time" in answer
    assert "15 minutes" in answer
    assert [source["file"] for source in used_sources] == [
        "cutover-approval.md",
        "handover-sla.md",
    ]
    assert "first-ack" not in used_sources[1]["text"].lower()


def test_maybe_answer_targeted_fact_question_from_sources_keeps_pdf_preview_resolution_clause_minimal():
    hooks = _build_hooks()

    answer, used_sources = (
        chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(
            "From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?",
            "",
            [
                {
                    "file": "preview-guide.pdf",
                    "text": (
                        "Evidence preview for PDF imports.\n"
                        "Every answer should carry doc_id and preview_locator.\n"
                        "中文补充：每条 PDF 证据回答都必须带上 doc_id 和 preview_locator，方便定位原文片段。\n"
                        "preview excerpt must resolve back to the original PDF chunk."
                    ),
                }
            ],
            hooks=hooks,
        )
    )

    assert "doc_id" in answer
    assert "preview_locator" in answer
    assert "original PDF chunk" in answer
    assert [source["file"] for source in used_sources] == ["preview-guide.pdf"]
    assert used_sources[0]["text"].count("preview excerpt") == 1


def test_collect_targeted_role_labels_supports_cjk_aliases():
    labels = chat_targeted_fact._collect_targeted_role_labels(
        "审批人和值班经理分别是谁？",
        "审批人和值班经理分别是谁？",
    )

    assert labels == ["approver", "on-call manager"]


def test_compute_targeted_candidate_penalties_adds_exact_pair_noise_penalty():
    hooks = _build_hooks()
    question = "Under the response contract, which two id fields should stay aligned with the request?"
    candidate = "Single-kb chat responses must echo requested_kb_ids, effective_kb_ids, requested_scope_type."

    context = chat_targeted_fact._build_targeted_question_context(
        question, question, candidate, hooks=hooks
    )

    assert context is not None
    signals = chat_targeted_fact._build_targeted_question_signals(context, hooks=hooks)
    features = chat_targeted_fact._extract_targeted_candidate_features(
        context, hooks=hooks
    )
    bonuses = chat_targeted_fact._compute_targeted_candidate_bonuses(
        context, signals, features
    )
    penalties = chat_targeted_fact._compute_targeted_candidate_penalties(
        context, signals, bonuses
    )

    assert signals["asks_exactly_two_fields"] is True
    assert bonuses["recognized_field_count"] == 3
    assert penalties["exact_two_fields_penalty"] == 1
