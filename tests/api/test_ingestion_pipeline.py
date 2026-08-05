"""ingestion pipeline 诊断与回退路径测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from llama_index.core.ingestion import DocstoreStrategy

import server.ingestion as ingestion


class _FakeVectorStore:
    """记录 add 调用的最小向量存储替身。"""

    def __init__(self) -> None:
        self.add = MagicMock()


class _FakeCache:
    """记录 cache get / put 调用。"""

    def __init__(self, cached_nodes):
        self.get = MagicMock(return_value=cached_nodes)
        self.put = MagicMock()


def _build_pipeline(
    *,
    input_nodes,
    docstore=object(),
    vector_store=None,
    strategy=DocstoreStrategy.UPSERTS,
    transformations=None,
    cache=None,
    disable_cache=False,
):
    """构造可直接调用 run 的最小 pipeline 对象。"""
    pipeline = ingestion.AdvancedIngestionPipeline.__new__(ingestion.AdvancedIngestionPipeline)
    object.__setattr__(pipeline, "docstore", docstore)
    object.__setattr__(pipeline, "vector_store", vector_store)
    object.__setattr__(pipeline, "docstore_strategy", strategy)
    object.__setattr__(pipeline, "transformations", list(transformations or []))
    object.__setattr__(pipeline, "cache", cache)
    object.__setattr__(pipeline, "disable_cache", disable_cache)
    object.__setattr__(pipeline, "_prepare_inputs", MagicMock(return_value=list(input_nodes)))
    object.__setattr__(pipeline, "_handle_upserts", MagicMock(side_effect=lambda nodes: list(nodes)))
    object.__setattr__(pipeline, "_handle_duplicates", MagicMock(side_effect=lambda nodes: list(nodes)))
    object.__setattr__(pipeline, "_update_docstore", MagicMock())
    return pipeline


def test_stage_timing_defaults_and_transform_stage_mapping_are_stable() -> None:
    """默认 stage timings 和 transform 名称映射应稳定可预期。"""
    timings = ingestion._new_ingestion_stage_timings()
    assert timings == {
        "document_load_ms": 0.0,
        "chunking_ms": 0.0,
        "embedding_ms": 0.0,
        "title_extract_ms": 0.0,
        "vector_store_ms": 0.0,
        "docstore_ms": 0.0,
        "index_insert_ms": 0.0,
        "total_ms": 0.0,
    }

    pipeline = ingestion.AdvancedIngestionPipeline.__new__(ingestion.AdvancedIngestionPipeline)
    assert pipeline._resolve_transform_stage_key(object(), 0) == "chunking_ms"
    assert pipeline._resolve_transform_stage_key(object(), 1) == "embedding_ms"
    assert pipeline._resolve_transform_stage_key(object(), 2) == "title_extract_ms"
    assert pipeline._resolve_transform_stage_key(SimpleNamespace(), 3) == "transform_simplenamespace_3_ms"


@pytest.mark.parametrize(
    ("diagnostics", "num_workers"),
    [
        (None, None),
        ({"stage_timings": {}}, 2),
    ],
)
def test_run_delegates_to_super_when_manual_diagnostics_not_supported(
    monkeypatch: pytest.MonkeyPatch,
    diagnostics,
    num_workers,
) -> None:
    """未提供 diagnostics 或启用多 worker 时，应回退到父类实现。"""
    pipeline = ingestion.AdvancedIngestionPipeline.__new__(ingestion.AdvancedIngestionPipeline)
    captured = {}

    def fake_super_run(self, **kwargs):
        captured.update(kwargs)
        return ["node-a"]

    monkeypatch.setattr(ingestion.IngestionPipeline, "run", fake_super_run)

    result = pipeline.run(
        documents=["doc-a"],
        diagnostics=diagnostics,
        num_workers=num_workers,
        cache_collection="kb-a",
        in_place=False,
        store_doc_text=False,
    )

    assert result == ["node-a"]
    assert captured["documents"] == ["doc-a"]
    assert captured["cache_collection"] == "kb-a"
    assert captured["in_place"] is False
    assert captured["store_doc_text"] is False
    assert captured["num_workers"] == num_workers


def test_run_falls_back_to_duplicates_only_when_vector_store_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无 vector_store 时，UPSERTS 应降级为 duplicates_only 并发出告警。"""
    input_nodes = [SimpleNamespace(embedding=None)]
    pipeline = _build_pipeline(input_nodes=input_nodes, docstore=object(), vector_store=None)
    diagnostics = {"stage_timings": {"document_load_ms": 12.0}}

    monkeypatch.setattr(ingestion, "get_tqdm_iterable", lambda transforms, *_: list(transforms))

    with pytest.warns(UserWarning, match="falling back to 'duplicates_only'"):
        result = pipeline.run(documents=["doc-a"], diagnostics=diagnostics)

    assert result == input_nodes
    pipeline._handle_upserts.assert_not_called()
    pipeline._handle_duplicates.assert_called_once_with(input_nodes)
    pipeline._update_docstore.assert_called_once_with(
        input_nodes,
        effective_strategy=DocstoreStrategy.DUPLICATES_ONLY,
        store_doc_text=True,
    )
    assert diagnostics["node_count"] == 1
    assert diagnostics["nodes_with_embedding_count"] == 0
    assert diagnostics["nodes_without_embedding_count"] == 1
    assert diagnostics["stage_timings"]["document_load_ms"] == 12.0
    assert diagnostics["stage_timings"]["docstore_ms"] >= 0.0
    assert diagnostics["stage_timings"]["total_ms"] >= 0.0


def test_run_uses_cached_transform_result_and_updates_vector_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cache hit 时不应重复执行 transform，但仍应写入向量库与 docstore。"""
    input_nodes = [SimpleNamespace(embedding=None, node_id="raw-1")]
    cached_nodes = [
        SimpleNamespace(embedding=[0.1, 0.2], node_id="vec-1"),
        SimpleNamespace(embedding=None, node_id="text-2"),
    ]
    cache = _FakeCache(cached_nodes)
    vector_store = _FakeVectorStore()

    def should_not_run(_nodes, **_kwargs):
        raise AssertionError("cache hit should bypass transform execution")

    pipeline = _build_pipeline(
        input_nodes=input_nodes,
        docstore=object(),
        vector_store=vector_store,
        transformations=[should_not_run],
        cache=cache,
    )
    diagnostics = {}

    monkeypatch.setattr(ingestion, "get_tqdm_iterable", lambda transforms, *_: list(transforms))
    monkeypatch.setattr(ingestion, "get_transformation_hash", lambda *_args, **_kwargs: "cache-key")

    result = pipeline.run(
        documents=["doc-a"],
        diagnostics=diagnostics,
        cache_collection="kb-cache",
    )

    assert result == cached_nodes
    cache.get.assert_called_once_with("cache-key", collection="kb-cache")
    cache.put.assert_not_called()
    vector_store.add.assert_called_once_with([cached_nodes[0]])
    pipeline._handle_upserts.assert_called_once_with(input_nodes)
    pipeline._update_docstore.assert_called_once_with(
        input_nodes,
        effective_strategy=DocstoreStrategy.UPSERTS,
        store_doc_text=True,
    )
    assert diagnostics["node_count"] == 2
    assert diagnostics["nodes_with_embedding_count"] == 1
    assert diagnostics["nodes_without_embedding_count"] == 1
    assert diagnostics["stage_timings"]["vector_store_ms"] >= 0.0


def test_run_writes_cache_on_miss_and_supports_pipeline_without_docstore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cache miss 时应写回缓存，且无 docstore / vector_store 时仍可返回 transform 结果。"""
    input_nodes = [SimpleNamespace(embedding=None, node_id="raw-1")]
    transformed_nodes = [SimpleNamespace(embedding=None, node_id="chunk-1")]
    cache = _FakeCache(None)

    def transform(nodes, **_kwargs):
        assert list(nodes) == input_nodes
        return transformed_nodes

    pipeline = _build_pipeline(
        input_nodes=input_nodes,
        docstore=None,
        vector_store=None,
        transformations=[transform],
        cache=cache,
    )
    diagnostics = {}

    monkeypatch.setattr(ingestion, "get_tqdm_iterable", lambda transforms, *_: list(transforms))
    monkeypatch.setattr(ingestion, "get_transformation_hash", lambda *_args, **_kwargs: "cache-miss-key")

    result = pipeline.run(documents=["doc-a"], diagnostics=diagnostics, in_place=False)

    assert result == transformed_nodes
    cache.get.assert_called_once_with("cache-miss-key", collection=None)
    cache.put.assert_called_once_with("cache-miss-key", transformed_nodes, collection=None)
    pipeline._handle_upserts.assert_not_called()
    pipeline._handle_duplicates.assert_not_called()
    pipeline._update_docstore.assert_not_called()
    assert diagnostics["node_count"] == 1
    assert diagnostics["nodes_with_embedding_count"] == 0
    assert diagnostics["nodes_without_embedding_count"] == 1


def test_run_normalizes_none_transform_result_before_cache_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """transform 返回 None 时，应归一化为空列表并写入缓存，避免空文档导入崩溃。"""
    input_nodes = [SimpleNamespace(embedding=None, node_id="raw-1")]
    cache = _FakeCache(None)
    vector_store = _FakeVectorStore()

    def transform(nodes, **_kwargs):
        assert list(nodes) == input_nodes
        return None

    pipeline = _build_pipeline(
        input_nodes=input_nodes,
        docstore=object(),
        vector_store=vector_store,
        transformations=[transform],
        cache=cache,
    )
    diagnostics = {}

    monkeypatch.setattr(ingestion, "get_tqdm_iterable", lambda transforms, *_: list(transforms))
    monkeypatch.setattr(ingestion, "get_transformation_hash", lambda *_args, **_kwargs: "cache-none-key")

    result = pipeline.run(documents=["doc-a"], diagnostics=diagnostics)

    assert result == []
    cache.get.assert_called_once_with("cache-none-key", collection=None)
    cache.put.assert_called_once_with("cache-none-key", [], collection=None)
    vector_store.add.assert_not_called()
    pipeline._handle_upserts.assert_called_once_with(input_nodes)
    pipeline._update_docstore.assert_called_once_with(
        input_nodes,
        effective_strategy=DocstoreStrategy.UPSERTS,
        store_doc_text=True,
    )
    assert diagnostics["node_count"] == 0
    assert diagnostics["nodes_with_embedding_count"] == 0
    assert diagnostics["nodes_without_embedding_count"] == 0


def test_run_raises_for_invalid_docstore_strategy() -> None:
    """docstore/vector_store 同时存在时，非法策略应显式报错。"""
    pipeline = _build_pipeline(
        input_nodes=[SimpleNamespace(embedding=None)],
        docstore=object(),
        vector_store=_FakeVectorStore(),
        strategy="invalid-strategy",
    )

    with pytest.raises(ValueError, match="Invalid docstore strategy"):
        pipeline.run(documents=["doc-a"], diagnostics={})
