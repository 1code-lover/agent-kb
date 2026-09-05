"""聊天问答来源裁剪与最小支撑集选择。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

Source = dict[str, Any]
SourceList = list[Source]
QuestionPredicate = Callable[[str], bool]
QuestionSourcePredicate = Callable[[str, Source], bool]
AnswerPredicate = Callable[[str], bool]
TextTokenizer = Callable[[str], set[str]]
SourceTextBuilder = Callable[[Source], str]
AnswerNormalizer = Callable[[str], str]
SourceDeduper = Callable[[SourceList], SourceList]
AnswerSegmentExtractor = Callable[[str, SourceList], list[dict[str, str | None]]]


@dataclass(frozen=True)
class SourceSelectionHooks:
    """收敛 chat_service 中来源裁剪/最小化所需的依赖与题型判别器。"""

    build_source_text_blob: SourceTextBuilder
    tokenize_text: TextTokenizer
    normalize_expanded_answer: AnswerNormalizer
    dedupe_sources_by_file: SourceDeduper
    answer_is_refusal_like: AnswerPredicate
    question_requests_summary_answer: QuestionPredicate
    question_prefers_cross_source_fact_assembly: QuestionPredicate
    question_requests_targeted_fact_answer: QuestionPredicate
    question_requests_boundary_answer: QuestionPredicate
    question_requests_negative_contract: QuestionPredicate
    source_supports_question: QuestionSourcePredicate
    extract_answer_support_segments: AnswerSegmentExtractor
    refusal_markers: tuple[str, ...]
    refusal_source_markers: tuple[str, ...]


def source_supports_refusal_answer(answer_text: str, source: Source, *, hooks: SourceSelectionHooks) -> bool:
    """判断来源是否直接支撑“缺证据/需拒答”的结论。"""
    source_blob = hooks.build_source_text_blob(source).lower()
    if not source_blob:
        return False
    if any(marker in source_blob for marker in hooks.refusal_source_markers):
        return True

    answer_blob = str(answer_text or "").lower()
    if not answer_blob:
        return False
    answer_markers = [marker for marker in hooks.refusal_markers if marker in answer_blob]
    return bool(answer_markers) and any(marker in source_blob for marker in answer_markers)


def prune_sources_for_refusal(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    hooks: SourceSelectionHooks,
) -> SourceList:
    """拒答时优先保留同时支撑问题主题和拒答结论的来源；negative-contract 题允许跨语言兜底。"""
    refusal_backed = [source for source in sources if source_supports_refusal_answer(answer_text, source, hooks=hooks)]
    if not refusal_backed:
        return []

    grounded = [source for source in refusal_backed if hooks.source_supports_question(question, source)]
    if grounded:
        return grounded

    if hooks.question_requests_negative_contract(question):
        return hooks.dedupe_sources_by_file(refusal_backed)

    return []


def source_supports_answer_segment(source: Source, segment: str, *, hooks: SourceSelectionHooks) -> bool:
    """判断单个 source 是否足以支撑 answer 中的某个事实片段。"""
    source_blob = hooks.build_source_text_blob(source)
    if not source_blob:
        return False

    normalized_segment = hooks.normalize_expanded_answer(segment)
    if not normalized_segment:
        return False

    source_blob_lower = source_blob.lower()
    normalized_lower = normalized_segment.lower()
    if normalized_lower in source_blob_lower:
        return True

    segment_tokens = hooks.tokenize_text(normalized_segment)
    source_tokens = hooks.tokenize_text(source_blob)
    if not segment_tokens or not source_tokens:
        return False

    overlap = segment_tokens & source_tokens
    if segment_tokens.issubset(source_tokens):
        return True

    focus_tokens = {token for token in segment_tokens if "_" in token or "-" in token or len(token) >= 12}
    if focus_tokens and not focus_tokens.issubset(source_tokens):
        return False

    return len(overlap) >= max(2, int(len(segment_tokens) * 0.7))


def score_source_selection(
    question: str,
    answer_text: str,
    source: Source,
    supported_count: int,
    *,
    mentioned: bool,
    hooks: SourceSelectionHooks,
) -> tuple[int, ...]:
    """为来源最小化选择“最贴题、最贴近答案”的 source。"""
    source_blob = hooks.build_source_text_blob(source)
    question_overlap = len(hooks.tokenize_text(question) & hooks.tokenize_text(source_blob))
    answer_overlap = len(hooks.tokenize_text(answer_text) & hooks.tokenize_text(source_blob))
    return (
        int(mentioned),
        supported_count,
        question_overlap,
        answer_overlap,
        -len(source_blob),
    )


@dataclass(frozen=True)
class SourceCoverage:
    """记录单个 source 对 answer segments 的覆盖情况。"""

    source: Source
    covered_indexes: frozenset[int]
    file_name: str



def _should_minimize_sources(question: str, answer_text: str, sources: SourceList, *, hooks: SourceSelectionHooks) -> bool:
    """冻结来源最小化是否应启用，避免主流程堆叠条件分支。"""
    if len(sources) <= 1 or not str(answer_text or "").strip() or hooks.answer_is_refusal_like(answer_text):
        return False
    return any(
        (
            hooks.question_requests_summary_answer(question),
            hooks.question_prefers_cross_source_fact_assembly(question),
            hooks.question_requests_targeted_fact_answer(question),
            hooks.question_requests_boundary_answer(question),
        )
    )



def _collect_mentioned_sources(segments: list[dict[str, str | None]], sources: SourceList, *, hooks: SourceSelectionHooks) -> SourceList | None:
    """若 answer 已显式点名来源，则优先按提及顺序收缩来源集合。"""
    mentioned_files_in_order: list[str] = []
    seen_mentioned_files: set[str] = set()
    for segment in segments:
        mentioned_file = str(segment.get("mentioned_file") or "").strip()
        if not mentioned_file or mentioned_file in seen_mentioned_files:
            continue
        seen_mentioned_files.add(mentioned_file)
        mentioned_files_in_order.append(mentioned_file)

    if not mentioned_files_in_order:
        return None

    source_by_file = {str(source.get("file") or source.get("title") or "").strip(): source for source in sources}
    mentioned_sources = [source_by_file[file_name] for file_name in mentioned_files_in_order if file_name in source_by_file]
    if not mentioned_sources:
        return None
    return hooks.dedupe_sources_by_file(mentioned_sources)



def _build_source_support_map(
    segments: list[dict[str, str | None]],
    sources: SourceList,
    *,
    hooks: SourceSelectionHooks,
) -> list[SourceCoverage]:
    """预先计算每个 source 能覆盖哪些 answer segment。"""
    support_map: list[SourceCoverage] = []
    for source in sources:
        file_name = str(source.get("file") or source.get("title") or "").strip()
        covered_indexes: set[int] = set()
        for index, segment in enumerate(segments):
            mentioned_file = str(segment.get("mentioned_file") or "").strip()
            if mentioned_file and mentioned_file != file_name:
                continue
            if source_supports_answer_segment(source, str(segment.get("text") or ""), hooks=hooks):
                covered_indexes.add(index)
        support_map.append(SourceCoverage(source=source, covered_indexes=frozenset(covered_indexes), file_name=file_name))
    return support_map



def _select_single_covering_source(
    question: str,
    answer_text: str,
    support_map: list[SourceCoverage],
    all_segment_indexes: frozenset[int],
    *,
    hooks: SourceSelectionHooks,
) -> Source | None:
    """若单个 source 已覆盖全部 segment，则直接返回最优单来源。"""
    single_source_candidates = [item for item in support_map if item.covered_indexes == all_segment_indexes]
    if not single_source_candidates:
        return None

    return max(
        single_source_candidates,
        key=lambda item: score_source_selection(
            question,
            answer_text,
            item.source,
            len(item.covered_indexes),
            mentioned=False,
            hooks=hooks,
        ),
    ).source



def _select_minimal_covering_sources(
    question: str,
    answer_text: str,
    support_map: list[SourceCoverage],
    *,
    segment_count: int,
    hooks: SourceSelectionHooks,
) -> SourceList:
    """用 greedy 方式挑出覆盖全部 segment 的最小必要来源集合。"""
    selected: SourceList = []
    covered_indexes: set[int] = set()
    remaining = list(support_map)

    while len(covered_indexes) < segment_count:
        best_item: SourceCoverage | None = None
        best_gain: set[int] = set()
        for candidate in remaining:
            gain = set(candidate.covered_indexes) - covered_indexes
            if not gain:
                continue
            if best_item is None:
                best_item = candidate
                best_gain = gain
                continue

            candidate_score = (len(gain), -min(gain)) + score_source_selection(
                question,
                answer_text,
                candidate.source,
                len(candidate.covered_indexes),
                mentioned=False,
                hooks=hooks,
            )
            best_score = (len(best_gain), -min(best_gain)) + score_source_selection(
                question,
                answer_text,
                best_item.source,
                len(best_item.covered_indexes),
                mentioned=False,
                hooks=hooks,
            )
            if candidate_score > best_score:
                best_item = candidate
                best_gain = gain

        if best_item is None:
            break
        selected.append(best_item.source)
        covered_indexes |= set(best_item.covered_indexes)
        remaining = [candidate for candidate in remaining if candidate.source is not best_item.source]

    if len(covered_indexes) == segment_count and selected:
        return hooks.dedupe_sources_by_file(selected)
    return []



def minimize_sources_for_answer(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    hooks: SourceSelectionHooks,
) -> SourceList:
    """在不丢失 answer 支撑关系的前提下，尽量缩到最小必要来源集合。"""
    deduped_sources = hooks.dedupe_sources_by_file(sources)
    if not _should_minimize_sources(question, answer_text, deduped_sources, hooks=hooks):
        return deduped_sources

    segments = hooks.extract_answer_support_segments(answer_text, deduped_sources)
    if not segments:
        return deduped_sources

    mentioned_sources = _collect_mentioned_sources(segments, deduped_sources, hooks=hooks)
    if mentioned_sources:
        return mentioned_sources

    support_map = _build_source_support_map(segments, deduped_sources, hooks=hooks)
    all_segment_indexes = frozenset(range(len(segments)))
    single_source = _select_single_covering_source(
        question,
        answer_text,
        support_map,
        all_segment_indexes,
        hooks=hooks,
    )
    if single_source is not None:
        return [single_source]

    selected = _select_minimal_covering_sources(
        question,
        answer_text,
        support_map,
        segment_count=len(segments),
        hooks=hooks,
    )
    return selected or deduped_sources

