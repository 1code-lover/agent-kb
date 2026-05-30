"""Chat service for knowledge-base grounded Q&A."""

from __future__ import annotations

from typing import Any

from api.runtime import runtime_state
from api.schemas import QueryRequest
from api.services.session_store import append_chat_message, clear_chat_messages, list_chat_messages


def _normalize_sources(response: Any) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for node in getattr(response, "source_nodes", []) or []:
        content_node = getattr(node, "node", None)
        metadata = getattr(content_node, "metadata", {}) if content_node is not None else {}
        sources.append(
            {
                "file": metadata.get("file_name") or metadata.get("title", "N/A"),
                "page": metadata.get("page_label", "N/A"),
                "score": getattr(node, "score", None),
                "text": getattr(content_node, "text", "") if content_node is not None else "",
            }
        )
    return sources


def query(request: QueryRequest, record_history: bool = True) -> dict[str, Any]:
    if not runtime_state.ensure_index_loaded():
        raise ValueError("Knowledge base is empty. Please import documents first.")

    engine = runtime_state.build_query_engine()
    answer = engine.query(request.question)
    answer_text = getattr(answer, "response", str(answer))

    if record_history:
        append_chat_message(request.session_id, "user", request.question)
        append_chat_message(request.session_id, "assistant", answer_text)

    return {
        "session_id": request.session_id,
        "answer": answer_text,
        "sources": _normalize_sources(answer),
    }


def get_history(session_id: str) -> list[dict[str, Any]]:
    return list_chat_messages(session_id)


def clear_history(session_id: str) -> None:
    clear_chat_messages(session_id)

