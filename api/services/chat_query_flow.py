"""聊天问答 follow-up 注入与查询前置流程。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from api.schemas import QueryRequest

Source = dict[str, Any]
SourceList = list[Source]
HistoryMessage = dict[str, str]
QuestionPredicate = Callable[[str], bool]
HistoryLoader = Callable[[str], list[dict[str, Any]]]
SourceNormalizer = Callable[[Any], SourceList]
SourceDeduper = Callable[[SourceList], SourceList]
SourceReconciler = Callable[[Any, str, SourceList], SourceList]
QuestionSourcePredicate = Callable[[str, Source], bool]
AnswerBuilder = Callable[[str, Any | None], str]
HistoryAppender = Callable[[str, str, str], Any]
ModelHealthGetter = Callable[[], dict[str, Any]]
NormalizeEvidence = Callable[[SourceList], list[dict[str, Any]]]
QueryEngineBuilder = Callable[..., Any]
ModelFallbackHandler = Callable[..., dict[str, Any]]
ModelInvalidator = Callable[[], Any]
IdentifierQuestionPredicate = Callable[[str], bool]
IdentifierSourceSupport = Callable[[str, SourceList], bool]
RefusalAnswerPredicate = Callable[[str], bool]
RefusalSourcePruner = Callable[[str, str, SourceList], SourceList]
SourceAnswerPostprocessor = Callable[[str, str, SourceList], tuple[str, SourceList]]


@dataclass(frozen=True)
class QueryFlowHooks:
    """收敛 chat_service 中 follow-up / preflight / query engine 前置依赖。"""

    question_looks_follow_up: QuestionPredicate
    list_chat_messages: HistoryLoader
    question_requests_exact_source_phrase: QuestionPredicate
    normalize_sources: SourceNormalizer
    dedupe_sources: SourceDeduper
    reconcile_sources_for_question: SourceReconciler
    source_supports_question: QuestionSourcePredicate
    build_refusal_answer: AnswerBuilder
    append_chat_message: HistoryAppender
    get_model_health: ModelHealthGetter
    normalize_evidence: NormalizeEvidence
    build_query_engine: QueryEngineBuilder
    attempt_model_fallback: ModelFallbackHandler
    invalidate_llm: ModelInvalidator
    question_requests_identifier_like_field: IdentifierQuestionPredicate
    sources_support_identifier_like_field: IdentifierSourceSupport
    answer_is_refusal_like: RefusalAnswerPredicate
    prune_sources_for_refusal: RefusalSourcePruner
    apply_source_answer_postprocessors: SourceAnswerPostprocessor
    max_follow_up_history_messages: int
    max_follow_up_history_chars: int


def load_recent_history_for_follow_up(session_id: str, *, hooks: QueryFlowHooks) -> list[HistoryMessage]:
    """裁剪当前 session 最近几条有效对话，供 follow-up 问答改写使用。"""
    recent_messages = hooks.list_chat_messages(session_id)
    normalized: list[HistoryMessage] = []
    total_chars = 0

    for item in reversed(list(recent_messages or [])):
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = " ".join(str(item.get("content") or "").split())
        if not content:
            continue
        remaining = hooks.max_follow_up_history_chars - total_chars
        if remaining <= 0:
            break
        clipped = content[-remaining:]
        normalized.append({"role": role, "content": clipped})
        total_chars += len(clipped)
        if len(normalized) >= hooks.max_follow_up_history_messages:
            break

    normalized.reverse()
    return normalized


def build_history_grounded_question(question: str, session_id: str, *, hooks: QueryFlowHooks) -> str:
    """对 follow-up 提问注入同 session 的最近上下文，但不改变 KB 范围契约。"""
    if not hooks.question_looks_follow_up(question):
        return question

    history = load_recent_history_for_follow_up(session_id, hooks=hooks)
    if not history:
        return question

    lines = ["Conversation context from the same session:"]
    for item in history:
        speaker = "User" if item["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {item['content']}")
    lines.append(f"Current question: {str(question or '').strip()}")
    lines.append("Answer only from the active knowledge base.")
    return "\n".join(lines)


def preflight_exact_question_sources(engine: Any, question: str, *, hooks: QueryFlowHooks) -> SourceList | None:
    """唯一值/原文类问题先做一次纯检索；无相关证据时不调用 LLM，避免跨库臆答。"""
    if not hooks.question_requests_exact_source_phrase(question):
        return None
    retrieve = getattr(engine, "retrieve", None)
    if not callable(retrieve):
        return None
    try:
        retrieved = retrieve(question)
    except Exception:
        return None
    if not isinstance(retrieved, (list, tuple)):
        return None

    sources = hooks.normalize_sources(retrieved)
    return [source for source in sources if hooks.source_supports_question(question, source)]


def execute_query_with_model_fallback(
    engine: Any,
    request: QueryRequest,
    scope: Any,
    grounded_question: str,
    *,
    hooks: QueryFlowHooks,
) -> tuple[Any, Any]:
    """执行 query，并在可恢复模型错误时重建 engine 后重试一次。"""
    try:
        answer = engine.query(grounded_question)
    except Exception as exc:
        fallback = hooks.attempt_model_fallback(exc, session_id=request.session_id)
        if not fallback.get("applied"):
            raise
        hooks.invalidate_llm()
        engine = build_query_engine_for_request(request, scope, hooks=hooks)
        answer = engine.query(grounded_question)
    return answer, engine


def build_no_source_result(request: QueryRequest, scope: Any, *, record_history: bool, hooks: QueryFlowHooks) -> dict[str, Any]:
    """构造限定知识库无相关证据时的稳定拒答结果。"""
    answer_text = hooks.build_refusal_answer(request.question, scope)
    if record_history:
        hooks.append_chat_message(request.session_id, "user", request.question)
        hooks.append_chat_message(request.session_id, "assistant", answer_text)
    result = {
        "session_id": request.session_id,
        "answer": answer_text,
        "sources": [],
        "evidence": [],
        "model_health": hooks.get_model_health(),
    }
    result.update(scope.to_dict())
    return result


def build_query_result(
    request: QueryRequest,
    scope: Any,
    answer_text: str,
    sources: SourceList,
    *,
    record_history: bool,
    hooks: QueryFlowHooks,
) -> dict[str, Any]:
    """组装 query 结果，并在需要时记录当前轮会话历史。"""
    if record_history:
        hooks.append_chat_message(request.session_id, "user", request.question)
        hooks.append_chat_message(request.session_id, "assistant", answer_text)
    result = {
        "session_id": request.session_id,
        "answer": answer_text,
        "sources": sources,
        "evidence": hooks.normalize_evidence(sources),
        "model_health": hooks.get_model_health(),
    }
    result.update(scope.to_dict())
    return result


def extract_query_answer_payload(answer: Any, engine: Any, question: str, *, hooks: QueryFlowHooks) -> tuple[str, SourceList]:
    """提取回答文本，并串接 source normalize / dedupe / reconcile 主流程。"""
    answer_text = getattr(answer, "response", str(answer))
    sources = hooks.dedupe_sources(hooks.normalize_sources(answer))
    sources = hooks.reconcile_sources_for_question(engine, question, sources)
    return answer_text, sources


def finalize_query_answer(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    scope: Any | None = None,
    hooks: QueryFlowHooks,
) -> tuple[str, SourceList]:
    """收口 identifier-gap、refusal pruning 与非 refusal postprocess 的尾段分支。"""
    identifier_like_gap = hooks.question_requests_identifier_like_field(question) and not hooks.sources_support_identifier_like_field(
        question,
        sources,
    )
    if identifier_like_gap:
        return hooks.build_refusal_answer(question, scope), []

    if hooks.answer_is_refusal_like(answer_text):
        return answer_text, hooks.prune_sources_for_refusal(question, answer_text, sources)

    return hooks.apply_source_answer_postprocessors(question, answer_text, sources)


def build_query_engine_for_request(request: QueryRequest, scope: Any, *, hooks: QueryFlowHooks) -> Any:
    """把请求级 RAG 参数透传到查询引擎构建逻辑。"""
    return hooks.build_query_engine(
        kb_ids=scope.effective_kb_ids,
        top_k=request.top_k,
        response_mode=request.response_mode,
        use_reranker=request.use_reranker,
        top_n=request.top_n,
        reranker_model=request.reranker_model,
    )

