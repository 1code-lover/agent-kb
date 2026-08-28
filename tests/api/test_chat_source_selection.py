"""chat_source_selection 的独立契约测试。"""

from __future__ import annotations

import re

from api.services import chat_source_selection


_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def _tokenize_text(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or "")) if token.strip()}



def _build_source_text_blob(source: dict[str, str]) -> str:
    return "\n".join(
        part
        for part in (
            str(source.get("file") or "").strip(),
            str(source.get("title") or "").strip(),
            str(source.get("text") or "").strip(),
            str(source.get("excerpt") or "").strip(),
        )
        if part
    )



def _normalize_answer(text: str) -> str:
    return str(text or "").strip()



def _dedupe_sources_by_file(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in sources:
        file_name = str(source.get("file") or source.get("title") or "").strip()
        if file_name and file_name in seen:
            continue
        if file_name:
            seen.add(file_name)
        deduped.append(source)
    return deduped



def _source_supports_question(question: str, source: dict[str, str]) -> bool:
    stop_tokens = {
        "the",
        "what",
        "should",
        "do",
        "if",
        "is",
        "in",
        "knowledge",
        "base",
        "active",
        "assistant",
        "confirmable",
        "evidence",
        "missing",
        "current",
    }
    question_tokens = {token for token in _tokenize_text(question) if token not in stop_tokens}
    source_tokens = {token for token in _tokenize_text(_build_source_text_blob(source)) if token not in stop_tokens}
    return bool(question_tokens & source_tokens)



def _extract_answer_support_segments(answer_text: str, _sources: list[dict[str, str]]) -> list[dict[str, str | None]]:
    segments: list[dict[str, str | None]] = []
    for raw_line in str(answer_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        mentioned_file: str | None = None
        segment_text = line
        if ">>" in line:
            maybe_file, maybe_text = [part.strip() for part in line.split(">>", 1)]
            if maybe_file and maybe_text:
                mentioned_file = maybe_file
                segment_text = maybe_text
        segments.append({"text": segment_text, "mentioned_file": mentioned_file})
    return segments



def _build_hooks() -> chat_source_selection.SourceSelectionHooks:
    return chat_source_selection.SourceSelectionHooks(
        build_source_text_blob=_build_source_text_blob,
        tokenize_text=_tokenize_text,
        normalize_expanded_answer=_normalize_answer,
        dedupe_sources_by_file=_dedupe_sources_by_file,
        answer_is_refusal_like=lambda answer: "no confirmable information" in str(answer or "").lower(),
        question_requests_summary_answer=lambda question: "summary" in str(question or "").lower(),
        question_prefers_cross_source_fact_assembly=lambda question: "across" in str(question or "").lower(),
        question_requests_targeted_fact_answer=lambda question: "who" in str(question or "").lower(),
        question_requests_boundary_answer=lambda question: "boundary" in str(question or "").lower(),
        question_requests_negative_contract=lambda question: any(
            marker in str(question or "").lower() for marker in ("confirmable", "fabricate", "外部记忆", "可确认")
        ),
        source_supports_question=_source_supports_question,
        extract_answer_support_segments=_extract_answer_support_segments,
        refusal_markers=("no confirmable information", "must not fabricate", "active knowledge base"),
        refusal_source_markers=(
            "no confirmable information",
            "must not fabricate",
            "active knowledge base",
            "当前知识库中没有可确认的信息",
            "不得从外部记忆编造答案",
        ),
    )



def test_minimize_sources_for_answer_prefers_explicit_mentioned_source_order():
    hooks = _build_hooks()
    sources = [
        {"file": "alpha.md", "text": "alpha handbook deadline 22:30"},
        {"file": "beta.md", "text": "beta sla escalation interval 15 minutes"},
        {"file": "gamma.md", "text": "gamma noise note"},
    ]

    selected = chat_source_selection.minimize_sources_for_answer(
        "Across the rollout summary, what matters?",
        "beta.md >> escalation interval 15 minutes\nalpha.md >> deadline 22:30",
        sources,
        hooks=hooks,
    )

    assert [source["file"] for source in selected] == ["beta.md", "alpha.md"]



def test_minimize_sources_for_answer_prefers_best_single_covering_source():
    hooks = _build_hooks()
    sources = [
        {
            "file": "full.md",
            "text": "Checklist deadline 22:30 Beijing time. Escalation interval 15 minutes.",
        },
        {"file": "deadline.md", "text": "Checklist deadline 22:30 Beijing time."},
        {"file": "escalation.md", "text": "Escalation interval 15 minutes."},
    ]

    selected = chat_source_selection.minimize_sources_for_answer(
        "Across the payroll summary, when is the deadline and what is the escalation interval?",
        "Checklist deadline 22:30 Beijing time\nEscalation interval 15 minutes",
        sources,
        hooks=hooks,
    )

    assert [source["file"] for source in selected] == ["full.md"]



def test_minimize_sources_for_answer_greedily_selects_minimal_cover_set():
    hooks = _build_hooks()
    sources = [
        {"file": "deadline.md", "text": "Checklist deadline 22:30 Beijing time."},
        {"file": "escalation.md", "text": "Escalation interval 15 minutes for P1 incidents."},
        {"file": "extra.md", "text": "Checklist owner is Li Qing."},
    ]

    selected = chat_source_selection.minimize_sources_for_answer(
        "Across the payroll summary, when is the deadline and what is the escalation interval?",
        "Checklist deadline 22:30 Beijing time\nEscalation interval 15 minutes",
        sources,
        hooks=hooks,
    )

    assert [source["file"] for source in selected] == ["deadline.md", "escalation.md"]



def test_minimize_sources_for_answer_falls_back_when_not_all_segments_are_covered():
    hooks = _build_hooks()
    sources = [
        {"file": "deadline.md", "text": "Checklist deadline 22:30 Beijing time."},
        {"file": "extra.md", "text": "Checklist owner is Li Qing."},
    ]

    selected = chat_source_selection.minimize_sources_for_answer(
        "Across the payroll summary, when is the deadline and what is the escalation interval?",
        "Checklist deadline 22:30 Beijing time\nEscalation interval 15 minutes",
        sources,
        hooks=hooks,
    )

    assert [source["file"] for source in selected] == ["deadline.md", "extra.md"]



def test_prune_sources_for_refusal_keeps_only_grounded_refusal_sources():
    hooks = _build_hooks()
    sources = [
        {
            "file": "policy.md",
            "text": "Payroll active knowledge base policy. No confirmable information is available in the current knowledge base. The assistant must not fabricate.",
        },
        {
            "file": "noise.md",
            "text": "Travel policy. No confirmable information is available in the current knowledge base.",
        },
        {
            "file": "topic-only.md",
            "text": "Payroll cutover checklist deadline 22:30 Beijing time.",
        },
    ]

    selected = chat_source_selection.prune_sources_for_refusal(
        "In the payroll active knowledge base, what should the assistant do if confirmable evidence is missing?",
        "No confirmable information is available in the current knowledge base. The assistant must not fabricate.",
        sources,
        hooks=hooks,
    )

    assert [source["file"] for source in selected] == ["policy.md"]



def test_prune_sources_for_refusal_falls_back_to_cross_language_contract_source_for_negative_contract_question():
    hooks = _build_hooks()
    sources = [
        {
            "file": "grain-policy-zh.md",
            "text": "当前知识库中没有可确认的信息。助手不得从外部记忆编造答案。",
        },
        {
            "file": "noise.md",
            "text": "Travel checklist deadline 22:30 Beijing time.",
        },
    ]

    selected = chat_source_selection.prune_sources_for_refusal(
        "If confirmable evidence is missing in the current knowledge base, what should the assistant say and what must it avoid?",
        "No confirmable information is available in the current knowledge base. The assistant must not fabricate.",
        sources,
        hooks=hooks,
    )

    assert [source["file"] for source in selected] == ["grain-policy-zh.md"]
