"""负向契约答案拼装与锚点筛选。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from api.services.chat_contract_markers import (
    MEMORY_MARKERS,
    NEGATIVE_CONTRACT_SEGMENT_ORDER,
    extract_negative_contract_labels as _extract_negative_contract_labels,
)

QuestionPredicate = Callable[[str], bool]
IterTargetedAnswerCandidates = Callable[[dict[str, Any]], list[str]]
NormalizeExpandedAnswer = Callable[[str], str]


@dataclass(frozen=True)
class NegativeContractHooks:
    """承载负向契约选择逻辑需要的最小依赖。"""

    question_requests_negative_contract: QuestionPredicate
    iter_targeted_answer_candidates: IterTargetedAnswerCandidates
    normalize_expanded_answer: NormalizeExpandedAnswer



def _normalize_segment(text: str, *, normalize_expanded_answer: NormalizeExpandedAnswer) -> str:
    return normalize_expanded_answer(str(text or ""))



def extract_negative_contract_labels(text: str) -> set[str]:
    """识别一条文本承担了哪类负向契约角色。"""
    return _extract_negative_contract_labels(text)



def collect_negative_contract_segments_from_answer(
    answer_text: str,
    *,
    normalize_expanded_answer: NormalizeExpandedAnswer,
) -> list[str]:
    """从已有 answer_text 中抽取可复用的负向契约片段。"""
    segments: list[str] = []
    seen: set[str] = set()
    for raw_line in str(answer_text or "").splitlines():
        normalized = _normalize_segment(raw_line, normalize_expanded_answer=normalize_expanded_answer)
        if not normalized or normalized in seen:
            continue
        if not extract_negative_contract_labels(normalized):
            continue
        seen.add(normalized)
        segments.append(normalized)
    return segments



def _candidate_score(candidate: str, *, label: str) -> tuple[int, ...]:
    lowered = candidate.lower()
    has_refusal = "no confirmable information" in lowered
    has_active_pdf_scope = "active pdf knowledge base" in lowered
    has_active_scope = "active knowledge base" in lowered and not has_active_pdf_scope
    has_current_scope = "current knowledge base" in lowered
    has_memory = any(marker in lowered for marker in MEMORY_MARKERS)
    has_stay_inside = any(marker in lowered for marker in ("stay inside", "inside the"))
    has_boundary = "authorization boundary" in lowered

    if label == "scope":
        return (
            int(has_active_pdf_scope),
            int(has_active_scope or has_stay_inside),
            int(has_current_scope),
            int(has_boundary),
            -int(has_refusal),
            -len(candidate),
        )
    if label == "memory":
        return (
            int(has_memory),
            int("outside memory" in lowered),
            int(has_active_pdf_scope or has_active_scope or has_current_scope),
            -len(candidate),
        )
    return (
        int(has_refusal),
        int(has_active_pdf_scope),
        int(has_active_scope or has_current_scope),
        int(has_memory),
        -len(candidate),
    )



def best_single_source_negative_contract_answer(
    question: str,
    sources: list[dict[str, Any]],
    *,
    hooks: NegativeContractHooks,
) -> tuple[str, list[dict[str, Any]]] | None:
    """若同一 source 已覆盖 refusal/scope/no-fabrication，则直接返回最小答案。"""
    if not hooks.question_requests_negative_contract(question):
        return None

    for source in sources:
        best_segments: dict[str, tuple[tuple[int, ...], str]] = {}
        for candidate in hooks.iter_targeted_answer_candidates(source):
            normalized = _normalize_segment(candidate, normalize_expanded_answer=hooks.normalize_expanded_answer)
            if not normalized:
                continue
            for label in extract_negative_contract_labels(normalized):
                score = _candidate_score(normalized, label=label)
                current = best_segments.get(label)
                if current is None or score > current[0]:
                    best_segments[label] = (score, normalized)

        if not all(label in best_segments for label in NEGATIVE_CONTRACT_SEGMENT_ORDER):
            continue

        selected: list[str] = []
        for label in NEGATIVE_CONTRACT_SEGMENT_ORDER:
            segment = best_segments[label][1]
            if segment not in selected:
                selected.append(segment)
        if selected:
            return "\n".join(selected), [source]
    return None



def best_negative_contract_segment(
    question: str,
    sources: list[dict[str, Any]],
    *,
    hooks: NegativeContractHooks,
) -> tuple[str, dict[str, Any]] | None:
    """为 refusal / negative-contract 问题补回 No confirmable information 锚点。"""
    if not hooks.question_requests_negative_contract(question):
        return None

    best: tuple[tuple[int, ...], str, dict[str, Any]] | None = None
    for source in sources:
        for candidate in hooks.iter_targeted_answer_candidates(source):
            normalized = _normalize_segment(candidate, normalize_expanded_answer=hooks.normalize_expanded_answer)
            if not normalized or "refusal" not in extract_negative_contract_labels(normalized):
                continue
            score = _candidate_score(normalized, label="refusal")
            if best is None or score > best[0]:
                best = (score, normalized, source)
    if best is None:
        return None
    return best[1], best[2]
