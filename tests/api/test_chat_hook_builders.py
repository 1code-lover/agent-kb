"""chat_service hook builder 缓存与最小可用性测试。"""

from __future__ import annotations

from api.services import (
    chat_answer_repair,
    chat_composite_answers,
    chat_query_flow,
    chat_service,
    chat_source_answers,
    chat_source_selection,
    chat_targeted_fact,
)
from api.services.chat_postprocessors import SourceAnswerPostprocessorHooks


def test_chat_hook_builders_cache_pure_singletons_but_keep_dynamic_builders_fresh() -> None:
    """纯函数 hook builder 应缓存；会捕获 monkeypatch 依赖的 builder 必须保持按次装配。"""
    assert chat_service._build_source_projection_hooks() is chat_service._build_source_projection_hooks()
    assert chat_service._build_source_answer_repair_hooks() is chat_service._build_source_answer_repair_hooks()
    assert chat_service._build_source_selection_hooks() is chat_service._build_source_selection_hooks()
    assert chat_service._build_composite_answer_hooks() is chat_service._build_composite_answer_hooks()
    assert chat_service._build_targeted_fact_hooks() is chat_service._build_targeted_fact_hooks()
    assert isinstance(chat_service._build_source_projection_hooks(), chat_source_answers.SourceProjectionHooks)
    assert isinstance(chat_service._build_source_answer_repair_hooks(), chat_answer_repair.SourceAnswerRepairHooks)
    assert isinstance(chat_service._build_source_selection_hooks(), chat_source_selection.SourceSelectionHooks)
    assert isinstance(chat_service._build_query_flow_hooks(), chat_query_flow.QueryFlowHooks)
    assert isinstance(chat_service._build_composite_answer_hooks(), chat_composite_answers.CompositeAnswerHooks)
    assert isinstance(chat_service._build_targeted_fact_hooks(), chat_targeted_fact.TargetedFactHooks)
    assert isinstance(chat_service._build_source_answer_postprocessor_hooks(), SourceAnswerPostprocessorHooks)
    assert chat_service._build_source_answer_postprocessor_hooks() is not chat_service._build_source_answer_postprocessor_hooks()
    assert chat_service._build_query_flow_hooks() is not chat_service._build_query_flow_hooks()


def test_cached_targeted_fact_hooks_still_expand_candidates() -> None:
    """targeted-fact hooks 在缓存后仍需保持自引用候选抽取能力。"""
    source = {
        "text": "审批人: Alice\n截止时间: 周五前",
        "kb_id": "kb-a",
    }

    candidates = chat_service._iter_targeted_answer_candidates(source)

    assert "审批人: Alice" in candidates
    assert "截止时间: 周五前" in candidates
