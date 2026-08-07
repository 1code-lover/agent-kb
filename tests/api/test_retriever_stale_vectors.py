"""检索器陈旧向量容错测试。"""

from __future__ import annotations

from types import SimpleNamespace

from llama_index.core.schema import Document, TextNode
from llama_index.core.vector_stores.types import VectorStoreQueryResult
from llama_index.core.vector_stores.types import FilterCondition

from server.retriever import (
    SafeVectorIndexRetriever,
    SimpleFusionRetriever,
    SimpleHybridRetriever,
    SimpleBM25Retriever,
    filter_bm25_compatible_nodes,
)


def _safe_retriever_with_nodes(nodes_dict: dict[str, str]) -> SafeVectorIndexRetriever:
    retriever = object.__new__(SafeVectorIndexRetriever)
    retriever._index = SimpleNamespace(index_struct=SimpleNamespace(nodes_dict=nodes_dict))
    return retriever


def test_safe_vector_retriever_filters_stale_vector_ids_and_keeps_score_alignment() -> None:
    retriever = _safe_retriever_with_nodes({"valid-vector-id": "valid-doc-node"})
    query_result = VectorStoreQueryResult(
        nodes=None,
        ids=["stale-vector-id", "valid-vector-id"],
        similarities=[0.99, 0.42],
    )

    filtered = retriever._filter_stale_query_result_ids(query_result)

    assert filtered.ids == ["valid-vector-id"]
    assert filtered.similarities == [0.42]


def test_safe_vector_retriever_keeps_query_result_with_embedded_nodes_unchanged() -> None:
    retriever = _safe_retriever_with_nodes({})
    query_result = VectorStoreQueryResult(nodes=[], ids=["stale-vector-id"], similarities=[0.1])

    assert retriever._filter_stale_query_result_ids(query_result) is query_result


def test_hybrid_retrievers_use_safe_vector_retriever(monkeypatch) -> None:
    class DummySafeVectorIndexRetriever:
        def __init__(self, index, similarity_top_k, verbose, filters=None):
            self.index = index
            self.similarity_top_k = similarity_top_k
            self.verbose = verbose

    class DummyBM25Retriever:
        @classmethod
        def from_defaults(cls, index, similarity_top_k, filters=None):
            return cls()

    monkeypatch.setattr("server.retriever.SafeVectorIndexRetriever", DummySafeVectorIndexRetriever)
    monkeypatch.setattr("server.retriever.SimpleBM25Retriever", DummyBM25Retriever)
    monkeypatch.setattr("server.retriever.clamp_top_k_to_corpus", lambda vector_index, top_k: top_k)
    monkeypatch.setattr("server.retriever.QueryFusionRetriever.__init__", lambda self, *args, **kwargs: None)

    index = object()

    simple = SimpleHybridRetriever(index, top_k=3)
    fusion = SimpleFusionRetriever(index, top_k=3)

    assert isinstance(simple.vector_retriever, DummySafeVectorIndexRetriever)
    assert isinstance(fusion.vector_retriever, DummySafeVectorIndexRetriever)



def test_safe_vector_retriever_prunes_incompatible_embedding_dimensions() -> None:
    retriever = _safe_retriever_with_nodes({})
    retriever._vector_store = SimpleNamespace(
        data=SimpleNamespace(
            embedding_dict={
                "valid": [0.1, 0.2, 0.3],
                "short": [0.5],
                "empty": [],
            },
            metadata_dict={"valid": {"kb_id": "default"}, "short": {}, "empty": {}},
            text_id_to_ref_doc_id={"valid": "doc-1", "short": "doc-2", "empty": "doc-3"},
        )
    )

    pruned = retriever._prune_incompatible_vector_embeddings([1.0, 2.0, 3.0])

    assert pruned == 2
    assert retriever._vector_store.data.embedding_dict == {"valid": [0.1, 0.2, 0.3]}
    assert retriever._vector_store.data.metadata_dict == {"valid": {"kb_id": "default"}}
    assert retriever._vector_store.data.text_id_to_ref_doc_id == {"valid": "doc-1"}



def test_simple_fusion_retriever_passes_kb_filters_to_child_retrievers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySafeVectorIndexRetriever:
        def __init__(self, index, similarity_top_k, verbose, filters=None):
            captured["vector_filters"] = filters

    class DummyBM25Retriever:
        @classmethod
        def from_defaults(cls, index, similarity_top_k, filters=None):
            captured["bm25_filters"] = filters
            return cls()

    monkeypatch.setattr("server.retriever.SafeVectorIndexRetriever", DummySafeVectorIndexRetriever)
    monkeypatch.setattr("server.retriever.SimpleBM25Retriever", DummyBM25Retriever)
    monkeypatch.setattr("server.retriever.clamp_top_k_to_corpus", lambda vector_index, top_k: top_k)
    monkeypatch.setattr("server.retriever.QueryFusionRetriever.__init__", lambda self, *args, **kwargs: None)

    SimpleFusionRetriever(object(), top_k=3, kb_ids=["kb-a", "kb-b"])

    vector_filters = captured["vector_filters"]
    bm25_filters = captured["bm25_filters"]
    assert vector_filters is not None
    assert bm25_filters is not None
    assert vector_filters.condition == FilterCondition.OR
    assert [item.value for item in vector_filters.filters] == ["kb-a", "kb-b"]
    assert [item.value for item in bm25_filters.filters] == ["kb-a", "kb-b"]


def test_filter_bm25_compatible_nodes_skips_empty_or_unserializable_nodes() -> None:
    valid = TextNode(text="valid content", metadata={"kb_id": "kb-a"})
    empty = Document(text="", metadata={"kb_id": "kb-a"})

    filtered = filter_bm25_compatible_nodes([empty, valid])

    assert filtered == [valid]


def test_simple_bm25_retriever_from_defaults_filters_invalid_nodes_before_build(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_from_defaults(*, nodes, similarity_top_k, verbose, tokenizer, **kwargs):
        captured["nodes"] = nodes
        captured["similarity_top_k"] = similarity_top_k
        captured["verbose"] = verbose
        captured["tokenizer"] = tokenizer
        captured["kwargs"] = kwargs
        return "fake-bm25"

    monkeypatch.setattr("server.retriever.BM25Retriever.from_defaults", fake_from_defaults)

    valid = TextNode(text="valid content", metadata={"kb_id": "kb-a"})
    empty = Document(text="", metadata={"kb_id": "kb-a"})
    index = SimpleNamespace(docstore=SimpleNamespace(docs={"empty": empty, "valid": valid}))

    result = SimpleBM25Retriever.from_defaults(index=index, similarity_top_k=3, filters="dummy-filter")

    assert result == "fake-bm25"
    assert captured["nodes"] == [valid]
    assert captured["similarity_top_k"] == 1
    assert captured["verbose"] is True
    assert captured["tokenizer"] is not None
    assert captured["kwargs"] == {}
