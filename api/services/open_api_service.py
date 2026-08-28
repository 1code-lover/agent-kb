"""只读开放问答与结构化搜索服务。"""

from __future__ import annotations

from types import SimpleNamespace

import config
from api.runtime import runtime_state
from api.schemas import QueryRequest
from api.services import asset_service, chat_service
from api.services.evidence_service import normalize_evidence, normalize_source_nodes
from server.retriever import SimpleFusionRetriever


def run_readonly_query(
    *,
    token_id: str,
    kb_id: str,
    question: str,
    top_k: int | None = None,
    response_mode: str | None = None,
    use_reranker: bool | None = None,
    top_n: int | None = None,
    reranker_model: str | None = None,
) -> dict:
    """固定单知识库范围执行只读问答，不记录会话历史。"""
    request = QueryRequest(
        question=question,
        session_id=f"open-readonly:{token_id}",
        kb_ids=[kb_id],
        top_k=top_k,
        response_mode=response_mode,
        use_reranker=use_reranker,
        top_n=top_n,
        reranker_model=reranker_model,
    )
    return chat_service.query(request, record_history=False)


def run_readonly_search(
    *,
    token_id: str,
    kb_id: str,
    question: str,
    top_k: int | None = None,
) -> dict:
    """在单个物理知识库内执行不调用 LLM 的结构化检索。"""
    del token_id  # 保留统一服务签名；审计和未来限流由路由层负责。
    if not runtime_state.ensure_models_ready(require_llm=False):
        raise RuntimeError("Embedding model is not configured or unavailable.")

    manager = runtime_state.get_index_manager(kb_id)
    if getattr(manager, "index", None) is None:
        if not manager.check_index_exists():
            raise ValueError("Knowledge base is empty. Please import documents first.")
        manager.load_index()

    effective_top_k = top_k or config.TOP_K
    retriever = SimpleFusionRetriever(
        vector_index=manager.index,
        top_k=effective_top_k,
        kb_ids=[kb_id],
    )
    nodes = retriever.retrieve(question)
    hits = normalize_source_nodes(SimpleNamespace(source_nodes=nodes))
    return {
        "kb_id": kb_id,
        "question": question,
        "top_k": effective_top_k,
        "hits": hits,
        "evidence": normalize_evidence(hits),
    }
