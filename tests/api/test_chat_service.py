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
        isolation_level="logical_filter_only",
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


def test_prune_sources_for_refusal_keeps_only_grounded_sources(chat_service_module):
    """拒答分支只保留与当前问题同主题的来源。"""
    sources = [
        {"file": "mobile-build-guide.md", "text": "GPU memory requirement is not specified."},
        {"file": "cutover.md", "text": "Rollback approval is issued by the deployment lead."},
    ]

    pruned = chat_service_module._prune_sources_for_refusal(
        "What is the GPU memory requirement for the mobile build?", sources
    )

    assert pruned == [sources[0]]


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

    monkeypatch.setattr(chat_service_module, "_normalize_sources", MagicMock(return_value=sources))
    monkeypatch.setattr(chat_service_module, "append_chat_message", append_chat_message)
    monkeypatch.setattr(chat_service_module, "normalize_evidence", normalize_evidence)

    result = chat_service_module.query(_build_request(), record_history=False)

    assert result["answer"] == "GPU memory is 8GB."
    assert result["sources"] == sources
    assert result["evidence"] == [{"id": "ev-1"}]
    assert result["effective_kb_ids"] == ["kb-a"]
    build_query_engine.assert_called_once_with(kb_ids=["kb-a"])
    engine.query.assert_called_once_with("What is the GPU memory requirement?")
    append_chat_message.assert_not_called()
    normalize_evidence.assert_called_once_with(sources)


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

