"""chat_negative_contract_answers 的独立契约测试。"""

from __future__ import annotations

from api.services import chat_negative_contract_answers



def _normalize_expanded_answer(text: str) -> str:
    return str(text or "").strip()



def _build_hooks() -> chat_negative_contract_answers.NegativeContractHooks:
    return chat_negative_contract_answers.NegativeContractHooks(
        question_requests_negative_contract=lambda question: (
            "knowledge base" in str(question or "").lower()
            or "evidence is missing" in str(question or "").lower()
            or "当前知识库" in str(question or "")
            or "可确认" in str(question or "")
        ),
        iter_targeted_answer_candidates=lambda source: [line.strip() for line in str(source.get("text") or "").splitlines() if line.strip()],
        normalize_expanded_answer=_normalize_expanded_answer,
    )



def test_extract_negative_contract_labels_treats_current_knowledge_base_refusal_as_scope_anchor():
    labels = chat_negative_contract_answers.extract_negative_contract_labels(
        "No confirmable information is available in the current knowledge base."
    )

    assert labels == {"refusal", "scope"}



def test_collect_negative_contract_segments_from_answer_preserves_refusal_scope_and_memory_lines():
    segments = chat_negative_contract_answers.collect_negative_contract_segments_from_answer(
        "No confirmable information is available in the current knowledge base.\n"
        "Keep the answer concise.\n"
        "The assistant must not fabricate from outside memory.\n"
        "No confirmable information is available in the current knowledge base.",
        normalize_expanded_answer=_normalize_expanded_answer,
    )

    assert segments == [
        "No confirmable information is available in the current knowledge base.",
        "The assistant must not fabricate from outside memory.",
    ]



def test_best_single_source_negative_contract_answer_allows_refusal_line_to_cover_scope_when_current_kb_is_explicit():
    hooks = _build_hooks()
    source = {
        "file": "ocr-refusal-board.png",
        "text": (
            "No confirmable information is available in the current knowledge base.\n"
            "The assistant must not fabricate from outside memory."
        ),
    }

    result = chat_negative_contract_answers.best_single_source_negative_contract_answer(
        "If evidence is missing in the current knowledge base, what should the assistant say and what must it avoid?",
        [source],
        hooks=hooks,
    )

    assert result is not None
    answer, used_sources = result
    assert answer.splitlines() == [
        "No confirmable information is available in the current knowledge base.",
        "The assistant must not fabricate from outside memory.",
    ]
    assert used_sources == [source]



def test_best_negative_contract_segment_prefers_refusal_anchor_with_scope_context():
    hooks = _build_hooks()
    sources = [
        {
            "file": "weak.txt",
            "text": "No confirmable information is available.",
        },
        {
            "file": "strong.txt",
            "text": "No confirmable information is available in the current knowledge base.",
        },
    ]

    result = chat_negative_contract_answers.best_negative_contract_segment(
        "If evidence is missing in the current knowledge base, what should the assistant say?",
        sources,
        hooks=hooks,
    )

    assert result == (
        "No confirmable information is available in the current knowledge base.",
        sources[1],
    )


def test_extract_negative_contract_labels_supports_chinese_refusal_scope_and_memory_markers():
    labels = chat_negative_contract_answers.extract_negative_contract_labels(
        "当前知识库中没有可确认的信息，助手不得从外部记忆编造答案。"
    )

    assert labels == {"refusal", "scope", "memory"}


def test_best_single_source_negative_contract_answer_supports_chinese_scope_and_memory_contract():
    hooks = _build_hooks()
    source = {
        "file": "zh-refusal.md",
        "text": (
            "当前知识库中没有可确认的信息。\n"
            "请留在当前知识库范围内。\n"
            "助手不得从外部记忆编造答案。"
        ),
    }

    result = chat_negative_contract_answers.best_single_source_negative_contract_answer(
        "如果当前知识库里没有可确认信息，助手应该怎么回答，并且不能编造什么？",
        [source],
        hooks=hooks,
    )

    assert result is not None
    answer, used_sources = result
    assert answer.splitlines() == [
        "当前知识库中没有可确认的信息。",
        "请留在当前知识库范围内。",
        "助手不得从外部记忆编造答案。",
    ]
    assert used_sources == [source]
