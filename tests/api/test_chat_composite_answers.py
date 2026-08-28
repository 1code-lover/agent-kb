"""chat_composite_answers 的独立契约测试。"""

from __future__ import annotations

import re

from api.services import chat_composite_answers, chat_question_intents


_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CJK_TOKEN_RE = re.compile(r"[一-鿿]+")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?;\n]+|(?<=\.)\s+")
_TIME_VALUE_RE = re.compile(r"\b\d{1,2}:\d{2}\b")


def _tokenize_text(text: str) -> set[str]:
    tokens: set[str] = set()
    lowered = str(text or "").lower()
    for raw in _ASCII_TOKEN_RE.findall(lowered):
        token = raw.strip()
        if token:
            tokens.add(token)
    for block in _CJK_TOKEN_RE.findall(str(text or "")):
        token = block.strip()
        if len(token) < 2:
            continue
        tokens.add(token)
        for size in (2, 3):
            if len(token) >= size:
                for index in range(0, len(token) - size + 1):
                    tokens.add(token[index : index + size])
    return tokens



def _iter_boundary_support_texts(source: dict[str, str]) -> list[str]:
    texts: list[str] = []
    for field in ("text", "excerpt"):
        value = str(source.get(field) or "").strip()
        if value:
            texts.append(value)
    return texts



def _iter_targeted_answer_candidates(source: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    for text in _iter_boundary_support_texts(source):
        for line in text.splitlines():
            normalized = line.strip()
            if normalized:
                candidates.append(normalized)
    return candidates



def _answer_is_refusal_like(answer_text: str) -> bool:
    lowered = str(answer_text or "").lower()
    return "no confirmable information" in lowered or "无法根据当前知识库确认" in answer_text



def _normalize_expanded_answer(candidate: str) -> str:
    cleaned = str(candidate or "").strip().strip("\"'“”‘’()[]{}<> ")
    cleaned = cleaned.lstrip("：:,，;； ")
    if not cleaned:
        return ""
    if cleaned[-1] not in "。！？.!?":
        cleaned += "。" if _CJK_TOKEN_RE.search(cleaned) else "."
    return cleaned



def _build_hooks() -> chat_composite_answers.CompositeAnswerHooks:
    return chat_composite_answers.CompositeAnswerHooks(
        tokenize_text=_tokenize_text,
        iter_boundary_support_texts=_iter_boundary_support_texts,
        iter_targeted_answer_candidates=_iter_targeted_answer_candidates,
        question_requests_boundary_answer=chat_question_intents.question_requests_boundary_answer,
        question_requests_multi_fact_merge=chat_question_intents.question_requests_multi_fact_merge,
        question_requests_summary_answer=chat_question_intents.question_requests_summary_answer,
        answer_is_refusal_like=_answer_is_refusal_like,
        normalize_expanded_answer=_normalize_expanded_answer,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        time_value_re=_TIME_VALUE_RE,
    )



def test_maybe_merge_source_facts_from_sources_combines_approval_and_preview_sentences():
    hooks = _build_hooks()
    sources = [
        {
            "file": "cutover.md",
            "text": "The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence.",
        },
        {
            "file": "preview-board.png",
            "text": "Evidence preview checklist\nEvery evidence preview must include doc_id and preview_locator",
        },
    ]

    answer = chat_composite_answers.maybe_merge_source_facts_from_sources(
        "In one answer, tell me who gives the final rollback approval and what every evidence preview should include.",
        "Every evidence preview must include doc_id and preview_locator.",
        sources,
        hooks=hooks,
    )

    assert "platform duty lead" in answer
    assert "final rollback approval" in answer
    assert "doc_id" in answer
    assert "preview_locator" in answer
    assert "checklist" not in answer.lower()



def test_maybe_merge_source_facts_from_sources_combines_boundary_and_preview_sentences():
    hooks = _build_hooks()
    sources = [
        {
            "file": "boundary.md",
            "text": "Knowledge Base is the authorization boundary. Folder remains organization only.",
        },
        {
            "file": "preview-board.png",
            "text": "Evidence preview checklist. Every evidence preview must include doc_id and preview_locator.",
        },
    ]

    answer = chat_composite_answers.maybe_merge_source_facts_from_sources(
        "In one answer, compare the escalation board image and the evidence preview board: what remains the authorization boundary, and does the preview board explicitly require doc_id and preview_locator?",
        "Evidence preview checklist.",
        sources,
        hooks=hooks,
    )

    assert "knowledge base" in answer.lower()
    assert "authorization boundary" in answer.lower()
    assert "doc_id" in answer
    assert "preview_locator" in answer



def test_maybe_merge_source_facts_from_sources_keeps_original_for_single_requested_fact():
    hooks = _build_hooks()
    sources = [
        {
            "file": "cutover.md",
            "text": "The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence.",
        },
        {
            "file": "preview-board.png",
            "text": "Every evidence preview must include doc_id and preview_locator.",
        },
    ]

    answer = chat_composite_answers.maybe_merge_source_facts_from_sources(
        "In one answer, tell me who gives the final rollback approval.",
        "The model already answered the approver completely.",
        sources,
        hooks=hooks,
    )

    assert answer == "The model already answered the approver completely."



def test_maybe_answer_summary_bundle_from_sources_appends_boundary_time_and_refusal_segments():
    hooks = _build_hooks()
    question = (
        "In one sentence, summarize the handover using the authorization boundary, "
        "within 10 minutes SLA, and No confirmable information anchor."
    )
    sources = [
        {"file": "boundary.md", "text": "Knowledge Base remains the authorization boundary."},
        {"file": "sla.md", "text": "Sev1 cutover issues must be escalated to the commander within 10 minutes."},
        {"file": "contract.md", "text": "No confirmable information is available in the current knowledge base."},
    ]

    answer = chat_composite_answers.maybe_answer_summary_bundle_from_sources(
        question,
        "Keep the handover aligned",
        sources,
        hooks=hooks,
    )

    segments = answer.splitlines()
    assert segments[0] == "Keep the handover aligned."
    assert "Knowledge Base remains the authorization boundary." in segments
    assert "Sev1 cutover issues must be escalated to the commander within 10 minutes." in segments
    assert "No confirmable information is available in the current knowledge base." in segments



def test_maybe_answer_summary_bundle_from_sources_keeps_original_when_signals_are_insufficient():
    hooks = _build_hooks()
    sources = [{"file": "boundary.md", "text": "Knowledge Base remains the authorization boundary."}]

    answer = chat_composite_answers.maybe_answer_summary_bundle_from_sources(
        "In one sentence, summarize the authorization boundary rule.",
        "Keep the answer short.",
        sources,
        hooks=hooks,
    )

    assert answer == "Keep the answer short."



def test_maybe_answer_summary_bundle_from_sources_prefers_clean_single_signal_sentences():
    hooks = _build_hooks()
    question = (
        "In one sentence, summarize the authorization boundary, within 10 minutes SLA, "
        "and No confirmable information anchor for the release handover."
    )
    sources = [
        {
            "file": "mixed.md",
            "text": (
                "Knowledge Base remains the authorization boundary, Sev1 cutover issues must be escalated "
                "to the commander within 10 minutes, and No confirmable information is available in the "
                "current knowledge base."
            ),
        },
        {"file": "boundary.md", "text": "Knowledge Base remains the authorization boundary."},
        {"file": "sla.md", "text": "Sev1 cutover issues must be escalated to the commander within 10 minutes."},
        {"file": "contract.md", "text": "No confirmable information is available in the current knowledge base."},
    ]

    answer = chat_composite_answers.maybe_answer_summary_bundle_from_sources(
        question,
        "Keep the release handover aligned",
        sources,
        hooks=hooks,
    )

    assert "Keep the release handover aligned." in answer
    assert "Knowledge Base remains the authorization boundary." in answer
    assert "Sev1 cutover issues must be escalated to the commander within 10 minutes." in answer
    assert "No confirmable information is available in the current knowledge base." in answer
    assert "Knowledge Base remains the authorization boundary, Sev1 cutover issues" not in answer
