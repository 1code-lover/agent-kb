"""聊天服务，封装问答与会话历史。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from api.runtime import runtime_state
from api.schemas import QueryRequest

_CHAT_HISTORY: dict[str, list[dict[str, str]]] = defaultdict(list)


def _normalize_sources(response: Any) -> list[dict[str, Any]]:
    """将 LlamaIndex 响应来源统一为前端可消费结构。"""
    sources: list[dict[str, Any]] = []
    for node in getattr(response, "source_nodes", []) or []:
        n = getattr(node, "node", None)
        metadata = getattr(n, "metadata", {}) if n is not None else {}
        sources.append(
            {
                "file": metadata.get("file_name") or metadata.get("title", "N/A"),
                "page": metadata.get("page_label", "N/A"),
                "score": getattr(node, "score", None),
                "text": getattr(n, "text", "") if n is not None else "",
            }
        )
    return sources


def query(request: QueryRequest) -> dict[str, Any]:
    """执行一次问答请求。

    Args:
        request: 问答请求参数。

    Returns:
        标准化问答结果。
    """
    if not runtime_state.ensure_index_loaded():
        raise ValueError("Knowledge base is empty. Please import documents first.")

    engine = runtime_state.build_query_engine()
    answer = engine.query(request.question)
    answer_text = getattr(answer, "response", str(answer))
    _CHAT_HISTORY[request.session_id].append({"role": "user", "content": request.question})
    _CHAT_HISTORY[request.session_id].append({"role": "assistant", "content": answer_text})

    return {
        "session_id": request.session_id,
        "answer": answer_text,
        "sources": _normalize_sources(answer),
    }


def get_history(session_id: str) -> list[dict[str, str]]:
    """获取会话历史。"""
    return _CHAT_HISTORY[session_id]


def clear_history(session_id: str) -> None:
    """清空会话历史。"""
    _CHAT_HISTORY[session_id] = []
