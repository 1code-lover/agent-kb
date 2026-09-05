"""聊天服务核心分支测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from api.schemas import QueryRequest
from api.services.query_scope import ChatQueryScope


@pytest.fixture
def chat_service_module():
    """统一导入 chat_service 模块，便于各用例复用 monkeypatch。"""
    import api.services.chat_service as chat_service

    return chat_service


@pytest.fixture
def single_kb_scope() -> ChatQueryScope:
    """构造单库查询范围回显对象。"""
    return ChatQueryScope(
        requested_scope_type="single_kb",
        requested_kb_ids=["kb-a"],
        effective_scope_type="single_kb",
        effective_kb_ids=["kb-a"],
        is_default_deny_applied=False,
        isolation_level="physical_isolated",
    )


def _build_request(question: str = "What is the GPU memory requirement?") -> QueryRequest:
    """构造标准 QueryRequest。"""
    return QueryRequest(question=question, session_id="chat-service-test", kb_ids=["kb-a"])


def _stub_query_runtime(chat_service, monkeypatch, single_kb_scope: ChatQueryScope, *, answer_text: str = "answer"):
    """为 query() 注入可控 scope/runtime/query_engine。"""
    engine = MagicMock()
    engine.query.return_value = SimpleNamespace(response=answer_text, source_nodes=[])

    monkeypatch.setattr(chat_service, "resolve_chat_query_scope", MagicMock(return_value=single_kb_scope))
    monkeypatch.setattr(chat_service.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    build_query_engine = MagicMock(return_value=engine)
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", build_query_engine)
    return engine, build_query_engine


def test_tokenize_text_extracts_stems_and_cjk_ngrams(chat_service_module):
    """tokenize 应过滤停用词，并补出英文词干与中文 2/3-gram。"""
    tokens = chat_service_module._tokenize_text("What deploying services need 服务发布检查")

    assert "what" not in tokens
    assert "deploying" in tokens
    assert "deploy" in tokens
    assert "services" in tokens
    assert "service" in tokens
    assert "服务发布检查" in tokens
    assert "服务" in tokens
    assert "发布" in tokens
    assert "服务发" in tokens


def test_source_supports_question_returns_true_when_question_tokens_empty(chat_service_module):
    """当问题分词后为空时，不应误删全部来源。"""
    source = {"title": "guide.md", "text": "release checklist and rollback plan"}

    assert chat_service_module._source_supports_question("a an the", source) is True


def test_source_supports_question_returns_false_when_source_tokens_empty(chat_service_module):
    """当来源文本没有有效 token 时，应视为无法支撑当前问题。"""
    source = {"title": "", "text": "!!! ???", "excerpt": "   "}

    assert chat_service_module._source_supports_question("release checklist", source) is False


def test_source_supports_question_returns_true_on_token_overlap(chat_service_module):
    """问题与来源有词面交集时，应判定为可支撑。"""
    source = {"title": "mobile-build-guide.md", "text": "GPU memory requirement is described here."}

    assert chat_service_module._source_supports_question("What is the GPU memory requirement?", source) is True


def test_prune_sources_for_refusal_keeps_only_refusal_backed_grounded_sources(chat_service_module):
    """拒答分支只保留既同主题又能支撑“信息缺失/拒答”结论的来源。"""
    sources = [
        {"file": "mobile-build-guide.md", "text": "GPU memory requirement is not specified."},
        {"file": "cutover.md", "text": "Rollback approval is issued by the deployment lead."},
    ]

    pruned = chat_service_module._prune_sources_for_refusal(
        "What is the GPU memory requirement for the mobile build?",
        "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only.",
        sources,
    )

    assert pruned == [sources[0]]


def test_prune_sources_for_refusal_hides_topical_but_non_refusal_sources(chat_service_module):
    """主题相关但未直接说明“缺证据/未列出”的来源，不应在拒答时继续暴露。"""
    sources = [
        {"file": "payroll-cutover.md", "text": "Payroll cutover approver is Li Qing and rollback owner is Zhou Yu."},
        {"file": "handover.md", "text": "War-room escalation interval is 15 minutes."},
    ]

    pruned = chat_service_module._prune_sources_for_refusal(
        "What is the CAB ticket number for the payroll cutover?",
        "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only.",
        sources,
    )

    assert pruned == []


def test_prune_sources_for_refusal_accepts_no_confirmable_evidence_wording(chat_service_module):
    """来源若明确说明“no confirmable evidence”，也应视为能支撑拒答。"""
    sources = [
        {
            "file": "refusal-guideline.md",
            "text": "If the current knowledge base has no confirmable evidence, the answer should explicitly say so and must not fabricate.",
        },
        {"file": "handover.md", "text": "War-room escalation interval is 15 minutes."},
    ]

    pruned = chat_service_module._prune_sources_for_refusal(
        "How should the assistant respond when the current KB has no confirmable evidence?",
        "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only.",
        sources,
    )

    assert pruned == [sources[0]]


def test_dedupe_sources_by_file_keeps_first_chunk_per_kb_file(chat_service_module):
    """sources 应按 kb_id + file 去重，但保留不同 KB 的同名文件。"""
    sources = [
        {"file": "policy.docx", "kb_id": "kb-a", "text": "first"},
        {"file": "policy.docx", "kb_id": "kb-a", "text": "second"},
        {"file": "policy.docx", "kb_id": "kb-b", "text": "other kb"},
        {"file": "manual.pdf", "kb_id": "kb-a", "text": "manual"},
    ]

    deduped = chat_service_module._dedupe_sources_by_file(sources)

    assert deduped == [sources[0], sources[2], sources[3]]


def test_query_raises_when_index_is_empty(chat_service_module, monkeypatch, single_kb_scope):
    """索引未就绪时，query 应直接拒绝而不是继续构建引擎。"""
    monkeypatch.setattr(chat_service_module, "resolve_chat_query_scope", MagicMock(return_value=single_kb_scope))
    monkeypatch.setattr(chat_service_module.runtime_state, "ensure_index_loaded", MagicMock(return_value=False))
    build_query_engine = MagicMock()
    monkeypatch.setattr(chat_service_module.runtime_state, "build_query_engine", build_query_engine)

    with pytest.raises(ValueError, match="Knowledge base is empty"):
        chat_service_module.query(_build_request(), record_history=False)

    build_query_engine.assert_not_called()


def test_query_does_not_record_history_when_disabled(chat_service_module, monkeypatch, single_kb_scope):
    """record_history=False 时不应产生任何会话写入。"""
    engine, build_query_engine = _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="GPU memory is 8GB.")
    sources = [{"file": "mobile-build-guide.md", "text": "GPU memory requirement is 8GB."}]
    append_chat_message = MagicMock()
    normalize_evidence = MagicMock(return_value=[{"id": "ev-1"}])
    model_health = {"state": "healthy", "current_model": "gpt-test"}

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", append_chat_message)
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)
    monkeypatch.setattr(chat_service_module.model_service, "get_model_health", MagicMock(return_value=model_health))

    result = chat_service_module.query(_build_request(), record_history=False)

    assert result["answer"] == "GPU memory is 8GB."
    assert result["sources"] == sources
    assert result["evidence"] == [{"id": "ev-1"}]
    assert result["model_health"] == model_health
    assert result["effective_kb_ids"] == ["kb-a"]
    build_query_engine.assert_called_once_with(
        kb_ids=["kb-a"],
        top_k=None,
        response_mode=None,
        use_reranker=None,
        top_n=None,
        reranker_model=None,
    )
    engine.query.assert_called_once_with("What is the GPU memory requirement?")
    append_chat_message.assert_not_called()
    normalize_evidence.assert_called_once_with(sources)


def test_query_exact_question_refuses_before_llm_when_retrieval_has_no_grounded_source(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """唯一值问题在限定 KB 内没有相关证据时，应直接拒答，避免无上下文模型错误或跨库泄漏。"""
    engine, _ = _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="should not run")
    engine.retrieve.return_value = [
        SimpleNamespace(
            node=SimpleNamespace(
                metadata={"file_name": "grain-policy.pdf", "kb_id": "kb-a", "doc_id": "grain-doc"},
                text="Reserve grain supervision policy and warehouse temperature checks.",
            ),
            score=0.72,
        )
    ]
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    model_health = {"state": "healthy", "current_model": "gpt-test"}
    monkeypatch.setattr(chat_service_module.model_service, "get_model_health", MagicMock(return_value=model_health))

    result = chat_service_module.query(
        _build_request(question="What is the unique desktop workflow passcode in diagnostic document 1786352564?"),
        record_history=False,
    )

    assert result["answer"] == "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only."
    assert result["sources"] == []
    assert result["evidence"] == []
    assert result["model_health"] == model_health
    engine.query.assert_not_called()


def test_query_fallbacks_model_once_and_retries(chat_service_module, monkeypatch, single_kb_scope):
    """模型调用失败时，chat query 应触发 fallback 并用新引擎重试一次。"""
    first_engine = MagicMock()
    first_engine.query.side_effect = RuntimeError("Free quota exhausted")
    second_engine = MagicMock()
    second_engine.query.return_value = SimpleNamespace(response="fallback answer", source_nodes=[])
    build_query_engine = MagicMock(side_effect=[first_engine, second_engine])
    fallback = MagicMock(return_value={"applied": True, "selected": {"model": "good-chat"}})
    invalidate_llm = MagicMock()
    model_health = {
        "state": "fallback_applied",
        "current_provider": "Cloud",
        "current_model": "good-chat",
        "fallback_from": {"service_provider": "OpenAI", "model": "bad-chat"},
        "fallback_to": {"service_provider": "Cloud", "model": "good-chat"},
    }

    monkeypatch.setattr(chat_service_module, "resolve_chat_query_scope", MagicMock(return_value=single_kb_scope))
    monkeypatch.setattr(chat_service_module.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(chat_service_module.runtime_state, "build_query_engine", build_query_engine)
    monkeypatch.setattr(chat_service_module.runtime_state, "invalidate_llm", invalidate_llm)
    monkeypatch.setattr(chat_service_module.model_service, "attempt_model_fallback", fallback)
    monkeypatch.setattr(chat_service_module.model_service, "get_model_health", MagicMock(return_value=model_health))
    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(_build_request(), record_history=False)

    assert result["answer"] == "fallback answer"
    assert result["model_health"] == model_health
    assert build_query_engine.call_count == 2
    fallback.assert_called_once()
    invalidate_llm.assert_called_once_with()
    second_engine.query.assert_called_once_with("What is the GPU memory requirement?")



def test_build_query_engine_for_request_forwards_request_level_rag_params(chat_service_module, monkeypatch, single_kb_scope):
    """请求级 QueryRequest 参数应完整透传到 runtime query engine 构建。"""
    build_query_engine = MagicMock(return_value="engine")
    monkeypatch.setattr(chat_service_module.runtime_state, "build_query_engine", build_query_engine)
    request = QueryRequest(
        question="What is the GPU memory requirement?",
        session_id="chat-service-test",
        kb_ids=["ignored-by-scope"],
        top_k=9,
        response_mode="tree_summarize",
        use_reranker=False,
        top_n=2,
        reranker_model="custom-reranker",
    )

    result = chat_service_module._build_query_engine_for_request(request, single_kb_scope)

    assert result == "engine"
    build_query_engine.assert_called_once_with(
        kb_ids=["kb-a"],
        top_k=9,
        response_mode="tree_summarize",
        use_reranker=False,
        top_n=2,
        reranker_model="custom-reranker",
    )



def test_query_fallback_rebuild_keeps_request_level_rag_params(chat_service_module, monkeypatch, single_kb_scope):
    """fallback 重建 query engine 时，不能丢掉请求级 top_k/reranker/response_mode。"""
    first_engine = MagicMock()
    first_engine.query.side_effect = RuntimeError("Free quota exhausted")
    second_engine = MagicMock()
    second_engine.query.return_value = SimpleNamespace(response="fallback answer", source_nodes=[])
    build_query_engine = MagicMock(side_effect=[first_engine, second_engine])

    monkeypatch.setattr(chat_service_module, "resolve_chat_query_scope", MagicMock(return_value=single_kb_scope))
    monkeypatch.setattr(chat_service_module.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(chat_service_module.runtime_state, "build_query_engine", build_query_engine)
    monkeypatch.setattr(chat_service_module.runtime_state, "invalidate_llm", MagicMock())
    monkeypatch.setattr(
        chat_service_module.model_service,
        "attempt_model_fallback",
        MagicMock(return_value={"applied": True, "selected": {"model": "good-chat"}}),
    )
    monkeypatch.setattr(chat_service_module.model_service, "get_model_health", MagicMock(return_value={"state": "fallback_applied"}))
    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    request = QueryRequest(
        question="What is the GPU memory requirement?",
        session_id="chat-service-test",
        kb_ids=["kb-a"],
        top_k=11,
        response_mode="compact",
        use_reranker=False,
        top_n=1,
        reranker_model="custom-reranker",
    )

    result = chat_service_module.query(request, record_history=False)

    assert result["answer"] == "fallback answer"
    assert build_query_engine.call_count == 2
    assert build_query_engine.call_args_list == [
        call(
            kb_ids=["kb-a"],
            top_k=11,
            response_mode="compact",
            use_reranker=False,
            top_n=1,
            reranker_model="custom-reranker",
        ),
        call(
            kb_ids=["kb-a"],
            top_k=11,
            response_mode="compact",
            use_reranker=False,
            top_n=1,
            reranker_model="custom-reranker",
        ),
    ]


def test_query_records_history_and_prunes_refusal_sources(chat_service_module, monkeypatch, single_kb_scope):
    """拒答回答应裁剪无关来源，并按用户/助手顺序记录历史。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="The mobile build guide does not mention any GPU memory requirement.",
    )
    relevant = {"file": "mobile-build-guide.md", "text": "The mobile build guide does not mention GPU memory requirement."}
    unrelated = {"file": "cutover.md", "text": "Rollback approval is issued by the deployment lead."}
    append_chat_message = MagicMock()
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[relevant, unrelated]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", append_chat_message)
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(_build_request(), record_history=True)

    assert result["sources"] == [relevant]
    assert result["evidence"] == [{"source_count": 1}]
    normalize_evidence.assert_called_once_with([relevant])
    assert append_chat_message.call_args_list == [
        call("chat-service-test", "user", "What is the GPU memory requirement?"),
        call("chat-service-test", "assistant", "The mobile build guide does not mention any GPU memory requirement."),
    ]


def test_query_refusal_hides_sources_without_refusal_backing(chat_service_module, monkeypatch, single_kb_scope):
    """当模型因字段缺失而拒答时，若返回的 chunk 只同主题但未直接支撑拒答，应清空 sources/evidence。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only.",
    )
    topical_only = {
        "file": "payroll-cutover.md",
        "text": "Payroll cutover approver is Li Qing and rollback owner is Zhou Yu.",
    }
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[topical_only]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(
        _build_request(question="What is the CAB ticket number for the payroll cutover?"),
        record_history=False,
    )

    assert result["answer"] == "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only."
    assert result["sources"] == []
    assert result["evidence"] == [{"source_count": 0}]
    normalize_evidence.assert_called_once_with([])

def test_query_scope_first_chinese_refusal_still_prunes_sources(chat_service_module, monkeypatch, single_kb_scope):
    """中文 negative-contract 若先给 scope，再给 refusal/memory，也应走拒答裁剪分支。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text=(
            "请仅依据当前知识库回答。\n"
            "当前知识库中没有可确认的信息。\n"
            "助手不得从外部记忆编造答案。"
        ),
    )
    relevant = {
        "file": "grain-scope.md",
        "text": "粮仓质检流程：当前知识库中没有可确认的信息。助手不得从外部记忆编造答案。",
    }
    unrelated = {
        "file": "handover.md",
        "text": "War-room escalation interval is 15 minutes.",
    }
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[relevant, unrelated]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(
        _build_request(question="如果当前知识库里没有可确认信息，助手应该怎么回答？"),
        record_history=False,
    )

    assert result["answer"].startswith("请仅依据当前知识库回答")
    assert result["sources"] == [relevant]
    assert result["evidence"] == [{"source_count": 1}]
    normalize_evidence.assert_called_once_with([relevant])


def test_sources_support_identifier_like_field_requires_field_signal_not_topic_overlap(chat_service_module):
    """bridge URL 问题不能因为 source 里出现 war-room 主题词就误判为字段已覆盖。"""
    sources = [
        {
            "file": "handover-sla.md",
            "text": "War-room handover SLA: escalate P1 incidents to the on-call manager within 15 minutes.",
        }
    ]

    assert chat_service_module._sources_support_identifier_like_field(
        "What bridge URL is listed for the war-room handover?",
        sources,
    ) is False



def test_sources_support_identifier_like_field_accepts_actual_url_evidence(chat_service_module):
    """当 source 明确给出 URL/链接证据时，不应误触发 identifier-gap 拒答。"""
    sources = [
        {
            "file": "handover-contact.md",
            "text": "Bridge URL: https://handover-bridge.local for the incident war room.",
        }
    ]

    assert chat_service_module._sources_support_identifier_like_field(
        "What bridge URL is listed for the war-room handover?",
        sources,
    ) is True



def test_answer_is_refusal_like_ignores_fact_answers_that_quote_refusal_guideline(chat_service_module):
    """只是在事实答案里引用 refusal 指南，不应整体判成拒答。"""
    answer = (
        "cutover-approval.md: Final approver is Li Qing\n"
        "handover-sla.md: On-call manager is Zhao Lin\n"
        "If the current knowledge base has no confirmable evidence, the assistant must refuse instead of fabricating."
    )

    assert chat_service_module._answer_is_refusal_like(answer) is False

def test_answer_is_refusal_like_accepts_chinese_scope_then_refusal_then_memory(chat_service_module):
    """当前知识库/外部记忆分行回答时，即使 refusal 锚点不在首行，也应判成拒答。"""
    answer = (
        "请仅依据当前知识库回答。\n"
        "当前知识库中没有可确认的信息。\n"
        "助手不得从外部记忆编造答案。"
    )

    assert chat_service_module._answer_is_refusal_like(answer) is True

def test_query_keeps_multi_sources_when_fact_answer_quotes_refusal_guideline(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """多文档事实答案即便引用 refusal 规则，也不应被误判成拒答并裁剪 sources。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text=(
            "cutover-approval.md: - Final approver: Release Manager Li Qing\n"
            "- Rollback owner: Platform SRE Wang Lei\n"
            "- Business confirmer: Finance Ops Zhou Yu\n"
            "handover-sla.md: - P1 cutover incident must be escalated to on-call manager Zhao Lin within 15 minutes\n"
            "- If the current knowledge base has no confirmable evidence, the assistant must refuse instead of fabricating."
        ),
    )
    sources = [
        {
            "file": "cutover-approval.md",
            "text": "Final approver: Release Manager Li Qing. Rollback owner: Platform SRE Wang Lei.",
        },
        {
            "file": "handover-sla.md",
            "text": (
                "P1 cutover incident must be escalated to on-call manager Zhao Lin within 15 minutes. "
                "If the current knowledge base has no confirmable evidence, the assistant must refuse instead of fabricating."
            ),
        },
    ]
    normalize_evidence = MagicMock(return_value=[{"id": "ev-1"}, {"id": "ev-2"}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(
        _build_request(
            question="Compare the payroll cutover approval matrix and the war-room handover SLA: who is the final approver and who is the on-call manager?"
        ),
        record_history=False,
    )

    assert [source["file"] for source in result["sources"]] == ["cutover-approval.md", "handover-sla.md"]
    assert result["sources"][0]["text"] == "Final approver: Release Manager Li Qing."
    assert "Rollback owner" not in result["sources"][0]["text"]
    assert "within 15 minutes" in result["sources"][1]["text"]
    assert "refuse instead of fabricating" not in result["sources"][1]["text"]
    assert result["evidence"] == [{"id": "ev-1"}, {"id": "ev-2"}]
    normalize_evidence.assert_called_once_with(result["sources"])



def test_query_identifier_like_gap_clears_sources_even_with_refusal_guideline(chat_service_module, monkeypatch, single_kb_scope):
    """字段缺口触发的拒答应清空误导性 sources，即便 chunk 里顺带写了 refusal guideline。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Bridge URL is not available.",
    )
    topical_with_guideline = {
        "file": "handover-sla.md",
        "text": (
            "War-room handover SLA: escalate P1 incidents to Zhao Lin within 15 minutes. "
            "If the current knowledge base has no confirmable evidence, the assistant must refuse instead of fabricating."
        ),
    }
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[topical_with_guideline]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(
        _build_request(question="What bridge URL is listed for the war-room handover?"),
        record_history=False,
    )

    assert result["answer"] == "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only."
    assert result["sources"] == []
    assert result["evidence"] == [{"source_count": 0}]
    normalize_evidence.assert_called_once_with([])



def test_question_requests_identifier_like_field_detects_pager_rotation_id(chat_service_module):
    """pager rotation id 这类字段问题不能因为 id 被停用词过滤而漏检。"""
    assert chat_service_module._question_requests_identifier_like_field(
        "What pager rotation id is listed in the PDF war-room handover sheet?"
    ) is True



def test_query_identifier_like_gap_turns_unrelated_fact_answer_into_refusal(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """ticket/url 等字段若来源完全没提到，应拒答而不是返回同主题的其他事实。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Final approver: Release Manager Li Qing.",
    )
    topical_only = {
        "file": "cutover-approval.md",
        "text": "Final approver: Release Manager Li Qing. Rollback owner: Platform SRE Wang Lei.",
    }
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[topical_only]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(
        _build_request(question="What is the CAB ticket number for the payroll cutover?"),
        record_history=False,
    )

    assert result["answer"] == "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only."
    assert result["sources"] == []
    assert result["evidence"] == [{"source_count": 0}]
    normalize_evidence.assert_called_once_with([])


def test_query_identifier_like_gap_uses_pdf_scope_refusal_for_generic_question(chat_service_module, monkeypatch):
    """generic identifier 问句在 PDF KB 下触发拒答时，也应收口到 active PDF knowledge base。"""
    pdf_scope = ChatQueryScope(
        requested_scope_type="single_kb",
        requested_kb_ids=["eval-kb-pdf"],
        effective_scope_type="single_kb",
        effective_kb_ids=["eval-kb-pdf"],
        is_default_deny_applied=False,
        isolation_level="physical_isolated",
    )
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        pdf_scope,
        answer_text="Primary incident commander: Zhao Lin.",
    )
    monkeypatch.setattr(
        chat_service_module.kb_service,
        "list_docs",
        MagicMock(return_value=[{"name": "war-room-handover-business.pdf"}, {"name": "refusal-rule.pdf"}]),
    )
    topical_only = {
        "file": "war-room-handover-business.pdf",
        "text": "Primary incident commander: Zhao Lin. Sev1 escalation interval: 10 minutes.",
    }
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[topical_only]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    request = QueryRequest(question="What pager rotation id does it list?", session_id="chat-service-test", kb_ids=["eval-kb-pdf"])
    result = chat_service_module.query(request, record_history=False)

    assert result["answer"] == (
        "No confirmable information is available in the current knowledge base. "
        "Please answer from the active PDF knowledge base only."
    )
    assert result["sources"] == []
    assert result["evidence"] == [{"source_count": 0}]
    normalize_evidence.assert_called_once_with([])


def test_query_keeps_sources_for_non_refusal_answer(chat_service_module, monkeypatch, single_kb_scope):
    """正常命中答案时，不应错误裁剪来源。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="GPU memory requirement is 8GB.")
    sources = [
        {"file": "mobile-build-guide.md", "text": "GPU memory requirement is 8GB."},
        {"file": "faq.md", "text": "Supported devices include the mobile build target."},
    ]
    normalize_evidence = MagicMock(return_value=[{"id": "ev-2"}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(_build_request(), record_history=False)

    assert result["sources"] == sources
    normalize_evidence.assert_called_once_with(sources)


def test_query_dedupes_sources_before_evidence(chat_service_module, monkeypatch, single_kb_scope):
    """正常回答返回前应合并同一 KB 同一文件的重复 chunks。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="GPU memory requirement is 8GB.")
    sources = [
        {"file": "mobile-build-guide.md", "kb_id": "kb-a", "text": "GPU memory requirement is 8GB."},
        {"file": "mobile-build-guide.md", "kb_id": "kb-a", "text": "GPU memory requirement is 8GB again."},
        {"file": "faq.md", "kb_id": "kb-a", "text": "Supported devices include the mobile build target."},
    ]
    expected_sources = [sources[0], sources[2]]
    normalize_evidence = MagicMock(return_value=[{"id": "ev-2"}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(_build_request(), record_history=False)

    assert result["sources"] == expected_sources
    normalize_evidence.assert_called_once_with(expected_sources)


def test_apply_source_answer_postprocessors_routes_preview_question(chat_service_module, monkeypatch):
    """preview 问题只应触发 preview/exact/minimize 相关后处理。"""
    sources = [{"file": "preview-board.png", "text": "Every evidence preview must include doc_id and preview_locator."}]
    preview = MagicMock(return_value="Preview answer from source.")
    exact = MagicMock(return_value="Preview answer repaired exactly.")
    minimize = MagicMock(return_value=[{"file": "preview-board.png", "text": "Preview answer repaired exactly."}])

    def _unexpected(name: str):
        def _raiser(*args, **kwargs):
            raise AssertionError(f"{name} should not run for preview-only question")

        return _raiser

    monkeypatch.setattr(chat_service_module, "_maybe_answer_preview_from_sources", preview)
    monkeypatch.setattr(chat_service_module, "_maybe_repair_exact_terms_from_sources", exact)
    monkeypatch.setattr(chat_service_module, "_minimize_sources_for_answer", minimize)
    monkeypatch.setattr(chat_service_module, "_maybe_expand_brief_answer_from_sources", _unexpected("brief expansion"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_boundary_from_sources", _unexpected("boundary"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_scope_definition_from_sources", _unexpected("scope"))
    monkeypatch.setattr(chat_service_module, "_maybe_merge_source_facts_from_sources", _unexpected("merge"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_summary_bundle_from_sources", _unexpected("summary"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_targeted_fact_question_from_sources", _unexpected("targeted fact"))

    answer, used_sources = chat_service_module._apply_source_answer_postprocessors(
        "What should evidence preview resolve after chat returns sources?",
        "Evidence preview checklist.",
        sources,
    )

    assert answer == "Preview answer repaired exactly."
    assert used_sources == [{"file": "preview-board.png", "text": "Preview answer repaired exactly."}]
    preview.assert_called_once_with(
        "What should evidence preview resolve after chat returns sources?",
        "Evidence preview checklist.",
        sources,
    )
    exact.assert_called_once_with(
        "What should evidence preview resolve after chat returns sources?",
        "Preview answer from source.",
        sources,
    )
    minimize.assert_called_once_with(
        "What should evidence preview resolve after chat returns sources?",
        "Preview answer repaired exactly.",
        sources,
    )



def test_apply_source_answer_postprocessors_routes_targeted_fact_question(chat_service_module, monkeypatch):
    """plain targeted-fact 问题应只走 targeted/minimize，不再无差别叠 exact repair。"""
    sources = [{"file": "cutover.md", "text": "Cutover approver is Li Qing. Rollback owner is Zhou Yu."}]
    targeted = MagicMock(return_value=("Cutover approver is Li Qing.\nRollback owner is Zhou Yu.", sources))
    minimize = MagicMock(return_value=sources)

    def _unexpected(name: str):
        def _raiser(*args, **kwargs):
            raise AssertionError(f"{name} should not run for plain targeted-fact question")

        return _raiser

    monkeypatch.setattr(chat_service_module, "_maybe_answer_preview_from_sources", _unexpected("preview"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_targeted_fact_question_from_sources", targeted)
    monkeypatch.setattr(chat_service_module, "_maybe_repair_exact_terms_from_sources", _unexpected("exact"))
    monkeypatch.setattr(chat_service_module, "_minimize_sources_for_answer", minimize)
    monkeypatch.setattr(chat_service_module, "_maybe_expand_brief_answer_from_sources", _unexpected("brief expansion"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_boundary_from_sources", _unexpected("boundary"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_scope_definition_from_sources", _unexpected("scope"))
    monkeypatch.setattr(chat_service_module, "_maybe_merge_source_facts_from_sources", _unexpected("merge"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_summary_bundle_from_sources", _unexpected("summary"))

    question = "Who approves the cutover and who owns rollback?"
    answer, used_sources = chat_service_module._apply_source_answer_postprocessors(
        question,
        "The checklist names Li Qing and Zhou Yu.",
        sources,
    )

    assert answer == "Cutover approver is Li Qing.\nRollback owner is Zhou Yu."
    assert used_sources == sources
    targeted.assert_called_once_with(
        question,
        "The checklist names Li Qing and Zhou Yu.",
        sources,
    )
    minimize.assert_called_once_with(
        question,
        "Cutover approver is Li Qing.\nRollback owner is Zhou Yu.",
        sources,
    )



def test_apply_source_answer_postprocessors_keeps_single_question_cross_source_boundary_out_of_targeted_handler(chat_service_module, monkeypatch):
    """跨 source 的单一 boundary 问句应走 boundary/exact/minimize，不应误进 targeted handler。"""
    sources = [
        {"file": "folder-boundary.pdf", "text": "Knowledge Base remains the range and authorization boundary."},
        {"file": "scope-manual.pdf", "text": "requested_scope_type must remain single_kb."},
    ]
    boundary = MagicMock(return_value="Knowledge Base remains the range and authorization boundary.\nrequested_scope_type must remain single_kb.")
    exact = MagicMock(return_value="Knowledge Base remains the range and authorization boundary.\nrequested_scope_type must remain single_kb.")
    minimize = MagicMock(return_value=sources)

    def _unexpected(*args, **kwargs):
        raise AssertionError("targeted fact handler should not run for single-question cross-source boundary prompt")

    monkeypatch.setattr(chat_service_module, "_maybe_answer_boundary_from_sources", boundary)
    monkeypatch.setattr(chat_service_module, "_maybe_answer_targeted_fact_question_from_sources", _unexpected)
    monkeypatch.setattr(chat_service_module, "_maybe_repair_exact_terms_from_sources", exact)
    monkeypatch.setattr(chat_service_module, "_minimize_sources_for_answer", minimize)

    question = "Across the scope manual and the folder boundary note, what remains the authorization boundary rule?"
    answer, used_sources = chat_service_module._apply_source_answer_postprocessors(
        question,
        "The authorization boundary stays with the knowledge base.",
        sources,
    )

    assert "authorization boundary" in answer
    assert used_sources == sources
    boundary.assert_called_once_with(
        question,
        "The authorization boundary stays with the knowledge base.",
        sources,
    )
    exact.assert_called_once_with(
        question,
        "Knowledge Base remains the range and authorization boundary.\nrequested_scope_type must remain single_kb.",
        sources,
    )
    minimize.assert_called_once_with(
        question,
        "Knowledge Base remains the range and authorization boundary.\nrequested_scope_type must remain single_kb.",
        sources,
    )


def test_apply_source_answer_postprocessors_does_not_route_which_scope_targeted_fact_into_scope_handler(chat_service_module, monkeypatch):
    """带 which/scope 词面的 targeted-fact 问题，不应被 scope-definition handler 抢跑。"""
    sources = [
        {
            "file": "scope-manual.pdf",
            "text": "effective_kb_ids must echo the active PDF knowledge base.",
        },
        {
            "file": "folder-boundary.pdf",
            "text": "Knowledge Base remains the authorization boundary.",
        },
    ]
    preview = MagicMock(return_value="Preview guide fields repaired.")
    targeted = MagicMock(return_value=(
        "effective_kb_ids mirrors the chosen KB.\nKnowledge Base remains the authorization boundary.",
        sources,
    ))
    exact = MagicMock(return_value=
        "effective_kb_ids mirrors the chosen KB.\nKnowledge Base remains the authorization boundary."
    )
    minimize = MagicMock(return_value=sources)

    def _unexpected(name: str):
        def _raiser(*args, **kwargs):
            raise AssertionError(f"{name} should not run for targeted-fact question")

        return _raiser

    monkeypatch.setattr(chat_service_module, "_maybe_answer_targeted_fact_question_from_sources", targeted)
    monkeypatch.setattr(chat_service_module, "_maybe_repair_exact_terms_from_sources", exact)
    monkeypatch.setattr(chat_service_module, "_minimize_sources_for_answer", minimize)
    monkeypatch.setattr(chat_service_module, "_maybe_answer_preview_from_sources", _unexpected("preview"))
    monkeypatch.setattr(chat_service_module, "_maybe_expand_brief_answer_from_sources", _unexpected("brief expansion"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_boundary_from_sources", _unexpected("boundary"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_scope_definition_from_sources", _unexpected("scope"))
    monkeypatch.setattr(chat_service_module, "_maybe_merge_source_facts_from_sources", _unexpected("merge"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_summary_bundle_from_sources", _unexpected("summary"))

    question = "In the PDF scope manual, which field mirrors the chosen KB, and which boundary acts as the real permission wall?"
    answer, used_sources = chat_service_module._apply_source_answer_postprocessors(
        question,
        "The manual talks about scope.",
        sources,
    )

    assert answer == "effective_kb_ids mirrors the chosen KB.\nKnowledge Base remains the authorization boundary."
    assert used_sources == sources
    targeted.assert_called_once_with(
        question,
        "The manual talks about scope.",
        sources,
    )
    exact.assert_called_once_with(
        question,
        "effective_kb_ids mirrors the chosen KB.\nKnowledge Base remains the authorization boundary.",
        sources,
    )
    minimize.assert_called_once_with(
        question,
        "effective_kb_ids mirrors the chosen KB.\nKnowledge Base remains the authorization boundary.",
        sources,
    )


def test_apply_source_answer_postprocessors_does_not_route_and_what_targeted_fact_into_merge_handler(chat_service_module, monkeypatch):
    """带 and what 的 targeted-fact 问题，不应再被 multi-fact merge handler 抢跑。"""
    sources = [
        {
            "file": "preview-guide.pdf",
            "text": (
                "Every answer should carry doc_id and preview_locator. "
                "preview excerpt must resolve back to the original PDF chunk."
            ),
        }
    ]
    preview = MagicMock(return_value="Preview guide fields repaired.")
    targeted = MagicMock(return_value=(
        "Every answer should carry doc_id and preview_locator.\npreview excerpt must resolve back to the original PDF chunk.",
        sources,
    ))
    exact = MagicMock(return_value=
        "Every answer should carry doc_id and preview_locator.\npreview excerpt must resolve back to the original PDF chunk."
    )
    minimize = MagicMock(return_value=sources)

    def _unexpected(name: str):
        def _raiser(*args, **kwargs):
            raise AssertionError(f"{name} should not run for targeted-fact question")

        return _raiser

    monkeypatch.setattr(chat_service_module, "_maybe_answer_preview_from_sources", preview)
    monkeypatch.setattr(chat_service_module, "_maybe_answer_targeted_fact_question_from_sources", targeted)
    monkeypatch.setattr(chat_service_module, "_maybe_repair_exact_terms_from_sources", exact)
    monkeypatch.setattr(chat_service_module, "_minimize_sources_for_answer", minimize)
    monkeypatch.setattr(chat_service_module, "_maybe_expand_brief_answer_from_sources", _unexpected("brief expansion"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_boundary_from_sources", _unexpected("boundary"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_scope_definition_from_sources", _unexpected("scope"))
    monkeypatch.setattr(chat_service_module, "_maybe_merge_source_facts_from_sources", _unexpected("merge"))
    monkeypatch.setattr(chat_service_module, "_maybe_answer_summary_bundle_from_sources", _unexpected("summary"))

    question = "From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?"
    answer, used_sources = chat_service_module._apply_source_answer_postprocessors(
        question,
        "The preview guide mentions output fields.",
        sources,
    )

    assert answer == "Every answer should carry doc_id and preview_locator.\npreview excerpt must resolve back to the original PDF chunk."
    assert used_sources == sources
    preview.assert_called_once_with(
        question,
        "The preview guide mentions output fields.",
        sources,
    )
    targeted.assert_called_once_with(
        question,
        "Preview guide fields repaired.",
        sources,
    )
    exact.assert_called_once_with(
        question,
        "Every answer should carry doc_id and preview_locator.\npreview excerpt must resolve back to the original PDF chunk.",
        sources,
    )
    minimize.assert_called_once_with(
        question,
        "Every answer should carry doc_id and preview_locator.\npreview excerpt must resolve back to the original PDF chunk.",
        sources,
    )

def test_apply_source_answer_postprocessors_skips_brief_expansion_for_targeted_fact_brief_answer(chat_service_module, monkeypatch):
    """plain targeted-fact 短答案也应直接走 targeted handler，而不是 brief-expansion 或 exact repair。"""
    sources = [{"file": "cutover.md", "text": "Cutover approver is Li Qing. Rollback owner is Zhou Yu."}]
    targeted = MagicMock(return_value=("Cutover approver is Li Qing.\nRollback owner is Zhou Yu.", sources))
    minimize = MagicMock(return_value=sources)

    def _unexpected(*args, **kwargs):
        raise AssertionError("brief expansion or exact repair should not run for plain targeted-fact question")

    monkeypatch.setattr(chat_service_module, "_maybe_answer_targeted_fact_question_from_sources", targeted)
    monkeypatch.setattr(chat_service_module, "_maybe_repair_exact_terms_from_sources", _unexpected)
    monkeypatch.setattr(chat_service_module, "_minimize_sources_for_answer", minimize)
    monkeypatch.setattr(chat_service_module, "_maybe_expand_brief_answer_from_sources", _unexpected)

    question = "Who approves the cutover and who owns rollback?"
    answer, used_sources = chat_service_module._apply_source_answer_postprocessors(
        question,
        "Li Qing",
        sources,
    )

    assert answer == "Cutover approver is Li Qing.\nRollback owner is Zhou Yu."
    assert used_sources == sources
    targeted.assert_called_once_with(question, "Li Qing", sources)
    minimize.assert_called_once_with(question, "Cutover approver is Li Qing.\nRollback owner is Zhou Yu.", sources)



def test_apply_source_answer_postprocessors_skips_brief_expansion_for_summary_brief_answer(chat_service_module, monkeypatch):
    """summary 问题的短答案应交给 summary handler，而不是先被通用实体扩写改写。"""
    sources = [{"file": "handover.md", "text": "The handover summary keeps CAB sign-off, rollback owner, and escalation interval aligned."}]
    summary = MagicMock(return_value="The handover summary keeps CAB sign-off, rollback owner, and escalation interval aligned.")
    minimize = MagicMock(return_value=sources)

    def _unexpected(*args, **kwargs):
        raise AssertionError("brief expansion should not run for summary question")

    monkeypatch.setattr(chat_service_module, "_maybe_answer_summary_bundle_from_sources", summary)
    monkeypatch.setattr(chat_service_module, "_minimize_sources_for_answer", minimize)
    monkeypatch.setattr(chat_service_module, "_maybe_expand_brief_answer_from_sources", _unexpected)

    question = "Summarize the handover obligations in one sentence."
    answer, used_sources = chat_service_module._apply_source_answer_postprocessors(
        question,
        "Aligned",
        sources,
    )

    assert answer == "The handover summary keeps CAB sign-off, rollback owner, and escalation interval aligned."
    assert used_sources == sources
    summary.assert_called_once_with(question, "Aligned", sources)
    minimize.assert_called_once_with(
        question,
        "The handover summary keeps CAB sign-off, rollback owner, and escalation interval aligned.",
        sources,
    )



def test_targeted_fact_answer_prefers_approval_clause_over_signer_clause(chat_service_module):
    """approval 子问不应被另一个 signer 角色句抢走。"""
    question = (
        "Compare the Friday release cutover note and the vendor cutover checklist: "
        "who gives the final rollback approval and who signs the checklist before traffic moves to the vendor stack?"
    )
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        question,
        "",
        [
            {
                "file": "cutover.md",
                "text": (
                    "The Friday release cutover note explains who can approve rollback decisions.\n"
                    "The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence."
                ),
            },
            {
                "file": "vendor-cutover.pdf",
                "text": (
                    "Vendor cutover checklist. "
                    "The customer success lead signs the cutover checklist before traffic moves to the vendor stack."
                ),
            },
        ],
    )

    assert "platform duty lead" in answer.lower()
    assert "customer success lead" in answer.lower()
    assert [source["file"] for source in used_sources] == ["cutover.md", "vendor-cutover.pdf"]



def test_targeted_fact_answer_keeps_adjacent_same_source_context(chat_service_module):
    """同一 source 两个命中点只隔一行时，应补回中间流程说明。"""
    question = "For the handover window scanned PDF fixture, what must OCR fallback do and what should the scanned content become?"
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        question,
        "",
        [
            {
                "file": "scan-fallback.pdf",
                "text": (
                    "handover window 扫描页没有文字层时，OCR fallback must merge every predict batch for the same page.\n"
                    "中文流程说明也要写回当前知识库，避免导入后只剩图片像素。\n"
                    "Scanned PDF content should still become searchable evidence in the active knowledge base."
                ),
            }
        ],
    )

    assert "OCR fallback must merge every predict batch for the same page" in answer
    assert "中文流程说明也要写回当前知识库" in answer
    assert "searchable evidence in the active knowledge base" in answer
    assert [source["file"] for source in used_sources] == ["scan-fallback.pdf"]
    assert "中文流程说明也要写回当前知识库" in used_sources[0]["text"]



def test_query_expands_brief_entity_answer_with_grounded_source_clause(chat_service_module, monkeypatch, single_kb_scope):
    """\u5f53\u6765\u6e90\u91cc\u6709\u76f4\u63a5\u652f\u6491\u5b50\u53e5\u65f6\uff0c\u5e94\u628a\u5b64\u7acb\u540d\u8bcd\u8865\u6210\u6700\u5c0f\u5b8c\u6574\u53e5\u3002"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="\u77e5\u8bc6\u5e93")
    sources = [
        {
            "file": "diag-import-utf8.md",
            "text": "\u6587\u6863\u660e\u786e\u8bf4\u660e\uff1a\u77e5\u8bc6\u5e93\u4ecd\u7136\u662f\u6388\u6743\u8fb9\u754c\uff0c\u6587\u4ef6\u5939\u53ea\u627f\u62c5\u7ec4\u7ec7\u4f5c\u7528\uff0c\u4e0d\u627f\u62c5\u6743\u9650\u9694\u79bb\u3002",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="\u8bca\u65ad\u6587\u6863\u91cc\uff0c\u4ec0\u4e48\u5bf9\u8c61\u4ecd\u7136\u662f\u6388\u6743\u8fb9\u754c\uff1f"),
        record_history=False,
    )

    assert result["answer"] == "\u77e5\u8bc6\u5e93\u4ecd\u7136\u662f\u6388\u6743\u8fb9\u754c\u3002"


def test_query_expands_brief_answer_with_grounded_pdf_clause(chat_service_module, monkeypatch, single_kb_scope):
    """短答案命中 PDF/OCR 证据子句时，仍应扩写成最小完整句。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="OCR fallback")
    sources = [
        {
            "file": "scan-fallback.pdf",
            "text": "OCR fallback must merge every predict batch for the same page. Scanned PDF content should still become searchable evidence in the active knowledge base.",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="In the scanned PDF note, what must OCR fallback do for the same page?"),
        record_history=False,
    )

    assert result["answer"] == "OCR fallback must merge every predict batch for the same page."


def test_query_expands_brief_answer_with_grounded_image_ocr_clause(chat_service_module, monkeypatch, single_kb_scope):
    """图片 OCR 来源也应复用 source-backed 短答案补全策略。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="Knowledge Base")
    sources = [
        {
            "file": "folder-board.png",
            "text": "Knowledge Base is the authorization boundary for image OCR answers. Folder remains organization only.",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="According to the OCR image, what remains the authorization boundary?"),
        record_history=False,
    )

    assert result["answer"] == "Knowledge Base is the authorization boundary for image OCR answers."


def test_query_answers_boundary_from_ocr_source_sentences(chat_service_module, monkeypatch, single_kb_scope):
    """边界类 OCR 问题应保留 source 中 folder / knowledge base 原句。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text=(
            "The folder is the organization's property and the knowledge base is the authorization boundary."
        ),
    )
    sources = [
        {
                "file": "diag-ocr.png",
                "text": (
                    "Image OCRdiagnostic\n"
                    "Folder is organization only\n"
                    "Knowledge Base is the authorization boundary\n"
                    "Preview should resolve to OCRchunk"
                ),
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What does the OCR diagnostic document say about folder and knowledge base boundaries?"),
        record_history=False,
    )

    assert result["answer"] == (
        "Folder is for organization only. Knowledge Base is the authorization boundary."
    )


def test_query_answers_boundary_from_chinese_source_sentence(chat_service_module, monkeypatch, single_kb_scope):
    """中文边界问题应优先保留 source 中的授权边界和组织作用表述。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="知识库在文件夹边界内，文件夹负责组织。",
    )
    sources = [
        {
            "file": "diag-import-utf8.md",
            "text": "知识库仍然是授权边界，文件夹只承担组织作用，不承担权限隔离。",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="这份 UTF-8 诊断文档如何描述知识库和文件夹的边界？"),
        record_history=False,
    )

    assert result["answer"] == "知识库仍然是授权边界，文件夹只承担组织作用，不承担权限隔离。"


def test_query_answers_boundary_from_ref_doc_when_source_chunk_is_truncated(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """当检索 chunk 截断边界原句时，应从同一 ref doc 回看完整文本。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="文档明确说明：知识库仍然是授。",
    )
    sources = [
        {
            "file": "diag-import-utf8.md",
            "kb_id": "kb-a",
            "doc_id": "doc-1",
            "text": "Markdown 诊断文档。\n\n文档明确说明：知识库仍然是授",
        }
    ]
    document = SimpleNamespace(text="# UTF-8 诊断知识库\n\n知识库仍然是授权边界，文件夹只承担组织作用，不承担权限隔离。\n")
    doc_store = SimpleNamespace(get_document=MagicMock(return_value=document))
    manager = SimpleNamespace(storage_context=SimpleNamespace(docstore=doc_store))

    monkeypatch.setattr(chat_service_module.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="这份 UTF-8 诊断文档如何描述知识库和文件夹的边界？"),
        record_history=False,
    )

    assert result["answer"] == "知识库仍然是授权边界，文件夹只承担组织作用，不承担权限隔离。"


def test_query_answers_boundary_scope_from_utf16_source_sentence(chat_service_module, monkeypatch, single_kb_scope):
    """UTF-16 边界问句应从 source 中回到完整授权边界原句。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="Knowledge Base remains the authorization.")
    sources = [
        {
            "file": "README-UTF16",
            "text": "Knowledge Base remains the authorization boundary.\nFolder is organization only.",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What exact sentence does the UTF-16 README use to describe the authorization boundary?"),
        record_history=False,
    )

    assert result["answer"] == "Knowledge Base remains the authorization boundary."


def test_query_answers_boundary_from_ref_doc_when_question_mentions_only_authorization_boundary(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """只问 authorization boundary 时，也应从完整 ref doc 补齐被截断的 UTF-16 原句。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Knowledge Base remains the authorization.",
    )
    sources = [
        {
            "file": "README-UTF16",
            "kb_id": "kb-a",
            "doc_id": "doc-utf16",
            "text": "Knowledge Base remains the authorization",
        }
    ]
    document = SimpleNamespace(
        text="Knowledge\x00 Base\x00 remains\x00 the\x00 authorization\x00 boundary\x00.\nFolder is organization only."
    )
    doc_store = SimpleNamespace(get_document=MagicMock(return_value=document))
    manager = SimpleNamespace(storage_context=SimpleNamespace(docstore=doc_store))

    monkeypatch.setattr(chat_service_module.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What does the UTF-16 README say about the authorization boundary?"),
        record_history=False,
    )

    assert result["answer"] == "Knowledge Base remains the authorization boundary."


@pytest.mark.parametrize(
    ("question", "answer_text", "sources", "required_terms"),
    [
        (
            "Across the workflow boundary note and the folder boundary model, what remains the authorization boundary?",
            (
                "workflow-boundary.md: Folder path is not an authorization boundary. "
                "Query scope and access control remain at the knowledge base level. "
                "folder-boundary.md: Folders are organizational objects inside one knowledge base."
            ),
            [
                {
                    "file": "workflow-boundary.md",
                    "text": (
                        "Folder path is not an authorization boundary. "
                        "Query scope and access control remain at the knowledge base level."
                    ),
                },
                {
                    "file": "folder-boundary.md",
                    "text": "Folders are organizational objects inside one knowledge base.",
                },
            ],
            ("knowledge base", "authorization boundary"),
        ),
        (
            "Across the scope manual and the folder boundary note, what remains the authorization boundary rule?",
            (
                "folder-boundary.pdf: Knowledge Base remains the range and authorization boundary. "
                "scope-manual.pdf: requested_scope_type must remain single_kb."
            ),
            [
                {
                    "file": "folder-boundary.pdf",
                    "text": "Knowledge Base remains the range and authorization boundary.",
                },
                {
                    "file": "scope-manual.pdf",
                    "text": "requested_scope_type must remain single_kb.",
                },
            ],
            ("single_kb", "authorization boundary"),
        ),
    ],
)
def test_query_preserves_complete_grounded_multi_source_boundary_answer(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
    question,
    answer_text,
    sources,
    required_terms,
):
    """多来源原答已覆盖边界锚点时，不应被压缩到丢失 knowledge base/single_kb。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text=answer_text)
    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(_build_request(question=question), record_history=False)

    for term in required_terms:
        assert term.lower() in result["answer"].lower()


def test_query_answers_scope_definition_from_source_sentence(chat_service_module, monkeypatch, single_kb_scope):
    """范围/定义类问题应优先返回完整定义句。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="非直属企业适用于收储库点。")
    sources = [
        {
            "file": "一卡通.docx",
            "text": "非直属企业是指中储粮直属企业以外的参与中央事权粮食入库和出库业务的收储库点（包括租仓库点、委托库点）。",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="非直属企业“一卡通”系统适用于哪些收储库点？"),
        record_history=False,
    )

    assert "租仓库点" in result["answer"]
    assert "委托库点" in result["answer"]


def test_query_answers_scope_definition_from_ref_doc_when_retrieved_chunk_is_incomplete(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """范围问题的检索 chunk 不完整时，应回看 ref doc 并保留括号中的完整适用库点。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="非(sqrt)企业‘一卡通’系统适用于中储粮非(sqrt)企业中的收储库点。",
    )
    sources = [
        {
            "file": "一卡通.docx",
            "kb_id": "kb-a",
            "doc_id": "one-card-doc",
            "text": "非直属企业中的收储库点。",
        }
    ]
    document = SimpleNamespace(
        text=(
            "第二条 非直属企业是指中储粮直属企业以外的参与中央事权粮食入库和出库业务的"
            "收储库点（包括租仓库点、委托库点），其在入库和出库业务中必须使用一卡通系统。"
        )
    )
    doc_store = SimpleNamespace(get_document=MagicMock(return_value=document))
    manager = SimpleNamespace(storage_context=SimpleNamespace(docstore=doc_store))

    monkeypatch.setattr(chat_service_module.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="非直属企业‘一卡通’系统适用于哪些收储库点？"),
        record_history=False,
    )

    assert "中央事权粮食入库和出库业务" in result["answer"]
    assert "租仓库点" in result["answer"]
    assert "委托库点" in result["answer"]


def test_query_merges_multi_fact_answer_from_sources(chat_service_module, monkeypatch, single_kb_scope):
    """一问两事实时，服务端应能合并来自不同 source 的最小完整句。"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="Every evidence preview should include doc_id.")
    sources = [
        {
            "file": "cutover.md",
            "text": "The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence.",
        },
        {
            "file": "preview-board.png",
            "text": "Every evidence preview must include doc_id and preview_locator.",
        },
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="In one answer, tell me who gives the final rollback approval and what every evidence preview should include."),
        record_history=False,
    )

    assert "platform duty lead" in result["answer"]
    assert "final rollback approval" in result["answer"]
    assert "doc_id" in result["answer"]
    assert "preview_locator" in result["answer"]


def test_query_merges_best_multi_fact_sentences_when_preview_source_has_heading(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """多事实合并应跳过 preview 标题和泛化说明，选择各子问题最完整的事实句。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Every evidence preview must include doc_id and preview_locator.",
    )
    sources = [
        {
            "file": "preview-board.png",
            "text": "Evidence preview checklist\nEvery evidence preview must include doc_id and preview_locator",
        },
        {
            "file": "cutover.md",
            "text": (
                "The Friday release cutover note explains who can approve rollback decisions.\n"
                "The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence."
            ),
        },
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="In one answer, tell me who gives the final rollback approval and what every evidence preview should include."),
        record_history=False,
    )

    assert "platform duty lead" in result["answer"]
    assert "final rollback approval" in result["answer"]
    assert "doc_id" in result["answer"]
    assert "preview_locator" in result["answer"]
    assert "checklist" not in result["answer"].lower()


def test_query_merges_boundary_and_preview_facts_for_compare_question(
    chat_service_module,
    monkeypatch,
    single_kb_scope,
):
    """compare 问题使用 and does 连接两个子问题时，也应合并边界和 preview 事实。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Evidence preview checklist.",
    )
    sources = [
        {
            "file": "escalation-board.png",
            "text": "Knowledge Base is the authorization boundary. Folder remains organization only.",
        },
        {
            "file": "preview-board.png",
            "text": "Evidence preview checklist. Every evidence preview must include doc_id and preview_locator.",
        },
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(
            question=(
                "Compare the escalation board image and the evidence preview board: "
                "what remains the authorization boundary, and does the preview board "
                "explicitly require doc_id and preview_locator?"
            )
        ),
        record_history=False,
    )

    assert "knowledge base" in result["answer"].lower()
    assert "authorization boundary" in result["answer"].lower()
    assert "doc_id" in result["answer"]
    assert "preview_locator" in result["answer"]


def test_query_expands_brief_preview_answer_from_source(chat_service_module, monkeypatch, single_kb_scope):
    """preview 问题短答偏到同源 passcode 时，应优先回到 preview 原句。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="The unique desktop workflow passcode is northagent-desktop-e2e-1786353063.",
    )
    sources = [
        {
            "file": "desktop-model-workflow.md",
            "text": (
                "The unique desktop workflow passcode is northagent-desktop-e2e-1786353063. "
                "Evidence preview must resolve this file after chat returns sources."
            ),
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What should evidence preview resolve after chat returns sources?"),
        record_history=False,
    )

    assert result["answer"] == "Evidence preview must resolve this file after chat returns sources."


def test_query_answers_markdown_table_fields_from_sources(chat_service_module, monkeypatch, single_kb_scope):
    """表格字段问答应优先使用 source 中的 Markdown 表格原值。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="推荐 kb_id: `grain-knowledge-base`，主要格式: `text(markdown)`",
    )
    sources = [
        {
            "file": "readme.md",
            "text": "\n".join(
                [
                    "| 字段 | 内容 |",
                    "|---|---|",
                    "| 推荐 kb_id | `grain-knowledge-base` |",
                    "| 主要语言 | 中文 |",
                    "| 主要格式 | `.pdf` 157 个，`.docx` 98 个 |",
                    "| 总体量 | 775744.1 KB |",
                ]
            ),
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="粮仓知识库 README 的基本信息表里，推荐 kb_id 和主要格式分别是什么？"),
        record_history=False,
    )

    assert "推荐 kb_id是 grain-knowledge-base" in result["answer"]
    assert "主要格式是 .pdf 157 个，.docx 98 个" in result["answer"]


def test_query_repairs_exact_hyphenated_passcode_from_sources(chat_service_module, monkeypatch, single_kb_scope):
    """模型改写唯一 passcode 时，应从 source 补回精确保真 token。"""

    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="The unique desktop workflow passcode is northagent desktop-e2e-1786353063.",
    )
    sources = [
        {
            "file": "desktop-model-workflow.md",
            "text": "The unique desktop workflow passcode is northagent-desktop-e2e-1786353063.",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What is the unique desktop workflow passcode in the diagnostic document?"),
        record_history=False,
    )

    assert result["answer"] == "The unique desktop workflow passcode is northagent-desktop-e2e-1786353063."


def test_query_repairs_exact_ocr_fallback_phrase_from_sources(chat_service_module, monkeypatch, single_kb_scope):
    """模型把 OCR fallback 粘连时，应从 source 补回精确短语。"""

    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Scanned PDF diagnostic says that OCRfallback must merge every predict batch per page.",
    )
    sources = [
        {
            "file": "diag-scan-fallback.pdf",
            "text": "Scanned PDF diagnostic says that OCR fallback must merge every predict batch per page.",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What does the scanned PDF diagnostic say about OCR fallback?"),
        record_history=False,
    )

    assert result["answer"] == "Scanned PDF diagnostic says that OCR fallback must merge every predict batch per page."


def test_query_repairs_preview_exact_phrase_from_sources(chat_service_module, monkeypatch, single_kb_scope):
    """模型把 this 改成 the 时，应从 source 补回 evidence preview 原句。"""

    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Evidence preview should resolve the file after chat returns sources.",
    )
    sources = [
        {
            "file": "desktop-model-workflow.md",
            "text": "Evidence preview should resolve this file after chat returns sources.",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What should evidence preview resolve after chat returns sources?"),
        record_history=False,
    )

    assert result["answer"] == "Evidence preview should resolve this file after chat returns sources."


def test_query_repairs_preview_field_tokens_from_sources(chat_service_module, monkeypatch, single_kb_scope):
    """模型漏掉 doc_id/preview_locator 时，应从 source 补回精确字段名。"""

    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Evidence preview checklist.",
    )
    sources = [
        {
            "file": "preview-board.png",
            "text": "Every evidence preview must include doc_id and preview_locator.",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="What should every evidence preview include?"),
        record_history=False,
    )

    assert result["answer"] == "Every evidence preview must include doc_id and preview_locator."


def test_query_repairs_chinese_storage_scope_phrase_from_sources(chat_service_module, monkeypatch, single_kb_scope):
    """中文 source 精确范围短语被模型泛化时，应补回来源原词。"""

    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="《粮油安全储存守则》适用于所有粮油仓储单位。",
    )
    sources = [
        {
            "file": "AAA粮油安全储存守则_0119014f.docx",
            "text": "《粮油安全储存守则》适用于各类粮油仓储单位。",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="《粮油安全储存守则》适用于哪些单位？"),
        record_history=False,
    )

    assert result["answer"] == "《粮油安全储存守则》适用于各类粮油仓储单位。"


def test_query_keeps_brief_answer_when_source_lacks_grounded_clause(chat_service_module, monkeypatch, single_kb_scope):
    """\u5f53\u6765\u6e90\u91cc\u6ca1\u6709\u53ef\u76f4\u63a5\u652f\u6491\u7684\u5b50\u53e5\u65f6\uff0c\u4e0d\u5e94\u5f3a\u884c\u6269\u5199\u77ed\u7b54\u6848\u3002"""
    _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="\u77e5\u8bc6\u5e93")
    sources = [
        {
            "file": "kb-overview.md",
            "text": "\u77e5\u8bc6\u5e93\u76ee\u5f55\u5305\u542b\u591a\u4e2a\u6587\u4ef6\u5939\uff0c\u7528\u4e8e\u7ec4\u7ec7\u5bfc\u5165\u6587\u4ef6\u4e0e\u8d44\u4ea7\u3002",
        }
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(question="\u8bca\u65ad\u6587\u6863\u91cc\uff0c\u4ec0\u4e48\u5bf9\u8c61\u4ecd\u7136\u662f\u6388\u6743\u8fb9\u754c\uff1f"),
        record_history=False,
    )

    assert result["answer"] == "\u77e5\u8bc6\u5e93"


def test_get_history_delegates_to_session_store(chat_service_module, monkeypatch):
    """get_history 应直接透传会话存储结果。"""
    list_chat_messages = MagicMock(return_value=[{"role": "user", "content": "hello"}])
    monkeypatch.setattr(chat_service_module, "list_chat_messages", list_chat_messages)

    assert chat_service_module.get_history("session-1") == [{"role": "user", "content": "hello"}]
    list_chat_messages.assert_called_once_with("session-1")


def test_clear_history_delegates_to_session_store(chat_service_module, monkeypatch):
    """clear_history 应直接调用会话存储清理。"""
    clear_chat_messages = MagicMock()
    monkeypatch.setattr(chat_service_module, "clear_chat_messages", clear_chat_messages)

    chat_service_module.clear_history("session-2")

    clear_chat_messages.assert_called_once_with("session-2")


def test_build_history_grounded_question_skips_history_for_standalone_question(chat_service_module, monkeypatch):
    """非 follow-up 问题不应为了历史注入而读取 session 对话。"""
    list_chat_messages = MagicMock(return_value=[{"role": "user", "content": "Tell me about the rollback packet."}])
    monkeypatch.setattr(chat_service_module, "list_chat_messages", list_chat_messages)

    question = "Who approves the rollback packet?"
    assert chat_service_module._build_history_grounded_question(question, "session-standalone") == question
    list_chat_messages.assert_not_called()


def test_build_history_grounded_question_skips_history_for_short_identifier_fragment(chat_service_module, monkeypatch):
    """短字段问句若本身就是 identifier-like，不应再误判成 follow-up 并注入历史。"""
    list_chat_messages = MagicMock(return_value=[{"role": "user", "content": "Tell me about the payroll cutover."}])
    monkeypatch.setattr(chat_service_module, "list_chat_messages", list_chat_messages)

    question = "CAB ticket?"
    assert chat_service_module._build_history_grounded_question(question, "session-identifier") == question
    list_chat_messages.assert_not_called()


def test_build_history_grounded_question_injects_recent_session_context(chat_service_module, monkeypatch):
    """follow-up 问题应注入同 session 的最近上下文。"""
    history = [
        {"role": "user", "content": "Tell me about the rollback packet."},
        {"role": "assistant", "content": "The rollback packet stays inside one knowledge base and must stay traceable."},
    ]
    list_chat_messages = MagicMock(return_value=history)
    monkeypatch.setattr(chat_service_module, "list_chat_messages", list_chat_messages)

    grounded = chat_service_module._build_history_grounded_question("Who approves it?", "session-follow-up")

    assert grounded.startswith("Conversation context from the same session:")
    assert "User: Tell me about the rollback packet." in grounded
    assert "Assistant: The rollback packet stays inside one knowledge base and must stay traceable." in grounded
    assert "Current question: Who approves it?" in grounded
    list_chat_messages.assert_called_once_with("session-follow-up")


def test_query_follow_up_without_history_falls_back_to_raw_question(chat_service_module, monkeypatch, single_kb_scope):
    """follow-up 问题若 session 没有可用历史，应回退为原始问句。"""
    engine, _ = _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="Release Manager Li Qing.")
    monkeypatch.setattr(chat_service_module, "list_chat_messages", MagicMock(return_value=[]))
    monkeypatch.setattr(
        chat_service_module,
        "_normalize_sources",
        MagicMock(return_value=[{"file": "rollback-packet.md", "text": "Release Manager Li Qing approves the rollback packet."}]),
    )
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    chat_service_module.query(_build_request(question="Who approves it?"), record_history=False)

    engine.query.assert_called_once_with("Who approves it?")


def test_query_short_identifier_fragment_does_not_use_history_grounding(chat_service_module, monkeypatch, single_kb_scope):
    """短 identifier-like 问句即使 session 有历史，也应保持 raw question，避免误绑上一轮实体。"""
    engine, _ = _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="No confirmable information is available.")
    monkeypatch.setattr(
        chat_service_module,
        "list_chat_messages",
        MagicMock(
            return_value=[
                {"role": "user", "content": "Tell me about the payroll cutover."},
                {"role": "assistant", "content": "The rollback owner is Zhou Yu."},
            ]
        ),
    )
    monkeypatch.setattr(
        chat_service_module,
        "_normalize_sources",
        MagicMock(return_value=[{"file": "payroll-cutover.md", "text": "No CAB ticket number is listed."}]),
    )
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    chat_service_module.query(_build_request(question="CAB ticket?"), record_history=False)

    engine.query.assert_called_once_with("CAB ticket?")


def test_query_uses_history_grounded_question_for_follow_up(chat_service_module, monkeypatch, single_kb_scope):
    """follow-up 问答应把最近 session 上下文注入检索问句。"""
    engine, _ = _stub_query_runtime(chat_service_module, monkeypatch, single_kb_scope, answer_text="Release Manager Li Qing.")
    history = [
        {"role": "user", "content": "Tell me about the rollback packet."},
        {"role": "assistant", "content": "The rollback packet stays inside one knowledge base and must stay traceable."},
    ]
    list_chat_messages = MagicMock(return_value=history)
    monkeypatch.setattr(chat_service_module, "list_chat_messages", list_chat_messages)
    monkeypatch.setattr(
        chat_service_module,
        "_normalize_sources",
        MagicMock(return_value=[{"file": "rollback-packet.md", "text": "Release Manager Li Qing approves the rollback packet."}]),
    )
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(_build_request(question="Who approves it?"), record_history=False)

    assert result["answer"] == "Release Manager Li Qing."
    grounded_question = engine.query.call_args.args[0]
    assert grounded_question.startswith("Conversation context from the same session:")
    assert "Tell me about the rollback packet." in grounded_question
    assert "Current question: Who approves it?" in grounded_question
    list_chat_messages.assert_called_once_with("chat-service-test")


def test_query_follow_up_semireal_can_recover_subject_from_same_session(chat_service_module, monkeypatch, single_kb_scope, tmp_path):
    """疑似 follow-up 问题应能利用同 session 历史恢复被省略主语。"""
    from tests.api._semireal_chat_support import SemirealIndexManager, SemirealQueryEngine

    manager = SemirealIndexManager("kb-a", tmp_path)
    manager.register_text_document(
        path=tmp_path / "rollback-packet.md",
        text="Rollback packet owner: Release Manager Li Qing. Preview evidence stays traceable inside one knowledge base.",
        kb_id="kb-a",
    )

    monkeypatch.setattr(chat_service_module, "resolve_chat_query_scope", MagicMock(return_value=single_kb_scope))
    monkeypatch.setattr(chat_service_module.runtime_state, "ensure_index_loaded", MagicMock(return_value=True))
    monkeypatch.setattr(
        chat_service_module.runtime_state,
        "build_query_engine",
        MagicMock(return_value=SemirealQueryEngine(manager)),
    )
    monkeypatch.setattr(
        chat_service_module,
        "list_chat_messages",
        MagicMock(
            return_value=[
                {"role": "user", "content": "Tell me about the rollback packet."},
                {"role": "assistant", "content": "It is the release artifact that must stay traceable."},
            ]
        ),
    )
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(_build_request(question="Who is it?"), record_history=False)

    assert "Li Qing" in result["answer"]
    assert result["sources"]
    assert result["sources"][0]["file"] == "rollback-packet.md"



def test_build_refusal_answer_uses_pdf_specific_copy(chat_service_module):
    """PDF 拒答文案应保留 current KB 约束，同时强调 active PDF knowledge base。"""
    assert chat_service_module._build_refusal_answer("What checksum token is listed in the PDF release checklist?") == (
        "No confirmable information is available in the current knowledge base. "
        "Please answer from the active PDF knowledge base only."
    )


def test_build_refusal_answer_uses_pdf_scope_copy_for_generic_question(chat_service_module, monkeypatch):
    """即使问题文本没写 PDF，只要 active KB 实际是 PDF，也应输出 PDF-specific refusal wording。"""
    pdf_scope = ChatQueryScope(
        requested_scope_type="single_kb",
        requested_kb_ids=["eval-kb-pdf"],
        effective_scope_type="single_kb",
        effective_kb_ids=["eval-kb-pdf"],
        is_default_deny_applied=False,
        isolation_level="physical_isolated",
    )
    monkeypatch.setattr(
        chat_service_module.kb_service,
        "list_docs",
        MagicMock(return_value=[{"name": "war-room-handover-business.pdf"}, {"name": "refusal-rule.pdf"}]),
    )

    assert chat_service_module._build_refusal_answer("What pager rotation id does it list?", pdf_scope) == (
        "No confirmable information is available in the current knowledge base. "
        "Please answer from the active PDF knowledge base only."
    )


def test_targeted_fact_answer_prunes_same_document_noise(chat_service_module):
    """同一文档多字段问题应只保留被问到的事实，不混入 rollback owner/截止时间噪声。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "In the payroll cutover approval matrix, who is the final approver and who is the business confirmer?",
        (
            "- Final approver: Release Manager Li Qing.\n"
            "- Rollback owner: Platform SRE Wang Lei.\n"
            "- Business confirmer: Finance Ops Zhou Yu.\n"
            "- Checklist must be signed before 22:30 Beijing time."
        ),
        [
            {
                "file": "cutover-approval.md",
                "text": (
                    "# Payroll Cutover Approval Matrix\n\n"
                    "- Final approver: Release Manager Li Qing.\n"
                    "- Rollback owner: Platform SRE Wang Lei.\n"
                    "- Business confirmer: Finance Ops Zhou Yu.\n"
                    "- Checklist must be signed before 22:30 Beijing time."
                ),
            }
        ],
    )

    assert "Li Qing" in answer
    assert "Zhou Yu" in answer
    assert "Wang Lei" not in answer
    assert "22:30" not in answer
    assert [source["file"] for source in used_sources] == ["cutover-approval.md"]


def test_query_targeted_fact_answer_merges_cross_source_values(chat_service_module, monkeypatch, single_kb_scope):
    """跨 source 的 deadline/interval 问题应补齐另一侧证据，并压掉 first-ack 噪声。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text=(
            "- P1 cutover incident must be escalated to on-call manager Zhao Lin within 15 minutes.\n"
            "- Service desk first-ack SLA is 5 minutes."
        ),
    )
    current_sources = [
        {
            "file": "handover-sla.md",
            "text": (
                "P1 cutover incident must be escalated to on-call manager Zhao Lin within 15 minutes. "
                "Service desk first-ack SLA is 5 minutes."
            ),
        }
    ]
    extra_sources = [
        {
            "file": "handover-sla.md",
            "text": current_sources[0]["text"],
        },
        {
            "file": "cutover-approval.md",
            "text": "Checklist must be signed before 22:30 Beijing time.",
        },
    ]

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=current_sources))
    monkeypatch.setattr(chat_service_module, "_collect_candidate_sources_for_question", MagicMock(return_value=extra_sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(
            question="Across the approval matrix and the handover SLA, which value is a sign deadline and which is an escalation interval?"
        ),
        record_history=False,
    )

    assert "22:30 Beijing time" in result["answer"]
    assert "15 minutes" in result["answer"]
    assert "first-ack" not in result["answer"].lower()
    assert [source["file"] for source in result["sources"]] == ["cutover-approval.md", "handover-sla.md"]


def test_query_targeted_fact_answer_prefers_literal_path_source(chat_service_module, monkeypatch, single_kb_scope):
    """问题显式点名 cutover/runbook/ 时，应优先命中字面路径来源而不是泛化 folder 文档。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text="Folders are organizational objects inside one knowledge base.",
    )
    monkeypatch.setattr(
        chat_service_module,
        "_normalize_sources",
        MagicMock(
            return_value=[
                {
                    "file": "folder-boundary.md",
                    "text": (
                        "Folders are organizational objects inside one knowledge base. "
                        "They do not create a separate authorization boundary."
                    ),
                }
            ]
        ),
    )
    monkeypatch.setattr(
        chat_service_module,
        "_collect_candidate_sources_for_question",
        MagicMock(
            return_value=[
                {
                    "file": "workflow-boundary.md",
                    "text": (
                        "Folder path `cutover/runbook/` is an internal organization path, not an authorization boundary. "
                        "Query scope and access control remain at the knowledge base level."
                    ),
                }
            ]
        ),
    )
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())

    result = chat_service_module.query(
        _build_request(
            question="Does folder path cutover/runbook/ create a separate authorization boundary, or does access control stay at the knowledge-base level?"
        ),
        record_history=False,
    )

    assert "cutover/runbook/" in result["answer"]
    assert "knowledge base level" in result["answer"].lower()
    assert [source["file"] for source in result["sources"]] == ["workflow-boundary.md"]


def test_targeted_fact_answer_adds_no_confirmable_anchor_for_negative_contract(chat_service_module):
    """弱证据负向契约问题应显式带出 No confirmable information 锚点。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "When OCR evidence is sparse on the noisy policy board, may the assistant rely on fabricated memory, or must it stay inside the active knowledge base?",
        "active knowledge base only.\nno fabricated memory.",
        [
            {
                "file": "noisy-policy-board.png",
                "text": "low contrast OCR fallback. no confirmable information. active knowledge base only. no fabricated memory.",
            }
        ],
    )

    assert "no confirmable information" in answer.lower()
    assert "active knowledge base only" in answer.lower()
    assert "no fabricated memory" in answer.lower()
    assert [source["file"] for source in used_sources] == ["noisy-policy-board.png"]

def test_split_targeted_fact_question_strips_shared_prefixes(chat_service_module):
    """Compare/On/In 等共享前缀应被裁掉，避免把别的 board 描述误当成子问题条件。"""
    question = "Compare the approval whiteboard and the escalation whiteboard: who is the final approver and who handles P1 escalation?"

    parts = chat_service_module._split_targeted_fact_question(question)

    assert parts == ["who is the final approver", "who handles P1 escalation"]
    assert chat_service_module._score_targeted_answer_candidate(question, parts[0], "Final approver Zhao Lin.") is not None



def test_targeted_fact_answer_collects_both_scope_alignment_id_fields(chat_service_module):
    """scope-contract 的“两个 id 字段”问题应显式列出 requested_kb_ids 与 effective_kb_ids。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "Under the single KB scope contract, can the effective scope expand beyond the requested KB, and which two id fields should stay aligned with the request?",
        "The effective scope must stay inside the explicitly requested knowledge base.\nSingle-kb chat responses must echo the following fields exactly.",
        [
            {
                "file": "scope-contract.md",
                "text": (
                    "Single-kb chat responses must echo the following fields exactly:\n"
                    "- requested_scope_type\n"
                    "- requested_kb_ids\n"
                    "- effective_scope_type\n"
                    "- effective_kb_ids\n"
                    "- is_default_deny_applied\n"
                    "- isolation_level\n\n"
                    "The effective scope must stay inside the explicitly requested knowledge base."
                ),
            }
        ],
    )

    assert "explicitly requested knowledge base" in answer
    assert "requested_kb_ids" in answer
    assert "effective_kb_ids" in answer
    assert [source["file"] for source in used_sources] == ["scope-contract.md"]



def test_targeted_fact_answer_keeps_single_kb_for_pdf_scope_contract(chat_service_module):
    """PDF scope contract 问题应同时回显 effective_kb_ids 与 single_kb。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "In the PDF scope contract, which response field should echo the active PDF knowledge base, and what scope type must remain in force?",
        "effective_kb_ids must echo the active PDF knowledge base.\nExternal agents must stay inside the declared knowledge scope.",
        [
            {
                "file": "scope-manual.pdf",
                "text": (
                    "Scope contract for PDF knowledge base queries.\n"
                    "requested_scope_type must remain single_kb.\n"
                    "effective_kb_ids must echo the active PDF knowledge base.\n"
                    "isolation_level remains physical_isolated in the current architecture."
                ),
            }
        ],
    )

    assert "effective_kb_ids" in answer
    assert "single_kb" in answer
    assert [source["file"] for source in used_sources] == ["scope-manual.pdf"]



def test_targeted_fact_answer_prefers_workflow_permission_wall_over_folder_noise(chat_service_module):
    """workflow note 的 permission wall 问题应回到 knowledge base level，而不是泛化成 folder boundary。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "In the workflow note, what is the real permission wall, and what thing is only an internal filing path?",
        "Folder path `cutover/runbook/` is an internal organization path, not an authorization boundary.\nFolders are organizational objects inside one knowledge base.",
        [
            {
                "file": "workflow-boundary.md",
                "text": (
                    "Folder path `cutover/runbook/` is an internal organization path, not an authorization boundary.\n"
                    "Query scope and access control remain at the knowledge base level.\n"
                    "Evidence preview must include doc_id and preview_locator."
                ),
            }
        ],
    )

    assert "knowledge base level" in answer.lower()
    assert "cutover/runbook/" in answer
    assert [source["file"] for source in used_sources] == ["workflow-boundary.md"]



def test_targeted_fact_answer_prefers_evidence_contract_over_unrelated_escalation_noise(chat_service_module):
    """evidence board 问题应只保留 doc_id/preview_locator/excerpt 相关片段。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "From the evidence board, what fields should evidence output include, and what else must be resolvable for OCR-derived assets?",
        "Evidence output should include doc_id preview_locator and a resolvable excerpt for OCR derived assets.\nP1 incidents escalate to Liu Chang within 10 minutes.",
        [
            {
                "file": "evidence-board.png",
                "text": "Evidence output should include doc_id preview_locator and a resolvable excerpt for OCR derived assets.",
            },
            {
                "file": "escalation-board.png",
                "text": "P1 incidents escalate to Liu Chang within 10 minutes.",
            },
        ],
    )

    assert "doc_id" in answer
    assert "preview_locator" in answer
    assert "excerpt" in answer.lower()
    assert "Liu Chang" not in answer
    assert [source["file"] for source in used_sources] == ["evidence-board.png"]



def test_targeted_fact_answer_negative_contract_short_circuits_single_source_even_with_noise(chat_service_module):
    """同一 source 已覆盖拒答契约时，不应再拼接无关 escalation 噪声。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "When OCR evidence is sparse on the noisy policy board, may the assistant rely on fabricated memory, or must it stay inside the active knowledge base?",
        "active knowledge base only.\nno fabricated memory.",
        [
            {
                "file": "noisy-policy-board.png",
                "text": "low contrast OCR fallback. no confirmable information. active knowledge base only. no fabricated memory.",
            },
            {
                "file": "escalation-board.png",
                "text": "P1 incidents escalate to Liu Chang within 10 minutes.",
            },
        ],
    )

    assert "no confirmable information" in answer.lower()
    assert "active knowledge base only" in answer.lower()
    assert "no fabricated memory" in answer.lower()
    assert "Liu Chang" not in answer
    assert [source["file"] for source in used_sources] == ["noisy-policy-board.png"]




def test_targeted_fact_answer_prefers_exact_two_preview_fields_from_workflow_note(chat_service_module):
    """workflow boundary note 明确只要求两个字段时，不应串到更宽泛的 evidence contract。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "According to the workflow boundary note, which two fields must an evidence preview include, and what remains the access-control boundary?",
        "",
        [
            {
                "file": "workflow-boundary.md",
                "text": (
                    "# Workflow Boundary Note\n\n"
                    "- Folder path `cutover/runbook/` is an internal organization path, not an authorization boundary.\n"
                    "- Query scope and access control remain at the knowledge base level.\n"
                    "- Evidence preview must include `doc_id` and `preview_locator`."
                ),
            },
            {
                "file": "evidence-preview.md",
                "text": (
                    "# Evidence Preview Contract\n\n"
                    "Evidence items should include title, source, excerpt, doc_id, and preview_locator.\n"
                    "These fields let the frontend render an evidence preview, show source location, and jump back to the originating document."
                ),
            },
        ],
    )

    assert "doc_id" in answer
    assert "preview_locator" in answer
    assert "knowledge base level" in answer.lower()
    assert "title, source, excerpt" not in answer
    assert [source["file"] for source in used_sources] == ["workflow-boundary.md"]


def test_targeted_fact_answer_trims_cross_source_excerpt_noise(chat_service_module):
    """跨 source deadline/interval 问题返回的 source excerpt 应裁到被问到的最小片段，避免 preview 混入 5 minutes 噪声。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "Across the approval matrix and the handover SLA, which value is a sign deadline and which is an escalation interval?",
        "",
        [
            {
                "file": "cutover-approval.md",
                "text": (
                    "# Payroll Cutover Approval Matrix\n\n"
                    "- Final approver: Release Manager Li Qing.\n"
                    "- Business confirmer: Finance Ops Zhou Yu.\n"
                    "- Checklist must be signed before 22:30 Beijing time."
                ),
            },
            {
                "file": "handover-sla.md",
                "text": (
                    "# War-room Handover SLA\n\n"
                    "- P1 cutover incident must be escalated to on-call manager Zhao Lin within 15 minutes.\n"
                    "- Service desk first-ack SLA is 5 minutes."
                ),
            },
        ],
    )

    assert "22:30 Beijing time" in answer
    assert "15 minutes" in answer
    assert [source["file"] for source in used_sources] == ["cutover-approval.md", "handover-sla.md"]
    assert "first-ack" not in used_sources[1]["text"].lower()
    assert "15 minutes" in used_sources[1]["text"]


def test_targeted_fact_answer_prefers_pdf_preview_resolution_clause(chat_service_module):
    """PDF preview guide 的 resolve-back 子问应命中 original PDF chunk 片段，而不是复述整段字段说明。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?",
        "",
        [
            {
                "file": "preview-guide.pdf",
                "text": (
                    "Evidence preview for PDF imports.\n"
                    "Every answer should carry doc_id and preview_locator.\n"
                    "中文补充：每条 PDF 证据回答都必须带上 doc_id 和 preview_locator，方便定位原文片段。\n"
                    "preview excerpt must resolve back to the original PDF chunk."
                ),
            }
        ],
    )

    assert "doc_id" in answer
    assert "preview_locator" in answer
    assert "original PDF chunk" in answer
    assert [source["file"] for source in used_sources] == ["preview-guide.pdf"]
    assert used_sources[0]["text"].count("preview excerpt") == 1


def test_targeted_fact_answer_accepts_echo_field_for_pdf_scope_manual(chat_service_module):
    """mirror/chosen KB 子问应接受 echo/effective_kb_ids 作为对齐字段答案，并补齐真正的 permission wall。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "In the PDF scope manual, which field mirrors the chosen KB, and what boundary acts as the real permission wall?",
        "",
        [
            {
                "file": "scope-manual.pdf",
                "text": (
                    "Scope contract for PDF knowledge base queries.\n"
                    "requested_scope_type must remain single_kb.\n"
                    "effective_kb_ids must echo the active PDF knowledge base.\n"
                    "isolation_level remains physical_isolated in the current architecture."
                ),
            },
            {
                "file": "folder-boundary.pdf",
                "text": (
                    "Folder boundary note for the PDF suite.\n"
                    "Folder is an organization object and not an authorization boundary.\n"
                    "Knowledge Base remains the range and authorization boundary."
                ),
            },
        ],
    )

    assert "effective_kb_ids" in answer
    assert "Knowledge Base" in answer
    assert [source["file"] for source in used_sources] == ["scope-manual.pdf", "folder-boundary.pdf"]


def test_targeted_fact_answer_prefers_operator_checklist_closing_time(chat_service_module):
    """PDF closing time vs escalation interval 问题应选 23:00，而不是把 Sev1 interval 误当 closing time。"""
    answer, used_sources = chat_service_module._maybe_answer_targeted_fact_question_from_sources(
        "Across the PDF release checklist and the war-room handover sheet, which value is the operator checklist closing time and which is the Sev1 escalation interval?",
        "",
        [
            {
                "file": "release-checklist-business.pdf",
                "text": (
                    "Payroll release checklist.\n"
                    "Final sign-off owner: Operations Director Chen Yu.\n"
                    "Rollback owner: Database Lead Xu Nan.\n"
                    "The operator checklist must close before 23:00 Beijing time.\n"
                    "Evidence package must include doc_id and preview_locator."
                ),
            },
            {
                "file": "war-room-handover-business.pdf",
                "text": (
                    "War-room handover sheet.\n"
                    "Primary incident commander: SRE Manager Zhao Lin.\n"
                    "Sev1 cutover issues must be escalated to the commander within 10 minutes.\n"
                    "If the active knowledge base has no confirmable evidence, the answer must say No confirmable information is available in the current knowledge base."
                ),
            },
        ],
    )

    assert "23:00 Beijing time" in answer
    assert "10 minutes" in answer
    assert [source["file"] for source in used_sources] == ["release-checklist-business.pdf", "war-room-handover-business.pdf"]


def test_query_negative_contract_english_question_keeps_chinese_refusal_source(chat_service_module, monkeypatch, single_kb_scope):
    """英文 negative-contract 问题命中中文 refusal source 时，也应保留 refusal-backed source。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text=(
            "请仅依据当前知识库回答。\n"
            "当前知识库中没有可确认的信息。\n"
            "助手不得从外部记忆编造答案。"
        ),
    )
    relevant = {
        "file": "grain-policy-zh.md",
        "text": "当前知识库中没有可确认的信息。助手不得从外部记忆编造答案。",
    }
    unrelated = {
        "file": "handover.md",
        "text": "War-room escalation interval is 15 minutes.",
    }
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[relevant, unrelated]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(
        _build_request(question="If confirmable evidence is missing in the current knowledge base, what should the assistant say and what must it avoid?"),
        record_history=False,
    )

    assert result["sources"] == [relevant]
    assert result["evidence"] == [{"source_count": 1}]
    normalize_evidence.assert_called_once_with([relevant])



def test_query_negative_contract_chinese_question_keeps_english_refusal_source(chat_service_module, monkeypatch, single_kb_scope):
    """中文 negative-contract 问题命中英文 refusal source 时，也应保留 refusal-backed source。"""
    _stub_query_runtime(
        chat_service_module,
        monkeypatch,
        single_kb_scope,
        answer_text=(
            "No confirmable information is available in the current knowledge base.\n"
            "Please answer from the active knowledge base only.\n"
            "You must not fabricate from outside memory."
        ),
    )
    relevant = {
        "file": "policy-en.md",
        "text": "No confirmable information is available in the current knowledge base. The assistant must not fabricate from outside memory.",
    }
    unrelated = {
        "file": "grain.md",
        "text": "各类粮油仓储单位包括国有粮库和政策性粮仓。",
    }
    normalize_evidence = MagicMock(side_effect=lambda srcs: [{"source_count": len(srcs)}])

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=[relevant, unrelated]))
    monkeypatch.setattr(chat_service_module, "append_chat_message", MagicMock())
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(
        _build_request(question="如果当前知识库里没有可确认信息，助手应该怎么回答，并且不能从外部记忆编造什么？"),
        record_history=False,
    )

    assert result["sources"] == [relevant]
    assert result["evidence"] == [{"source_count": 1}]
    normalize_evidence.assert_called_once_with([relevant])
