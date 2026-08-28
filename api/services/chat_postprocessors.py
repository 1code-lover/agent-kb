"""聊天问答 source-backed 后处理调度器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

SourceList = list[dict[str, Any]]
QuestionPredicate = Callable[[str], bool]
AnswerProcessor = Callable[[str, str, SourceList], str]
TargetedFactProcessor = Callable[[str, str, SourceList], tuple[str, SourceList]]
TableFieldExtractor = Callable[[str], list[str] | None]
BriefAnswerPredicate = Callable[[str], bool]
SourceMinimizer = Callable[[str, str, SourceList], SourceList]


@dataclass(frozen=True)
class SourceAnswerPostprocessorHooks:
    """收敛 chat_service 中后处理调度所需的分类器与处理器。"""

    extract_table_field_names: TableFieldExtractor
    question_requests_preview_expansion: QuestionPredicate
    answer_is_brief_entity: BriefAnswerPredicate
    question_benefits_from_brief_answer_expansion: QuestionPredicate
    question_requests_boundary_answer: QuestionPredicate
    question_requests_scope_definition: QuestionPredicate
    question_requests_multi_fact_merge: QuestionPredicate
    question_requests_summary_answer: QuestionPredicate
    question_requests_targeted_fact_answer: QuestionPredicate
    question_may_need_exact_term_repair: QuestionPredicate
    maybe_answer_table_fields_from_sources: AnswerProcessor
    maybe_answer_preview_from_sources: AnswerProcessor
    maybe_expand_brief_answer_from_sources: AnswerProcessor
    maybe_answer_boundary_from_sources: AnswerProcessor
    maybe_answer_scope_definition_from_sources: AnswerProcessor
    maybe_merge_source_facts_from_sources: AnswerProcessor
    maybe_answer_summary_bundle_from_sources: AnswerProcessor
    maybe_answer_targeted_fact_question_from_sources: TargetedFactProcessor
    maybe_repair_exact_terms_from_sources: AnswerProcessor
    minimize_sources_for_answer: SourceMinimizer


@dataclass(frozen=True)
class SourceAnswerPostprocessingPlan:
    """把后处理 if 链收口为可测试、可解释的显式路由计划。"""

    should_extract_table_fields: bool
    should_expand_preview: bool
    should_expand_brief_entity: bool
    should_answer_boundary: bool
    should_answer_scope_definition: bool
    should_merge_multi_fact: bool
    should_answer_summary: bool
    should_answer_targeted_fact: bool
    should_repair_exact_terms: bool

    def active_steps(self) -> tuple[str, ...]:
        """返回当前问题会命中的后处理步骤，便于测试显式协同边界。"""
        steps: list[str] = []
        if self.should_extract_table_fields:
            steps.append("table_fields")
        if self.should_expand_preview:
            steps.append("preview")
        if self.should_expand_brief_entity:
            steps.append("brief_expansion")
        if self.should_answer_boundary:
            steps.append("boundary")
        if self.should_answer_scope_definition:
            steps.append("scope_definition")
        if self.should_merge_multi_fact:
            steps.append("multi_fact_merge")
        if self.should_answer_summary:
            steps.append("summary")
        if self.should_answer_targeted_fact:
            steps.append("targeted_fact")
        if self.should_repair_exact_terms:
            steps.append("exact_repair")
        steps.append("minimize_sources")
        return tuple(steps)


def plan_source_answer_postprocessing(
    question: str,
    answer_text: str,
    *,
    hooks: SourceAnswerPostprocessorHooks,
) -> SourceAnswerPostprocessingPlan:
    """先冻结本轮题型路由，避免 apply 阶段继续隐式叠加 classifier。"""
    return SourceAnswerPostprocessingPlan(
        should_extract_table_fields=bool(hooks.extract_table_field_names(question)),
        should_expand_preview=hooks.question_requests_preview_expansion(question),
        should_expand_brief_entity=(
            hooks.answer_is_brief_entity(answer_text)
            and hooks.question_benefits_from_brief_answer_expansion(question)
        ),
        should_answer_boundary=hooks.question_requests_boundary_answer(question),
        should_answer_scope_definition=hooks.question_requests_scope_definition(question),
        should_merge_multi_fact=hooks.question_requests_multi_fact_merge(question),
        should_answer_summary=hooks.question_requests_summary_answer(question),
        should_answer_targeted_fact=hooks.question_requests_targeted_fact_answer(question),
        should_repair_exact_terms=hooks.question_may_need_exact_term_repair(question),
    )


def apply_source_answer_postprocessors(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    hooks: SourceAnswerPostprocessorHooks,
) -> tuple[str, SourceList]:
    """按显式题型路由调度 source-backed 后处理，避免每个问题都串行跑完整规则链。"""
    current_answer = answer_text
    current_sources = sources
    plan = plan_source_answer_postprocessing(question, answer_text, hooks=hooks)

    if plan.should_extract_table_fields:
        current_answer = hooks.maybe_answer_table_fields_from_sources(question, current_answer, current_sources)

    if plan.should_expand_preview:
        current_answer = hooks.maybe_answer_preview_from_sources(question, current_answer, current_sources)

    if plan.should_expand_brief_entity:
        current_answer = hooks.maybe_expand_brief_answer_from_sources(question, current_answer, current_sources)

    if plan.should_answer_boundary:
        current_answer = hooks.maybe_answer_boundary_from_sources(question, current_answer, current_sources)

    if plan.should_answer_scope_definition:
        current_answer = hooks.maybe_answer_scope_definition_from_sources(question, current_answer, current_sources)

    if plan.should_merge_multi_fact:
        current_answer = hooks.maybe_merge_source_facts_from_sources(question, current_answer, current_sources)

    if plan.should_answer_summary:
        current_answer = hooks.maybe_answer_summary_bundle_from_sources(question, current_answer, current_sources)

    if plan.should_answer_targeted_fact:
        current_answer, current_sources = hooks.maybe_answer_targeted_fact_question_from_sources(
            question,
            current_answer,
            current_sources,
        )

    if plan.should_repair_exact_terms:
        current_answer = hooks.maybe_repair_exact_terms_from_sources(question, current_answer, current_sources)

    current_sources = hooks.minimize_sources_for_answer(question, current_answer, current_sources)
    return current_answer, current_sources
