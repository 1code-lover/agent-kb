"""聊天服务：处理基于知识库的问答请求。"""

from __future__ import annotations

from typing import Any

from api.runtime import runtime_state
from api.schemas import QueryRequest
from api.services.evidence_service import normalize_evidence, normalize_source_nodes
from api.services.query_scope import resolve_chat_query_scope
from api.services.session_store import append_chat_message, clear_chat_messages, list_chat_messages


def _normalize_sources(response: Any) -> list[dict[str, Any]]:
    """兼容旧 sources 字段，统一复用 evidence service 的节点映射。"""
    return normalize_source_nodes(response)


def query(request: QueryRequest, record_history: bool = True) -> dict[str, Any]:
    """执行单轮问答，并返回答案、证据与范围回显。"""
    scope = resolve_chat_query_scope(request.kb_ids)

    if not runtime_state.ensure_index_loaded():
        raise ValueError("Knowledge base is empty. Please import documents first.")

    engine = runtime_state.build_query_engine(kb_ids=scope.effective_kb_ids)
    answer = engine.query(request.question)
    answer_text = getattr(answer, "response", str(answer))
    sources = _normalize_sources(answer)

    if record_history:
        append_chat_message(request.session_id, "user", request.question)
        append_chat_message(request.session_id, "assistant", answer_text)

    result = {
        "session_id": request.session_id,
        "answer": answer_text,
        "sources": sources,
        "evidence": normalize_evidence(sources),
    }
    result.update(scope.to_dict())
    return result


def get_history(session_id: str) -> list[dict[str, Any]]:
    return list_chat_messages(session_id)


def clear_history(session_id: str) -> None:
    clear_chat_messages(session_id)
