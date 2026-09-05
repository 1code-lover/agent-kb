"""chat_source_reconciliation 的独立契约测试。"""

from __future__ import annotations

from types import SimpleNamespace

from api.services import chat_source_reconciliation


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
    question_lower = str(question or "").lower()
    source_lower = _build_source_text_blob(source).lower()
    return any(token in source_lower for token in question_lower.replace('?', '').split())


def _build_hooks(**overrides) -> chat_source_reconciliation.SourceReconciliationHooks:
    defaults = dict(
        normalize_sources=lambda response: list(getattr(response, 'source_nodes', response)),
        source_supports_question=_source_supports_question,
        dedupe_sources_by_file=_dedupe_sources_by_file,
        extract_literal_question_terms=lambda question: [],
        question_prefers_cross_source_fact_assembly=lambda question: False,
        question_requests_targeted_fact_answer=lambda question: False,
        build_source_text_blob=_build_source_text_blob,
    )
    defaults.update(overrides)
    return chat_source_reconciliation.SourceReconciliationHooks(**defaults)


def test_collect_candidate_sources_for_question_prefers_engine_retrieve_and_filters_ungrounded_duplicates():
    engine = SimpleNamespace(retrieve=lambda _question: [
        {'file': 'keep.md', 'text': 'cutover runbook deadline 22:30'},
        {'file': 'keep.md', 'text': 'duplicate keep'},
        {'file': 'drop.md', 'text': 'unrelated travel policy'},
    ])
    hooks = _build_hooks(source_supports_question=lambda question, source: source['file'] == 'keep.md')

    candidates = chat_source_reconciliation.collect_candidate_sources_for_question(
        engine,
        'What does the cutover runbook say?',
        hooks=hooks,
    )

    assert candidates == [{'file': 'keep.md', 'text': 'cutover runbook deadline 22:30'}]


def test_collect_candidate_sources_for_question_falls_back_to_manager_search_when_retrieve_missing():
    engine = SimpleNamespace(manager=SimpleNamespace(search=lambda question, top_k=4: [
        {'file': 'search.md', 'text': f'{question} result top_k={top_k}'},
    ]))

    candidates = chat_source_reconciliation.collect_candidate_sources_for_question(
        engine,
        'What does search find?',
        hooks=_build_hooks(),
        top_k=7,
    )

    assert candidates == [{'file': 'search.md', 'text': 'What does search find? result top_k=7'}]


def test_reconcile_sources_for_question_prefers_literal_path_match_when_current_sources_do_not_echo_literal_term():
    hooks = _build_hooks(
        extract_literal_question_terms=lambda question: ['cutover/runbook/'],
    )
    current_sources = [{'file': 'folder-boundary.md', 'text': 'Folder is organization only.'}]
    engine = SimpleNamespace(
        retrieve=lambda _question: [
            {'file': 'workflow-boundary.md', 'text': 'Path cutover/runbook/ stays organization only; KB remains authorization boundary.'},
        ]
    )

    reconciled = chat_source_reconciliation.reconcile_sources_for_question(
        engine,
        'Does cutover/runbook/ create a separate authorization boundary?',
        current_sources,
        hooks=hooks,
    )

    assert reconciled == [
        {'file': 'workflow-boundary.md', 'text': 'Path cutover/runbook/ stays organization only; KB remains authorization boundary.'},
    ]


def test_reconcile_sources_for_question_merges_cross_source_candidates_when_question_explicitly_requires_it():
    hooks = _build_hooks(question_prefers_cross_source_fact_assembly=lambda question: True)
    current_sources = [{'file': 'approval.md', 'text': 'Final sign-off deadline is 22:30.'}]
    engine = SimpleNamespace(
        retrieve=lambda _question: [
            {'file': 'approval.md', 'text': 'Final sign-off deadline is 22:30.'},
            {'file': 'handover.md', 'text': 'Escalation interval is 15 minutes.'},
        ]
    )

    reconciled = chat_source_reconciliation.reconcile_sources_for_question(
        engine,
        'Across the approval matrix and handover SLA, which value is the deadline and which is the escalation interval?',
        current_sources,
        hooks=hooks,
    )

    assert [source['file'] for source in reconciled] == ['approval.md', 'handover.md']


def test_reconcile_sources_for_question_expands_single_source_targeted_fact_answers():
    hooks = _build_hooks(question_requests_targeted_fact_answer=lambda question: True)
    current_sources = [{'file': 'approval.md', 'text': 'Final approver is Li Qing.'}]
    engine = SimpleNamespace(
        retrieve=lambda _question: [
            {'file': 'approval.md', 'text': 'Final approver is Li Qing.'},
            {'file': 'handover.md', 'text': 'Rollback owner is Zhou Yu.'},
        ]
    )

    reconciled = chat_source_reconciliation.reconcile_sources_for_question(
        engine,
        'Who is the final approver and who owns rollback?',
        current_sources,
        hooks=hooks,
    )

    assert [source['file'] for source in reconciled] == ['approval.md', 'handover.md']
