"""chat_postprocessors 调度器测试。"""

from __future__ import annotations

from api.services.chat_postprocessors import (
    SourceAnswerPostprocessorHooks,
    apply_source_answer_postprocessors,
    plan_source_answer_postprocessing,
)


def _make_hooks(**overrides) -> SourceAnswerPostprocessorHooks:
    """构造默认不触发任何分支的 hooks，便于覆盖单条调度路径。"""
    defaults = dict(
        extract_table_field_names=lambda question: None,
        question_requests_preview_expansion=lambda question: False,
        answer_is_brief_entity=lambda answer: False,
        question_benefits_from_brief_answer_expansion=lambda question: False,
        question_requests_boundary_answer=lambda question: False,
        question_requests_scope_definition=lambda question: False,
        question_requests_multi_fact_merge=lambda question: False,
        question_requests_summary_answer=lambda question: False,
        question_requests_targeted_fact_answer=lambda question: False,
        question_may_need_exact_term_repair=lambda question: False,
        maybe_answer_table_fields_from_sources=lambda question, answer, sources: answer,
        maybe_answer_preview_from_sources=lambda question, answer, sources: answer,
        maybe_expand_brief_answer_from_sources=lambda question, answer, sources: answer,
        maybe_answer_boundary_from_sources=lambda question, answer, sources: answer,
        maybe_answer_scope_definition_from_sources=lambda question, answer, sources: answer,
        maybe_merge_source_facts_from_sources=lambda question, answer, sources: answer,
        maybe_answer_summary_bundle_from_sources=lambda question, answer, sources: answer,
        maybe_answer_targeted_fact_question_from_sources=lambda question, answer, sources: (answer, sources),
        maybe_repair_exact_terms_from_sources=lambda question, answer, sources: answer,
        minimize_sources_for_answer=lambda question, answer, sources: sources,
    )
    defaults.update(overrides)
    return SourceAnswerPostprocessorHooks(**defaults)


def test_plan_source_answer_postprocessing_exposes_preview_targeted_exact_combo():
    """显式 route plan 应能表达 preview + targeted + exact 这类允许协同的组合。"""
    plan = plan_source_answer_postprocessing(
        'From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?',
        'draft',
        hooks=_make_hooks(
            question_requests_preview_expansion=lambda question: True,
            question_requests_targeted_fact_answer=lambda question: True,
            question_may_need_exact_term_repair=lambda question: True,
        ),
    )

    assert plan.active_steps() == ('preview', 'targeted_fact', 'exact_repair', 'minimize_sources')


def test_apply_source_answer_postprocessors_routes_preview_and_exact_steps():
    """preview 问题应先走 preview 修正，再走 exact repair，并保持最小 source 收敛。"""
    call_order: list[str] = []

    def preview(question, answer, sources):
        call_order.append('preview')
        assert answer == 'draft'
        return 'previewed'

    def exact(question, answer, sources):
        call_order.append('exact')
        assert answer == 'previewed'
        return 'repaired'

    def minimize(question, answer, sources):
        call_order.append('minimize')
        assert answer == 'repaired'
        return [{'file': 'preview.md', 'text': 'minimal'}]

    answer, used_sources = apply_source_answer_postprocessors(
        'What should preview return?',
        'draft',
        [{'file': 'preview.md', 'text': 'raw'}],
        hooks=_make_hooks(
            question_requests_preview_expansion=lambda question: True,
            question_may_need_exact_term_repair=lambda question: True,
            maybe_answer_preview_from_sources=preview,
            maybe_repair_exact_terms_from_sources=exact,
            minimize_sources_for_answer=minimize,
        ),
    )

    assert answer == 'repaired'
    assert used_sources == [{'file': 'preview.md', 'text': 'minimal'}]
    assert call_order == ['preview', 'exact', 'minimize']


def test_apply_source_answer_postprocessors_plain_targeted_fact_skips_exact_repair():
    """plain targeted 问题应只走 targeted/minimize，避免无差别再叠一层 exact repair。"""
    call_order: list[str] = []

    def targeted(question, answer, sources):
        call_order.append('targeted')
        assert answer == 'draft'
        return 'focused', sources

    def exact(*args, **kwargs):
        raise AssertionError('exact repair should not run for plain targeted question')

    def minimize(question, answer, sources):
        call_order.append('minimize')
        assert answer == 'focused'
        return sources

    answer, used_sources = apply_source_answer_postprocessors(
        'Who approves the cutover and who owns rollback?',
        'draft',
        [{'file': 'cutover.md', 'text': 'raw'}],
        hooks=_make_hooks(
            question_requests_targeted_fact_answer=lambda question: True,
            maybe_answer_targeted_fact_question_from_sources=targeted,
            maybe_repair_exact_terms_from_sources=exact,
            minimize_sources_for_answer=minimize,
        ),
    )

    assert answer == 'focused'
    assert used_sources == [{'file': 'cutover.md', 'text': 'raw'}]
    assert call_order == ['targeted', 'minimize']


def test_apply_source_answer_postprocessors_passes_targeted_fact_sources_into_exact_repair_when_route_requires_it():
    """targeted 分支若仍需 exact repair，应把最新 answer 与最新 sources 传给 exact。"""
    targeted_sources = [{'file': 'targeted.md', 'text': 'focused evidence'}]
    call_order: list[str] = []

    def targeted(question, answer, sources):
        call_order.append('targeted')
        assert answer == 'previewed'
        return 'focused', targeted_sources

    def exact(question, answer, sources):
        call_order.append('exact')
        assert answer == 'focused'
        assert sources == targeted_sources
        return 'focused exact'

    def minimize(question, answer, sources):
        call_order.append('minimize')
        assert answer == 'focused exact'
        assert sources == targeted_sources
        return sources

    answer, used_sources = apply_source_answer_postprocessors(
        'From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?',
        'draft',
        [{'file': 'raw.md', 'text': 'raw'}],
        hooks=_make_hooks(
            question_requests_preview_expansion=lambda question: True,
            question_requests_targeted_fact_answer=lambda question: True,
            question_may_need_exact_term_repair=lambda question: True,
            maybe_answer_preview_from_sources=lambda question, answer, sources: 'previewed',
            maybe_answer_targeted_fact_question_from_sources=targeted,
            maybe_repair_exact_terms_from_sources=exact,
            minimize_sources_for_answer=minimize,
        ),
    )

    assert answer == 'focused exact'
    assert used_sources == targeted_sources
    assert call_order == ['targeted', 'exact', 'minimize']
