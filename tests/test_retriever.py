"""Retriever 关键路径单元测试。

这些用例聚焦 kb filter、BM25 兼容过滤、stale vector id 清理、hybrid / fusion 检索兜底。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from llama_index.core.vector_stores.types import FilterCondition, VectorStoreQueryResult

from server import retriever as retriever_module


def _scored_node(
    node_id: str,
    score: float,
    *,
    text: str = "text",
    kb_id: str | None = None,
    file_name: str | None = None,
):
    metadata = {} if kb_id is None else {"kb_id": kb_id}
    if file_name is not None:
        metadata["file_name"] = file_name
    inner = SimpleNamespace(node_id=node_id, metadata=metadata)
    return SimpleNamespace(node=inner, node_id=node_id, text=text, score=score)


def test_build_kb_metadata_filters_returns_or_filters() -> None:
    """kb_id 过滤器应在多库场景下构造 OR 条件。"""
    assert retriever_module.build_kb_metadata_filters(None) is None
    assert retriever_module.build_kb_metadata_filters([]) is None

    filters = retriever_module.build_kb_metadata_filters(["kb-a", "kb-b"])

    assert filters is not None
    assert filters.condition == FilterCondition.OR
    assert [(item.key, item.value) for item in filters.filters] == [("kb_id", "kb-a"), ("kb_id", "kb-b")]


def test_filter_bm25_compatible_nodes_skips_empty_and_bad_metadata(monkeypatch) -> None:
    """BM25 兼容过滤应跳过空内容节点与 metadata 序列化失败节点。"""

    class FakeNode:
        def __init__(self, node_id: str, content) -> None:
            self.node_id = node_id
            self._content = content

        def get_content(self, metadata_mode=None):
            return self._content

    monkeypatch.setattr(
        retriever_module,
        "node_to_metadata_dict",
        lambda node: (_ for _ in ()).throw(ValueError("bad metadata")) if node.node_id == "bad-meta" else {"id": node.node_id},
    )
    monkeypatch.setattr(retriever_module, "metadata_dict_to_node", lambda metadata: metadata)

    nodes = [
        FakeNode("ok", "第一段内容"),
        FakeNode("blank", "   "),
        FakeNode("bad-meta", "第二段内容"),
        FakeNode("none", None),
    ]

    compatible = retriever_module.filter_bm25_compatible_nodes(nodes)

    assert [node.node_id for node in compatible] == ["ok"]


def test_clamp_top_k_to_corpus_uses_smallest_available_store_size() -> None:
    """top_k 应被限制到 docstore 与 vector store 的较小规模。"""
    vector_index = SimpleNamespace(
        docstore=SimpleNamespace(docs={"a": 1, "b": 2, "c": 3}),
        vector_store=SimpleNamespace(_collection=SimpleNamespace(count=lambda: 2)),
    )

    assert retriever_module.clamp_top_k_to_corpus(vector_index, 5) == 2
    assert retriever_module.clamp_top_k_to_corpus(SimpleNamespace(docstore=None), 0) == 1


def test_safe_vector_retriever_filters_stale_ids_and_prunes_bad_embeddings() -> None:
    """安全向量检索器应先剔除 stale id，再删除维度不兼容 embedding。"""
    retriever = object.__new__(retriever_module.SafeVectorIndexRetriever)
    retriever._index = SimpleNamespace(index_struct=SimpleNamespace(nodes_dict={"keep": "node"}))

    filtered = retriever._filter_stale_query_result_ids(
        VectorStoreQueryResult(nodes=None, similarities=[0.9, 0.1], ids=["keep", "stale"])
    )

    vector_data = SimpleNamespace(
        embedding_dict={"keep": [1.0, 2.0], "bad": [1.0]},
        metadata_dict={"keep": {"k": 1}, "bad": {"k": 2}},
        text_id_to_ref_doc_id={"keep": "doc-keep", "bad": "doc-bad"},
    )
    retriever._vector_store = SimpleNamespace(data=vector_data)
    removed = retriever._prune_incompatible_vector_embeddings([0.1, 0.2])

    assert filtered.ids == ["keep"]
    assert filtered.similarities == [0.9]
    assert removed == 1
    assert vector_data.embedding_dict == {"keep": [1.0, 2.0]}
    assert vector_data.metadata_dict == {"keep": {"k": 1}}
    assert vector_data.text_id_to_ref_doc_id == {"keep": "doc-keep"}


def test_simple_bm25_retriever_from_defaults_clamps_top_k_and_passes_tokenizer(monkeypatch) -> None:
    """BM25 工厂应使用过滤后的节点列表、中文分词器与收缩后的 top_k，并剥离底层不支持的 filters。"""
    doc_a = SimpleNamespace(node_id="a")
    doc_b = SimpleNamespace(node_id="b")
    index = SimpleNamespace(docstore=SimpleNamespace(docs={"a": doc_a, "b": doc_b}))
    monkeypatch.setattr(retriever_module, "filter_bm25_compatible_nodes", lambda nodes: [nodes[0]])
    bm25_ctor = MagicMock(return_value="bm25")
    monkeypatch.setattr(retriever_module.BM25Retriever, "from_defaults", bm25_ctor)

    result = retriever_module.SimpleBM25Retriever.from_defaults(index=index, similarity_top_k=5, filters="kb-filter")

    assert result == "bm25"
    kwargs = bm25_ctor.call_args.kwargs
    assert kwargs["nodes"] == [doc_a]
    assert kwargs["similarity_top_k"] == 1
    assert kwargs["verbose"] is True
    assert kwargs["tokenizer"] is retriever_module.chinese_tokenizer
    # BM25Retriever (bm25s) 不接受 metadata filters，应被显式剥离，
    # kb_id 过滤改由 SimpleHybridRetriever 在融合层兜底完成。
    assert "filters" not in kwargs


def test_simple_hybrid_retriever_normalizes_bm25_scores_and_deduplicates() -> None:
    """Hybrid 检索应先归一化 BM25 分数，再按向量优先顺序去重。"""
    hybrid = object.__new__(retriever_module.SimpleHybridRetriever)
    hybrid.top_k = 2
    bm25_nodes = [_scored_node("dup", 2.0, text="bm25-dup"), _scored_node("bm", 4.0, text="bm25-only")]
    vector_nodes = [_scored_node("dup", 0.8, text="vector-dup"), _scored_node("vec", 0.7, text="vector-only")]
    hybrid.bm25_retriever = SimpleNamespace(retrieve=lambda query, **kwargs: bm25_nodes)
    hybrid.vector_retriever = SimpleNamespace(retrieve=lambda query, **kwargs: vector_nodes)

    result = hybrid._retrieve("查询词")

    assert [item.node.node_id for item in result] == ["dup", "vec"]
    assert [item.score for item in bm25_nodes] == [0.0, 1.0]


def test_simple_fusion_retriever_filters_nodes_by_kb_scope() -> None:
    """Fusion 检索器应在返回层兜底过滤不属于当前 kb 范围的节点。"""
    fusion = object.__new__(retriever_module.SimpleFusionRetriever)
    fusion._kb_ids = {"kb-a", "default"}
    nodes = [
        _scored_node("a", 0.9, kb_id="kb-a"),
        _scored_node("missing", 0.7, kb_id=None),
        _scored_node("b", 0.6, kb_id="kb-b"),
    ]

    filtered = fusion._filter_nodes_by_kb(nodes)
    fusion._kb_ids = {"kb-a"}

    assert [item.node.node_id for item in filtered] == ["a", "missing"]
    assert fusion._node_allowed_by_kb(_scored_node("a", 0.9, kb_id="kb-a")) is True
    assert fusion._node_allowed_by_kb(_scored_node("missing", 0.7, kb_id=None)) is False



def test_safe_vector_retriever_get_nodes_with_embeddings_fetches_missing_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    """同步向量检索应先过滤 stale id，再回填 docstore 节点。"""

    retriever = object.__new__(retriever_module.SafeVectorIndexRetriever)
    retriever._kwargs = {"alpha": 1}

    query_bundle = SimpleNamespace(name="bundle")
    query = SimpleNamespace(query_embedding=[1.0, 2.0])
    query_result = VectorStoreQueryResult(nodes=None, similarities=[0.8], ids=["node-1"])
    assembled = [SimpleNamespace(node=SimpleNamespace(node_id="node-1"), score=0.8)]
    captured: dict[str, object] = {}

    def fake_prune(embedding):
        captured["embedding"] = embedding
        return 0

    def fake_query(built_query, **kwargs):
        captured["query_args"] = (built_query, kwargs)
        return query_result

    retriever._build_vector_store_query = lambda bundle: query
    retriever._prune_incompatible_vector_embeddings = fake_prune
    retriever._vector_store = SimpleNamespace(query=fake_query)
    retriever._filter_stale_query_result_ids = lambda result: result
    retriever._build_node_list_from_query_result = lambda result: assembled
    monkeypatch.setattr(retriever_module, "log_vector_store_query_result", lambda result: captured.setdefault("logged", result))

    result = retriever._get_nodes_with_embeddings(query_bundle)

    assert captured["embedding"] == [1.0, 2.0]
    assert captured["query_args"] == (query, {"alpha": 1})
    assert result[0].node.node_id == "node-1"


def test_safe_vector_retriever_aget_nodes_with_embeddings_fetches_missing_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    """异步向量检索分支也应经过 stale id 过滤与 docstore 回填。"""

    retriever = object.__new__(retriever_module.SafeVectorIndexRetriever)
    retriever._kwargs = {"alpha": 1}

    query_bundle = SimpleNamespace(name="bundle")
    query = SimpleNamespace(query_embedding=[1.0, 2.0])
    query_result = VectorStoreQueryResult(nodes=None, similarities=[0.6], ids=["node-1"])
    assembled = [SimpleNamespace(node=SimpleNamespace(node_id="node-1"), score=0.6)]
    captured: dict[str, object] = {}

    async def fake_aquery(built_query, **kwargs):
        captured["query_args"] = (built_query, kwargs)
        return query_result

    def fake_prune(embedding):
        captured["embedding"] = embedding
        return 0

    retriever._build_vector_store_query = lambda bundle: query
    retriever._prune_incompatible_vector_embeddings = fake_prune
    retriever._vector_store = SimpleNamespace(aquery=fake_aquery)
    retriever._filter_stale_query_result_ids = lambda result: result
    retriever._build_node_list_from_query_result = lambda result: assembled
    monkeypatch.setattr(retriever_module, "log_vector_store_query_result", lambda result: captured.setdefault("logged", result))

    result = asyncio.run(retriever._aget_nodes_with_embeddings(query_bundle))

    assert captured["embedding"] == [1.0, 2.0]
    assert captured["query_args"] == (query, {"alpha": 1})
    assert result[0].node.node_id == "node-1"


def test_simple_hybrid_retriever_init_uses_safe_retrievers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hybrid 检索器初始化时应使用收缩后的 top_k 创建两路召回器。"""

    captured: dict[str, object] = {}

    monkeypatch.setattr(retriever_module, "clamp_top_k_to_corpus", lambda vector_index, top_k: 3)
    def fake_vector_ctor(**kwargs):
        captured["vector"] = kwargs
        return "vector-retriever"

    def fake_bm25_ctor(**kwargs):
        captured["bm25"] = kwargs
        return "bm25-retriever"

    monkeypatch.setattr(retriever_module, "SafeVectorIndexRetriever", fake_vector_ctor)
    monkeypatch.setattr(retriever_module.SimpleBM25Retriever, "from_defaults", fake_bm25_ctor)

    hybrid = retriever_module.SimpleHybridRetriever(vector_index="index-sentinel", top_k=10)

    assert hybrid.top_k == 3
    assert hybrid.vector_retriever == "vector-retriever"
    assert hybrid.bm25_retriever == "bm25-retriever"
    assert captured["vector"] == {"index": "index-sentinel", "similarity_top_k": 3, "verbose": True}
    assert captured["bm25"] == {"index": "index-sentinel", "similarity_top_k": 3}


def test_simple_hybrid_retriever_assigns_half_score_when_bm25_scores_are_identical() -> None:
    """BM25 分数全部相同时，Hybrid 检索应将其统一归为 0.5。"""

    hybrid = object.__new__(retriever_module.SimpleHybridRetriever)
    hybrid.top_k = 3
    bm25_nodes = [_scored_node("bm-1", 2.0), _scored_node("bm-2", 2.0)]
    vector_nodes = [_scored_node("vec-1", 0.9)]
    hybrid.bm25_retriever = SimpleNamespace(retrieve=lambda query, **kwargs: bm25_nodes)
    hybrid.vector_retriever = SimpleNamespace(retrieve=lambda query, **kwargs: vector_nodes)

    result = hybrid._retrieve("一致分数查询")

    assert [item.node.node_id for item in result] == ["vec-1", "bm-1", "bm-2"]
    assert [item.score for item in bm25_nodes] == [0.5, 0.5]


def test_simple_fusion_retriever_init_wires_filters_and_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fusion 检索器初始化时应传递 kb 过滤与固定融合权重。"""

    captured: dict[str, object] = {}

    monkeypatch.setattr(retriever_module, "clamp_top_k_to_corpus", lambda vector_index, top_k: 4)
    monkeypatch.setattr(retriever_module, "build_kb_metadata_filters", lambda kb_ids: {"kb_ids": kb_ids})
    def fake_vector_ctor(**kwargs):
        captured["vector"] = kwargs
        return "vector-retriever"

    def fake_bm25_ctor(**kwargs):
        captured["bm25"] = kwargs
        return "bm25-retriever"

    monkeypatch.setattr(retriever_module, "SafeVectorIndexRetriever", fake_vector_ctor)
    monkeypatch.setattr(retriever_module.SimpleBM25Retriever, "from_defaults", fake_bm25_ctor)

    original_init = retriever_module.QueryFusionRetriever.__init__

    def fake_init(self, retrievers, **kwargs):
        captured["super"] = {"retrievers": retrievers, **kwargs}

    monkeypatch.setattr(retriever_module.QueryFusionRetriever, "__init__", fake_init)
    try:
        fusion = retriever_module.SimpleFusionRetriever(
            vector_index="vector-index",
            top_k=10,
            mode=retriever_module.FUSION_MODES.SIMPLE,
            kb_ids=["kb-a"],
        )
    finally:
        monkeypatch.setattr(retriever_module.QueryFusionRetriever, "__init__", original_init)

    assert fusion.top_k == 4
    assert fusion.mode == retriever_module.FUSION_MODES.SIMPLE
    assert fusion._kb_ids == {"kb-a"}
    assert fusion._kb_filters == {"kb_ids": ["kb-a"]}
    assert captured["vector"] == {
        "index": "vector-index",
        "similarity_top_k": 4,
        "verbose": True,
        "filters": {"kb_ids": ["kb-a"]},
    }
    assert captured["bm25"] == {
        "index": "vector-index",
        "similarity_top_k": 4,
        "filters": {"kb_ids": ["kb-a"]},
    }
    assert captured["super"]["retrievers"] == ["vector-retriever", "bm25-retriever"]
    assert captured["super"]["retriever_weights"] == [0.6, 0.4]
    assert captured["super"]["similarity_top_k"] == 4
    assert captured["super"]["num_queries"] == 1
    assert captured["super"]["mode"] == retriever_module.FUSION_MODES.SIMPLE


def test_simple_fusion_retriever_allows_nodes_without_scope_limit() -> None:
    """未声明 kb 范围时，Fusion 检索器不应额外过滤节点。"""

    fusion = object.__new__(retriever_module.SimpleFusionRetriever)
    fusion._kb_ids = None
    nodes = [_scored_node("a", 0.9, kb_id="kb-a")]

    assert fusion._node_allowed_by_kb(nodes[0]) is True
    assert fusion._filter_nodes_by_kb(nodes) is nodes


def test_simple_fusion_retriever_filters_sync_and_async_super_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fusion 检索器应对 super() 返回的同步与异步结果执行 kb 过滤。"""

    fusion = object.__new__(retriever_module.SimpleFusionRetriever)
    fusion._kb_ids = {"kb-a"}
    fusion.top_k = 5

    sync_nodes = [_scored_node("a", 0.9, kb_id="kb-a"), _scored_node("b", 0.5, kb_id="kb-b")]
    async_nodes = [_scored_node("c", 0.8, kb_id="kb-a"), _scored_node("d", 0.4, kb_id="kb-b")]

    original_retrieve = retriever_module.QueryFusionRetriever._retrieve
    original_aretrieve = retriever_module.QueryFusionRetriever._aretrieve

    async def fake_aretrieve(self, query_bundle):
        return async_nodes

    monkeypatch.setattr(retriever_module.QueryFusionRetriever, "_retrieve", lambda self, query_bundle: sync_nodes)
    monkeypatch.setattr(retriever_module.QueryFusionRetriever, "_aretrieve", fake_aretrieve)
    try:
        sync_result = fusion._retrieve("sync-query")
        async_result = asyncio.run(fusion._aretrieve("async-query"))
    finally:
        monkeypatch.setattr(retriever_module.QueryFusionRetriever, "_retrieve", original_retrieve)
        monkeypatch.setattr(retriever_module.QueryFusionRetriever, "_aretrieve", original_aretrieve)

    assert [item.node.node_id for item in sync_result] == ["a"]
    assert [item.node.node_id for item in async_result] == ["c"]


def test_title_match_boost_promotes_named_source_file() -> None:
    """查询点名文档标题时，应给对应来源文件提供明显排序加权。"""

    node = _scored_node(
        "aircon",
        0.1,
        file_name="17空调控温储粮技术规程20160624.docx",
    )

    boost = retriever_module.title_match_boost("空调控温储粮技术规程适用于什么条件下的平房仓？", node)

    assert boost >= 0.55


def test_simple_fusion_retriever_reranks_by_title_and_file_diversity() -> None:
    """Fusion 出口应在候选池中提升标题命中文档，并优先保留不同来源文件。"""

    fusion = object.__new__(retriever_module.SimpleFusionRetriever)
    fusion._kb_ids = {"kb-a"}
    fusion.top_k = 3
    nodes = [
        _scored_node("rice-1", 0.6, kb_id="kb-a", file_name="06稻谷控温储藏技术规程t6.docx"),
        _scored_node("rice-2", 0.5, kb_id="kb-a", file_name="06稻谷控温储藏技术规程t6.docx"),
        _scored_node("aircon", 0.1, kb_id="kb-a", file_name="17空调控温储粮技术规程20160624.docx"),
        _scored_node("other", 0.4, kb_id="kb-a", file_name="20超高大平房仓安全储粮技术规程.docx"),
    ]

    result = fusion._rerank_and_trim_nodes(nodes, "空调控温储粮技术规程适用于什么条件下的平房仓？")

    assert result[0].node.node_id == "aircon"
    assert "rice-2" not in [item.node.node_id for item in result]
    assert {item.node.node_id for item in result} == {"aircon", "rice-1", "other"}
