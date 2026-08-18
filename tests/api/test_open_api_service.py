"""只读 Open API 服务层测试。"""

from __future__ import annotations

from types import SimpleNamespace

from llama_index.core.schema import NodeWithScore, TextNode

from api.services import open_api_service


class _Manager:
    """提供已加载物理索引的最小管理器。"""

    def __init__(self) -> None:
        self.index = object()

    def check_index_exists(self):
        return True

    def load_index(self):
        return self.index


class _Runtime:
    """记录模型检查和知识库选择。"""

    def __init__(self) -> None:
        self.manager = _Manager()
        self.kb_ids: list[str] = []

    def ensure_models_ready(self, require_llm=False):
        assert require_llm is False
        return True

    def get_index_manager(self, kb_id):
        self.kb_ids.append(kb_id)
        return self.manager


class _Retriever:
    """返回一个带范围元数据的结构化命中。"""

    def __init__(self, *, vector_index, top_k, kb_ids):
        assert vector_index is runtime.manager.index
        assert top_k == 4
        assert kb_ids == ["finance"]

    def retrieve(self, question):
        assert question == "revenue"
        return [
            NodeWithScore(
                node=TextNode(
                    id_="n1",
                    text="finance revenue 100",
                    metadata={"kb_id": "finance", "file_name": "finance.md", "ref_doc_id": "doc-1"},
                ),
                score=0.91,
            )
        ]


runtime = _Runtime()


def test_structured_search_uses_one_physical_kb_and_returns_hits(monkeypatch):
    """搜索只选择一个知识库管理器，并返回 hits/evidence，不调用 LLM。"""
    global runtime
    runtime = _Runtime()
    monkeypatch.setattr(open_api_service, "runtime_state", runtime)
    monkeypatch.setattr(open_api_service, "SimpleFusionRetriever", _Retriever)
    monkeypatch.setattr(open_api_service.asset_service, "list_assets", lambda kb_id: [])

    result = open_api_service.run_readonly_search(
        token_id="tok-1",
        kb_id="finance",
        question="revenue",
        top_k=4,
    )

    assert runtime.kb_ids == ["finance"]
    assert result["kb_id"] == "finance"
    assert result["top_k"] == 4
    assert result["hits"][0]["kb_id"] == "finance"
    assert result["hits"][0]["text"] == "finance revenue 100"
    assert result["evidence"][0]["excerpt"] == "finance revenue 100"


def test_structured_search_requires_embedding_runtime(monkeypatch):
    """Embedding 未就绪时搜索应稳定返回运行时错误。"""
    unavailable = SimpleNamespace(ensure_models_ready=lambda require_llm=False: False)
    monkeypatch.setattr(open_api_service, "runtime_state", unavailable)

    try:
        open_api_service.run_readonly_search(
            token_id="tok-1",
            kb_id="finance",
            question="revenue",
        )
    except RuntimeError as exc:
        assert "Embedding model" in str(exc)
    else:
        raise AssertionError("Embedding 未就绪必须拒绝搜索")
