"""聊天问答来源补检索与 source reconcile 逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

Source = dict[str, Any]
SourceList = list[Source]
QuestionPredicate = Callable[[str], bool]
QuestionSourcePredicate = Callable[[str, Source], bool]
SourceNormalizer = Callable[[Any], SourceList]
SourceDeduper = Callable[[SourceList], SourceList]
LiteralExtractor = Callable[[str], list[str]]
SourceTextBuilder = Callable[[Source], str]


@dataclass(frozen=True)
class SourceReconciliationHooks:
    """承载 query 后 source 补检索 / reconcile 所需依赖。"""

    normalize_sources: SourceNormalizer
    source_supports_question: QuestionSourcePredicate
    dedupe_sources_by_file: SourceDeduper
    extract_literal_question_terms: LiteralExtractor
    question_prefers_cross_source_fact_assembly: QuestionPredicate
    question_requests_targeted_fact_answer: QuestionPredicate
    build_source_text_blob: SourceTextBuilder


def source_matches_literal_terms(source: Source, literal_terms: list[str], *, hooks: SourceReconciliationHooks) -> bool:
    """判断来源是否命中了问题里显式出现的路径/字面 token。"""
    if not literal_terms:
        return False
    source_blob = hooks.build_source_text_blob(source).lower()
    return any(term.lower() in source_blob for term in literal_terms)


def collect_candidate_sources_for_question(
    engine: Any,
    question: str,
    *,
    hooks: SourceReconciliationHooks,
    top_k: int = 4,
) -> SourceList:
    """尽量从 query engine / retriever / manager 补拿候选来源，供精确答案重组使用。"""
    retrieved: list[Any] | tuple[Any, ...] | None = None

    retrieve = getattr(engine, 'retrieve', None)
    if callable(retrieve):
        try:
            retrieved = retrieve(question)
        except Exception:
            retrieved = None

    if retrieved is None:
        retriever = getattr(engine, '_retriever', None)
        retrieve = getattr(retriever, 'retrieve', None)
        if callable(retrieve):
            try:
                retrieved = retrieve(question)
            except Exception:
                retrieved = None

    if retrieved is None:
        manager = getattr(engine, 'manager', None)
        search = getattr(manager, 'search', None)
        if callable(search):
            try:
                retrieved = search(question, top_k=top_k)
            except TypeError:
                retrieved = search(question)
            except Exception:
                retrieved = None

    if not isinstance(retrieved, (list, tuple)):
        return []

    normalized = hooks.normalize_sources(SimpleNamespace(source_nodes=list(retrieved)))
    grounded = [source for source in normalized if hooks.source_supports_question(question, source)]
    return hooks.dedupe_sources_by_file(grounded)


def reconcile_sources_from_candidates(
    question: str,
    sources: SourceList,
    candidates: SourceList,
    *,
    hooks: SourceReconciliationHooks,
) -> SourceList:
    """基于已补拿的候选来源执行 reconcile，便于 chat_service 维持可 monkeypatch 的边界。"""
    if not candidates:
        return sources

    literal_terms = hooks.extract_literal_question_terms(question)
    if literal_terms and not any(source_matches_literal_terms(source, literal_terms, hooks=hooks) for source in sources):
        literal_matches = [source for source in candidates if source_matches_literal_terms(source, literal_terms, hooks=hooks)]
        if literal_matches and not hooks.question_prefers_cross_source_fact_assembly(question):
            return hooks.dedupe_sources_by_file(literal_matches[:1])

    if hooks.question_prefers_cross_source_fact_assembly(question):
        return hooks.dedupe_sources_by_file([*sources, *candidates])

    if hooks.question_requests_targeted_fact_answer(question) and len(hooks.dedupe_sources_by_file(sources)) <= 1:
        expanded = hooks.dedupe_sources_by_file([*sources, *candidates])
        if len(expanded) > len(hooks.dedupe_sources_by_file(sources)):
            return expanded

    return sources


def reconcile_sources_for_question(
    engine: Any,
    question: str,
    sources: SourceList,
    *,
    hooks: SourceReconciliationHooks,
) -> SourceList:
    """必要时补充/替换来源，避免 targeted/cross-source 问题只拿到半边证据。"""
    candidates = collect_candidate_sources_for_question(engine, question, hooks=hooks)
    return reconcile_sources_from_candidates(question, sources, candidates, hooks=hooks)
