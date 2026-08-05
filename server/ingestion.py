"""
导入流水线封装。
- 统一当前项目对 ingestion pipeline 的初始化方式与诊断输出。

当前职责：
1. 复用 Settings 中已注册的 embedding 与 text splitter。
2. 用 AdvancedIngestionPipeline 固定 transformations 顺序。
3. 在 run 阶段补齐分阶段耗时诊断。

相关依赖：
- llama_index.core.ingestion.IngestionPipeline
- server.splitters.ChineseTitleExtractor
- server.stores.strage_context / ingestion_cache
"""

from __future__ import annotations

import time
import warnings
from typing import Any

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline, DocstoreStrategy
from llama_index.core.ingestion.pipeline import get_transformation_hash, get_tqdm_iterable

from server.splitters import ChineseTitleExtractor
from server.stores.strage_context import get_default_storage_context
from server.stores.ingestion_cache import INGESTION_CACHE


def _new_ingestion_stage_timings() -> dict[str, float]:
    """创建 ingestion 阶段耗时诊断的默认结构。"""
    return {
        "document_load_ms": 0.0,
        "chunking_ms": 0.0,
        "embedding_ms": 0.0,
        "title_extract_ms": 0.0,
        "vector_store_ms": 0.0,
        "docstore_ms": 0.0,
        "index_insert_ms": 0.0,
        "total_ms": 0.0,
    }


def _normalize_transformed_nodes(nodes: Any):
    """把 transform 返回的 None 归一化为 []，避免空文档导入在缓存层崩溃。"""
    if nodes is None:
        return []
    return nodes


class AdvancedIngestionPipeline(IngestionPipeline):
    def __init__(
        self,
        *,
        storage_context=None,
    ):
        """初始化 ingestion pipeline，并支持注入当前知识库的存储上下文。"""
        embed_model = Settings.embed_model
        text_splitter = Settings.text_splitter
        effective_storage_context = storage_context or get_default_storage_context()

        super().__init__(
            transformations=[
                text_splitter,
                embed_model,
                ChineseTitleExtractor(),
            ],
            docstore=effective_storage_context.docstore,
            vector_store=effective_storage_context.vector_store,
            cache=INGESTION_CACHE,
            docstore_strategy=DocstoreStrategy.UPSERTS,
        )

    def _resolve_transform_stage_key(self, transform: Any, index: int) -> str:
        """把 transform 序号映射成稳定的 diagnostics 字段名。"""
        if index == 0:
            return "chunking_ms"
        if index == 1:
            return "embedding_ms"
        if index == 2:
            return "title_extract_ms"
        return f"transform_{type(transform).__name__.lower()}_{index}_ms"

    def run(
        self,
        show_progress: bool = False,
        documents=None,
        nodes=None,
        cache_collection: str | None = None,
        in_place: bool = True,
        store_doc_text: bool = True,
        num_workers: int | None = None,
        diagnostics: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        """
        运行 ingestion pipeline。
        - 默认保持与 LlamaIndex IngestionPipeline 一致的行为。

        额外能力：
        - 当传入 diagnostics 时，记录每个阶段的耗时、Embedding 写入和向量入库情况。
        - 当不需要 diagnostics 时，继续走原有实现，避免无谓改动执行路径。
        """
        input_documents = documents or []
        print(f"Load {len(input_documents)} Documents")

        if diagnostics is None or (num_workers is not None and num_workers > 1):
            nodes_result = super().run(
                show_progress=show_progress,
                documents=documents,
                nodes=nodes,
                cache_collection=cache_collection,
                in_place=in_place,
                store_doc_text=store_doc_text,
                num_workers=num_workers,
                **kwargs,
            )
            print(f"Ingested {len(nodes_result)} Nodes")
            return nodes_result

        started_at = time.perf_counter()
        stage_timings = diagnostics.setdefault("stage_timings", _new_ingestion_stage_timings())
        for key, value in _new_ingestion_stage_timings().items():
            stage_timings.setdefault(key, value)

        input_nodes = self._prepare_inputs(documents, nodes)

        effective_strategy = self.docstore_strategy
        if (
            self.docstore is not None
            and self.vector_store is None
            and self.docstore_strategy in (DocstoreStrategy.UPSERTS, DocstoreStrategy.UPSERTS_AND_DELETE)
        ):
            warnings.warn(
                f"docstore_strategy='{self.docstore_strategy.value}' requires a vector store "
                "to apply upsert/delete semantics; falling back to 'duplicates_only' for this run. "
                "pipeline.docstore_strategy is unchanged.",
                UserWarning,
                stacklevel=3,
            )
            effective_strategy = DocstoreStrategy.DUPLICATES_ONLY

        if self.docstore is not None and self.vector_store is not None:
            if effective_strategy in (DocstoreStrategy.UPSERTS, DocstoreStrategy.UPSERTS_AND_DELETE):
                nodes_to_run = self._handle_upserts(input_nodes)
            elif effective_strategy == DocstoreStrategy.DUPLICATES_ONLY:
                nodes_to_run = self._handle_duplicates(input_nodes)
            else:
                raise ValueError(f"Invalid docstore strategy: {effective_strategy}")
        elif self.docstore is not None and self.vector_store is None:
            nodes_to_run = self._handle_duplicates(input_nodes)
        else:
            nodes_to_run = input_nodes

        if not in_place:
            transformed_nodes = list(nodes_to_run)
        else:
            transformed_nodes = nodes_to_run

        for index, transform in enumerate(get_tqdm_iterable(self.transformations, show_progress, "Applying transformations")):
            stage_key = self._resolve_transform_stage_key(transform, index)
            transform_started_at = time.perf_counter()
            if self.cache is not None and not self.disable_cache:
                cache_key = get_transformation_hash(transformed_nodes, transform)
                cached_nodes = self.cache.get(cache_key, collection=cache_collection)
                if cached_nodes is not None:
                    transformed_nodes = _normalize_transformed_nodes(cached_nodes)
                else:
                    transformed_nodes = _normalize_transformed_nodes(transform(transformed_nodes, **kwargs))
                    self.cache.put(cache_key, transformed_nodes, collection=cache_collection)
            else:
                transformed_nodes = _normalize_transformed_nodes(transform(transformed_nodes, **kwargs))
            stage_timings[stage_key] = round(
                float(stage_timings.get(stage_key, 0.0))
                + max(time.perf_counter() - transform_started_at, 0.0) * 1000,
                3,
            )

        output_nodes = list(transformed_nodes or [])
        nodes_with_embeddings = [node for node in output_nodes if getattr(node, "embedding", None) is not None]

        if self.vector_store is not None and nodes_with_embeddings:
            vector_started_at = time.perf_counter()
            self.vector_store.add(nodes_with_embeddings)
            stage_timings["vector_store_ms"] = round(
                float(stage_timings.get("vector_store_ms", 0.0))
                + max(time.perf_counter() - vector_started_at, 0.0) * 1000,
                3,
            )

        if self.docstore is not None:
            docstore_started_at = time.perf_counter()
            self._update_docstore(
                nodes_to_run,
                effective_strategy=effective_strategy,
                store_doc_text=store_doc_text,
            )
            stage_timings["docstore_ms"] = round(
                float(stage_timings.get("docstore_ms", 0.0))
                + max(time.perf_counter() - docstore_started_at, 0.0) * 1000,
                3,
            )

        diagnostics["node_count"] = len(output_nodes)
        diagnostics["nodes_with_embedding_count"] = len(nodes_with_embeddings)
        diagnostics["nodes_without_embedding_count"] = max(len(output_nodes) - len(nodes_with_embeddings), 0)
        stage_timings["total_ms"] = round(max(time.perf_counter() - started_at, 0.0) * 1000, 3)
        print(f"Ingested {len(output_nodes)} Nodes")
        return output_nodes
