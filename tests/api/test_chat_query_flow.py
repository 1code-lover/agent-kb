"""chat_query_flow 模块纯函数测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from api.schemas import QueryRequest
from api.services import chat_query_flow


class _ScopeStub:
    def __init__(self) -> None:
        self.effective_kb_ids = ["kb-a"]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_scope_type": "single_kb",
            "requested_kb_ids": ["kb-a"],
            "effective_scope_type": "single_kb",
            "effective_kb_ids": ["kb-a"],
            "is_default_deny_applied": False,
            "isolation_level": "physical_isolated",
        }


def _build_hooks(**overrides: object) -> chat_query_flow.QueryFlowHooks:
    defaults: dict[str, object] = {
        "question_looks_follow_up": lambda question: False,
        "list_chat_messages": lambda session_id: [],
        "question_requests_exact_source_phrase": lambda question: False,
        "normalize_sources": lambda response: list(response),
        "dedupe_sources": lambda sources: list(sources),
        "reconcile_sources_for_question": lambda engine, question, sources: list(sources),
        "source_supports_question": lambda question, source: True,
        "build_refusal_answer": lambda question, scope=None: f"no answer for {question}",
        "append_chat_message": MagicMock(),
        "get_model_health": lambda: {"state": "ok"},
        "normalize_evidence": lambda sources: [{"source_count": len(sources)}],
        "build_query_engine": MagicMock(return_value="engine"),
        "attempt_model_fallback": MagicMock(return_value={"applied": False}),
        "invalidate_llm": MagicMock(),
        "question_requests_identifier_like_field": lambda question: False,
        "sources_support_identifier_like_field": lambda question, sources: True,
        "answer_is_refusal_like": lambda answer_text: False,
        "prune_sources_for_refusal": lambda question, answer_text, sources: list(sources),
        "apply_source_answer_postprocessors": lambda question, answer_text, sources: (answer_text, list(sources)),
        "max_follow_up_history_messages": 4,
        "max_follow_up_history_chars": 24,
    }
    defaults.update(overrides)
    return chat_query_flow.QueryFlowHooks(**defaults)


def test_load_recent_history_for_follow_up_filters_roles_and_limits_window() -> None:
    """仅保留最近有效 user/assistant 对话，并按字符窗口裁剪。"""
    hooks = _build_hooks(
        list_chat_messages=lambda _session_id: [
            {"role": "system", "content": "ignore me"},
            {"role": "user", "content": "first turn"},
            {"role": "assistant", "content": "second turn"},
            {"role": "user", "content": "third turn is much longer than the cap"},
        ],
        max_follow_up_history_messages=2,
        max_follow_up_history_chars=80,
    )

    history = chat_query_flow.load_recent_history_for_follow_up("session-a", hooks=hooks)

    assert history == [
        {"role": "assistant", "content": "second turn"},
        {"role": "user", "content": "third turn is much longer than the cap"},
    ]


def test_build_history_grounded_question_injects_session_context_for_follow_up() -> None:
    """follow-up 问题应注入裁剪后的同 session 历史。"""
    hooks = _build_hooks(
        question_looks_follow_up=lambda question: True,
        list_chat_messages=lambda _session_id: [
            {"role": "user", "content": "Tell me about rollback packet."},
            {"role": "assistant", "content": "It stays traceable inside one KB."},
        ],
        max_follow_up_history_chars=200,
    )

    grounded = chat_query_flow.build_history_grounded_question("Who approves it?", "session-a", hooks=hooks)

    assert "Conversation context from the same session:" in grounded
    assert "User: Tell me about rollback packet." in grounded
    assert "Assistant: It stays traceable inside one KB." in grounded
    assert grounded.endswith("Answer only from the active knowledge base.")


def test_preflight_exact_question_sources_filters_unsupported_sources() -> None:
    """exact phrase preflight 只返回能支撑问题的来源。"""
    engine = SimpleNamespace(retrieve=lambda _question: [{"file": "keep.md"}, {"file": "drop.md"}])
    hooks = _build_hooks(
        question_requests_exact_source_phrase=lambda question: True,
        source_supports_question=lambda _question, source: source["file"] == "keep.md",
    )

    sources = chat_query_flow.preflight_exact_question_sources(engine, "What does keep.md say?", hooks=hooks)

    assert sources == [{"file": "keep.md"}]


def test_build_no_source_result_records_history_and_model_health() -> None:
    """无来源结果应回填拒答、会话和 model health。"""
    append_chat_message = MagicMock()
    hooks = _build_hooks(
        append_chat_message=append_chat_message,
        get_model_health=lambda: {"state": "fallback_applied", "current_model": "good-chat"},
    )
    request = QueryRequest(question="Who approves it?", session_id="session-a", kb_ids=["kb-a"])
    scope = _ScopeStub()

    result = chat_query_flow.build_no_source_result(request, scope, record_history=True, hooks=hooks)

    assert result["answer"] == "no answer for Who approves it?"
    assert result["effective_kb_ids"] == ["kb-a"]
    assert result["model_health"]["current_model"] == "good-chat"
    append_chat_message.assert_any_call("session-a", "user", "Who approves it?")
    append_chat_message.assert_any_call("session-a", "assistant", "no answer for Who approves it?")


def test_build_no_source_result_passes_scope_into_refusal_builder() -> None:
    """无来源拒答应把 scope 透传给 refusal builder，便于输出 PDF-specific wording。"""
    seen: dict[str, object] = {}

    def _build_refusal(question: str, scope: object | None = None) -> str:
        seen["question"] = question
        seen["scope"] = scope
        return "active PDF knowledge base only"

    hooks = _build_hooks(build_refusal_answer=_build_refusal)
    request = QueryRequest(question="What checksum token is listed?", session_id="session-a", kb_ids=["eval-kb-pdf"])
    scope = _ScopeStub()
    scope.effective_kb_ids = ["eval-kb-pdf"]

    result = chat_query_flow.build_no_source_result(request, scope, record_history=False, hooks=hooks)

    assert result["answer"] == "active PDF knowledge base only"
    assert seen == {"question": "What checksum token is listed?", "scope": scope}


def test_build_query_engine_for_request_forwards_request_level_params() -> None:
    """query engine builder 应完整接收请求级 RAG 参数。"""
    build_query_engine = MagicMock(return_value="engine")
    hooks = _build_hooks(build_query_engine=build_query_engine)
    request = QueryRequest(
        question="What is the GPU memory requirement?",
        session_id="session-a",
        kb_ids=["ignored-by-scope"],
        top_k=9,
        response_mode="tree_summarize",
        use_reranker=False,
        top_n=2,
        reranker_model="custom-reranker",
    )
    scope = _ScopeStub()

    result = chat_query_flow.build_query_engine_for_request(request, scope, hooks=hooks)

    assert result == "engine"
    build_query_engine.assert_called_once_with(
        kb_ids=["kb-a"],
        top_k=9,
        response_mode="tree_summarize",
        use_reranker=False,
        top_n=2,
        reranker_model="custom-reranker",
    )


def test_execute_query_with_model_fallback_retries_after_applied_fallback() -> None:
    """fallback 生效时应重建 engine，并在同一问题上重试一次。"""
    first_engine = MagicMock()
    first_engine.query.side_effect = RuntimeError("quota exhausted")
    second_engine = MagicMock()
    second_engine.query.return_value = SimpleNamespace(response="fallback answer")
    build_query_engine = MagicMock(return_value=second_engine)
    attempt_model_fallback = MagicMock(return_value={"applied": True, "selected": {"model": "good-chat"}})
    invalidate_llm = MagicMock()
    hooks = _build_hooks(
        build_query_engine=build_query_engine,
        attempt_model_fallback=attempt_model_fallback,
        invalidate_llm=invalidate_llm,
    )
    request = QueryRequest(question="Who approves it?", session_id="session-a", kb_ids=["kb-a"])
    scope = _ScopeStub()

    answer, engine = chat_query_flow.execute_query_with_model_fallback(
        first_engine,
        request,
        scope,
        "Who approves it?",
        hooks=hooks,
    )

    assert answer.response == "fallback answer"
    assert engine is second_engine
    assert build_query_engine.call_count == 1
    attempt_model_fallback.assert_called_once()
    invalidate_llm.assert_called_once_with()
    second_engine.query.assert_called_once_with("Who approves it?")


def test_execute_query_with_model_fallback_reraises_when_fallback_not_applied() -> None:
    """fallback 未生效时应直接抛出原异常，且不应 invalidate LLM。"""
    engine = MagicMock()
    engine.query.side_effect = RuntimeError("hard failure")
    attempt_model_fallback = MagicMock(return_value={"applied": False})
    invalidate_llm = MagicMock()
    hooks = _build_hooks(
        build_query_engine=MagicMock(return_value=engine),
        attempt_model_fallback=attempt_model_fallback,
        invalidate_llm=invalidate_llm,
    )
    request = QueryRequest(question="Who approves it?", session_id="session-a", kb_ids=["kb-a"])
    scope = _ScopeStub()

    try:
        chat_query_flow.execute_query_with_model_fallback(engine, request, scope, "Who approves it?", hooks=hooks)
    except RuntimeError as exc:
        assert str(exc) == "hard failure"
    else:
        raise AssertionError("expected RuntimeError")

    attempt_model_fallback.assert_called_once()
    invalidate_llm.assert_not_called()


def test_build_query_result_records_history_evidence_and_scope() -> None:
    """正常结果组装应带上 history、evidence、model health 与 scope。"""
    append_chat_message = MagicMock()
    normalize_evidence = MagicMock(return_value=[{"source_count": 1}])
    hooks = _build_hooks(
        append_chat_message=append_chat_message,
        normalize_evidence=normalize_evidence,
        get_model_health=lambda: {"state": "fallback_applied", "current_model": "good-chat"},
    )
    request = QueryRequest(question="Who approves it?", session_id="session-a", kb_ids=["kb-a"])
    scope = _ScopeStub()
    sources = [{"file": "approval.md", "text": "Approver is Li Qing."}]

    result = chat_query_flow.build_query_result(
        request,
        scope,
        "Approver is Li Qing.",
        sources,
        record_history=True,
        hooks=hooks,
    )

    assert result["answer"] == "Approver is Li Qing."
    assert result["sources"] == sources
    assert result["evidence"] == [{"source_count": 1}]
    assert result["model_health"]["current_model"] == "good-chat"
    assert result["effective_kb_ids"] == ["kb-a"]
    append_chat_message.assert_any_call("session-a", "user", "Who approves it?")
    append_chat_message.assert_any_call("session-a", "assistant", "Approver is Li Qing.")
    normalize_evidence.assert_called_once_with(sources)


def test_extract_query_answer_payload_prefers_response_attribute_and_pipelines_sources() -> None:
    """应优先读取 answer.response，并按 normalize -> dedupe -> reconcile 顺序处理来源。"""
    call_order: list[tuple[str, object]] = []
    normalized_sources = [
        {"file": "cutover.md", "text": "Approver is Li Qing."},
        {"file": "cutover.md", "text": "Approver is Li Qing. duplicate chunk"},
    ]
    deduped_sources = [normalized_sources[0]]
    reconciled_sources = [
        normalized_sources[0],
        {"file": "rollback.md", "text": "Rollback owner is Zhou Yu."},
    ]

    def _normalize(answer: object) -> list[dict[str, object]]:
        call_order.append(("normalize", answer))
        return normalized_sources

    def _dedupe(sources: list[dict[str, object]]) -> list[dict[str, object]]:
        call_order.append(("dedupe", list(sources)))
        return deduped_sources

    def _reconcile(engine: object, question: str, sources: list[dict[str, object]]) -> list[dict[str, object]]:
        call_order.append(("reconcile", (engine, question, list(sources))))
        return reconciled_sources

    hooks = _build_hooks(
        normalize_sources=_normalize,
        dedupe_sources=_dedupe,
        reconcile_sources_for_question=_reconcile,
    )
    answer = SimpleNamespace(response="Cutover approver is Li Qing.", source_nodes=["unused"])
    engine = object()

    answer_text, sources = chat_query_flow.extract_query_answer_payload(
        answer,
        engine,
        "Who approves the cutover and who owns rollback?",
        hooks=hooks,
    )

    assert answer_text == "Cutover approver is Li Qing."
    assert sources == reconciled_sources
    assert call_order == [
        ("normalize", answer),
        ("dedupe", normalized_sources),
        ("reconcile", (engine, "Who approves the cutover and who owns rollback?", deduped_sources)),
    ]


def test_extract_query_answer_payload_falls_back_to_string_when_response_missing() -> None:
    """当 answer 没有 response 字段时，应回退到 str(answer)。"""

    class _AnswerWithoutResponse:
        def __str__(self) -> str:
            return "stringified answer"

    hooks = _build_hooks(normalize_sources=lambda response: [])

    answer_text, sources = chat_query_flow.extract_query_answer_payload(
        _AnswerWithoutResponse(),
        engine=object(),
        question="What is the answer?",
        hooks=hooks,
    )

    assert answer_text == "stringified answer"
    assert sources == []


def test_finalize_query_answer_turns_identifier_gap_into_refusal() -> None:
    """identifier-like 问题缺字段证据时应稳定拒答并清空 sources。"""
    apply_source_answer_postprocessors = MagicMock(return_value=("postprocessed", [{"file": "ignored.md"}]))
    hooks = _build_hooks(
        question_requests_identifier_like_field=lambda question: True,
        sources_support_identifier_like_field=lambda question, sources: False,
        build_refusal_answer=lambda question, scope=None: f"refuse {question}",
        apply_source_answer_postprocessors=apply_source_answer_postprocessors,
    )
    sources = [{"file": "ticket-guide.md", "text": "No CAB ticket recorded."}]

    answer_text, final_sources = chat_query_flow.finalize_query_answer(
        "What is the CAB ticket?",
        "hallucinated ticket",
        sources,
        hooks=hooks,
    )

    assert answer_text == "refuse What is the CAB ticket?"
    assert final_sources == []
    apply_source_answer_postprocessors.assert_not_called()


def test_finalize_query_answer_passes_scope_into_identifier_gap_refusal() -> None:
    """identifier-gap refusal 也应拿到 scope，避免 PDF KB 回退成通用 wording。"""
    apply_source_answer_postprocessors = MagicMock(return_value=("postprocessed", []))
    seen: dict[str, object] = {}

    def _build_refusal(question: str, scope: object | None = None) -> str:
        seen["question"] = question
        seen["scope"] = scope
        return "active PDF knowledge base only"

    hooks = _build_hooks(
        question_requests_identifier_like_field=lambda question: True,
        sources_support_identifier_like_field=lambda question, sources: False,
        build_refusal_answer=_build_refusal,
        apply_source_answer_postprocessors=apply_source_answer_postprocessors,
    )
    scope = _ScopeStub()
    scope.effective_kb_ids = ["eval-kb-pdf"]

    answer_text, final_sources = chat_query_flow.finalize_query_answer(
        "What pager rotation id does it list?",
        "hallucinated id",
        [{"file": "war-room-handover-business.pdf", "text": "Commander: Zhao Lin."}],
        scope=scope,
        hooks=hooks,
    )

    assert answer_text == "active PDF knowledge base only"
    assert final_sources == []
    assert seen == {"question": "What pager rotation id does it list?", "scope": scope}
    apply_source_answer_postprocessors.assert_not_called()


def test_finalize_query_answer_prunes_refusal_sources_before_postprocessing() -> None:
    """refusal 类回答应先裁剪 sources，不应再进入普通 postprocessor。"""
    apply_source_answer_postprocessors = MagicMock(return_value=("postprocessed", []))
    hooks = _build_hooks(
        answer_is_refusal_like=lambda answer_text: True,
        prune_sources_for_refusal=lambda question, answer_text, sources: [sources[0]],
        apply_source_answer_postprocessors=apply_source_answer_postprocessors,
    )
    sources = [
        {"file": "grounded.md", "text": "The document does not mention CAB ticket."},
        {"file": "noise.md", "text": "Rollback owner is Li Qing."},
    ]

    answer_text, final_sources = chat_query_flow.finalize_query_answer(
        "What is the CAB ticket?",
        "No confirmable information is available.",
        sources,
        hooks=hooks,
    )

    assert answer_text == "No confirmable information is available."
    assert final_sources == [sources[0]]
    apply_source_answer_postprocessors.assert_not_called()


def test_finalize_query_answer_routes_non_refusal_answer_to_postprocessors() -> None:
    """非 refusal 回答应走普通 postprocessor，并返回其改写结果。"""
    apply_source_answer_postprocessors = MagicMock(return_value=("expanded answer", [{"file": "keep.md"}]))
    hooks = _build_hooks(apply_source_answer_postprocessors=apply_source_answer_postprocessors)
    sources = [{"file": "keep.md", "text": "Approver is Li Qing."}]

    answer_text, final_sources = chat_query_flow.finalize_query_answer(
        "Who approves it?",
        "Li Qing",
        sources,
        hooks=hooks,
    )

    assert answer_text == "expanded answer"
    assert final_sources == [{"file": "keep.md"}]
    apply_source_answer_postprocessors.assert_called_once_with("Who approves it?", "Li Qing", sources)
