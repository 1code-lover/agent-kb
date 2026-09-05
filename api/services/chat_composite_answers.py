"""聊天问答中的多事实合并与 summary bundle 组装逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from api.services import chat_source_answers

SourceList = list[dict[str, Any]]
TokenizeText = Callable[[str], set[str]]
SourceTextIterator = Callable[[dict[str, Any]], list[str]]
QuestionPredicate = Callable[[str], bool]
AnswerPredicate = Callable[[str], bool]
NormalizeAnswer = Callable[[str], str]

_APPROVAL_FACT_MARKERS = ("approval", "approv", "rollback", "批准", "回滚")
_APPROVAL_SENTENCE_MARKERS = ("approval", "approv", "final rollback", "platform duty lead", "最终回滚批准", "回滚批准")
_PREVIEW_FACT_MARKERS = ("preview", "doc_id", "preview_locator", "预览")
_TIME_SIGNAL_MARKERS = ("minutes", "minute", "deadline", "within")
_SUMMARY_TIME_SENTENCE_MARKERS = ("minutes", "minute", "within", "before")


@dataclass(frozen=True)
class CompositeAnswerHooks:
    """承载 multi-fact merge / summary bundle 所需依赖，降低 chat_service 耦合。"""

    tokenize_text: TokenizeText
    iter_boundary_support_texts: SourceTextIterator
    iter_targeted_answer_candidates: SourceTextIterator
    question_requests_boundary_answer: QuestionPredicate
    question_requests_multi_fact_merge: QuestionPredicate
    question_requests_summary_answer: QuestionPredicate
    answer_is_refusal_like: AnswerPredicate
    normalize_expanded_answer: NormalizeAnswer
    sentence_split_re: re.Pattern[str]
    time_value_re: re.Pattern[str]


def maybe_merge_source_facts_from_sources(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    hooks: CompositeAnswerHooks,
) -> str:
    """当问题明确要求一个回答里包含多个 source 事实时，按子问题选择最完整的 source 句。"""
    if not sources or hooks.answer_is_refusal_like(answer_text):
        return answer_text

    if not hooks.question_requests_multi_fact_merge(question):
        return answer_text

    question_lower = str(question or "").lower()
    wants_approval = any(marker in question_lower for marker in _APPROVAL_FACT_MARKERS)
    wants_boundary = hooks.question_requests_boundary_answer(question)
    wants_preview = any(marker in question_lower for marker in _PREVIEW_FACT_MARKERS)
    requested_facts = {
        name
        for name, requested in (
            ("approval", wants_approval),
            ("boundary", wants_boundary),
            ("preview", wants_preview),
        )
        if requested
    }
    if len(requested_facts) < 2:
        return answer_text

    question_tokens = hooks.tokenize_text(question)
    best_by_fact: dict[str, tuple[tuple[int, ...], str]] = {}

    for source in sources:
        for support_text in hooks.iter_boundary_support_texts(source):
            sentences = [segment.strip() for segment in hooks.sentence_split_re.split(support_text) if segment.strip()]
            for sentence in sentences:
                sentence_lower = sentence.lower()
                sentence_tokens = hooks.tokenize_text(sentence)
                overlap = len(question_tokens & sentence_tokens)
                if question_tokens and overlap <= 0:
                    continue
                normalized = hooks.normalize_expanded_answer(sentence)
                if not normalized or len(normalized) > 260:
                    continue

                is_approval = any(marker in sentence_lower or marker in sentence for marker in _APPROVAL_SENTENCE_MARKERS)
                is_boundary = any(
                    marker in sentence_lower or marker in sentence
                    for marker in chat_source_answers.BOUNDARY_RELATION_HINTS
                ) and any(
                    marker in sentence_lower or marker in sentence
                    for marker in chat_source_answers.BOUNDARY_SENTENCE_HINTS
                )
                is_preview = any(marker in sentence_lower or marker in sentence for marker in _PREVIEW_FACT_MARKERS)
                if not is_approval and not is_boundary and not is_preview:
                    continue

                if is_approval:
                    score = (
                        int("platform duty lead" in sentence_lower or "最终回滚批准" in sentence),
                        int("final rollback approval" in sentence_lower or "回滚批准" in sentence),
                        int(" gives " in f" {sentence_lower} " or "批准" in sentence),
                        overlap,
                    )
                    if "approval" not in best_by_fact or score > best_by_fact["approval"][0]:
                        best_by_fact["approval"] = (score, normalized)

                if is_boundary:
                    score = (
                        int("authorization boundary" in sentence_lower or "授权边界" in sentence),
                        int("knowledge base" in sentence_lower or "知识库" in sentence),
                        int("remains" in sentence_lower or "仍然" in sentence or "仍是" in sentence),
                        overlap,
                    )
                    if "boundary" not in best_by_fact or score > best_by_fact["boundary"][0]:
                        best_by_fact["boundary"] = (score, normalized)

                if is_preview:
                    score = (
                        int("doc_id" in sentence_lower) + int("preview_locator" in sentence_lower),
                        int("must include" in sentence_lower or "应包含" in sentence),
                        int("every evidence preview" in sentence_lower),
                        overlap,
                    )
                    if "preview" not in best_by_fact or score > best_by_fact["preview"][0]:
                        best_by_fact["preview"] = (score, normalized)

    selected: list[str] = []
    for fact_name in ("approval", "boundary", "preview"):
        if fact_name not in requested_facts or fact_name not in best_by_fact:
            continue
        candidate = best_by_fact[fact_name][1]
        if candidate not in selected:
            selected.append(candidate)

    return " ".join(selected) if len(selected) >= 2 else answer_text


def maybe_answer_summary_bundle_from_sources(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    hooks: CompositeAnswerHooks,
) -> str:
    """处理“一句话总结/summary”类问题，补齐时间、边界和拒答锚点。"""
    if not sources or hooks.answer_is_refusal_like(answer_text):
        return answer_text

    raw_question = str(question or "")
    lowered = raw_question.lower()
    if not hooks.question_requests_summary_answer(raw_question):
        return answer_text

    wants_time = bool(hooks.time_value_re.search(raw_question)) or any(marker in lowered for marker in _TIME_SIGNAL_MARKERS)
    wants_boundary = "authorization boundary" in lowered or "授权边界" in raw_question
    wants_refusal_anchor = "no confirmable information" in lowered or "No confirmable information" in raw_question
    if sum(int(flag) for flag in (wants_time, wants_boundary, wants_refusal_anchor)) < 2:
        return answer_text

    best_time: tuple[tuple[int, ...], str] | None = None
    best_boundary: tuple[tuple[int, ...], str] | None = None
    best_refusal: tuple[tuple[int, ...], str] | None = None
    question_tokens = hooks.tokenize_text(raw_question)

    for source in sources:
        for candidate in hooks.iter_targeted_answer_candidates(source):
            normalized = hooks.normalize_expanded_answer(candidate)
            if not normalized:
                continue

            candidate_lower = normalized.lower()
            token_overlap = len(question_tokens & hooks.tokenize_text(normalized))
            sentence_count = len([segment for segment in hooks.sentence_split_re.split(normalized) if segment.strip()])
            has_time_signal = bool(hooks.time_value_re.search(normalized)) or any(
                marker in candidate_lower for marker in _SUMMARY_TIME_SENTENCE_MARKERS
            )
            has_boundary_signal = "authorization boundary" in candidate_lower
            has_refusal_signal = "no confirmable information" in candidate_lower
            other_signal_penalty = int(has_time_signal) + int(has_boundary_signal) + int(has_refusal_signal)

            if wants_time and has_time_signal:
                score = (
                    int(bool(hooks.time_value_re.search(normalized))),
                    -max(other_signal_penalty - 1, 0),
                    -sentence_count,
                    token_overlap,
                    -len(normalized),
                )
                if best_time is None or score > best_time[0]:
                    best_time = (score, normalized)

            if wants_boundary and has_boundary_signal:
                score = (
                    int("knowledge base" in candidate_lower),
                    int("remains" in candidate_lower),
                    -max(other_signal_penalty - 1, 0),
                    -sentence_count,
                    token_overlap,
                    -len(normalized),
                )
                if best_boundary is None or score > best_boundary[0]:
                    best_boundary = (score, normalized)

            if wants_refusal_anchor and has_refusal_signal:
                score = (
                    int("current knowledge base" in candidate_lower or "active knowledge base" in candidate_lower),
                    -max(other_signal_penalty - 1, 0),
                    -sentence_count,
                    token_overlap,
                    -len(normalized),
                )
                if best_refusal is None or score > best_refusal[0]:
                    best_refusal = (score, normalized)

    supplemental_segments = [best[1] for best in (best_boundary, best_time, best_refusal) if best is not None]
    if len(supplemental_segments) < 2:
        return answer_text

    merged_segments: list[str] = []
    normalized_answer = hooks.normalize_expanded_answer(answer_text)
    if normalized_answer:
        merged_segments.append(normalized_answer)
    for segment in supplemental_segments:
        if segment not in merged_segments:
            merged_segments.append(segment)
    return "\n".join(merged_segments)
