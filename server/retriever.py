"""
模块功能：
- 提供 ThinkRAG 的检索器实现，包括 BM25、混合检索与融合检索。

执行逻辑：
1. 通过中文分词器修复 BM25 对中文检索不友好的问题。
2. 在查询前根据语料规模动态约束 top_k，避免小语料报错。
3. 组合向量检索与 BM25 检索，输出更稳健的召回结果。
"""

from llama_index.core.retrievers import BaseRetriever
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.indices.vector_store.retrievers.retriever import log_vector_store_query_result
from llama_index.core.schema import BaseNode
from llama_index.core.schema import MetadataMode
from llama_index.core.vector_stores.utils import metadata_dict_to_node, node_to_metadata_dict
from llama_index.core.vector_stores.types import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQueryResult,
)
from llama_index.retrievers.bm25 import BM25Retriever

# BM25Retriever 默认分词器对中文支持不足：
# https://github.com/run-llama/llama_index/issues/13866

import jieba
from typing import List


def build_kb_metadata_filters(kb_ids: list[str] | None):
    """按 kb_id 构建向量检索与 BM25 检索共用的 metadata 过滤条件。"""
    if not kb_ids:
        return None
    return MetadataFilters(
        filters=[
            MetadataFilter(key="kb_id", value=kb_id, operator=FilterOperator.EQ)
            for kb_id in kb_ids
        ],
        condition=FilterCondition.OR,
    )


def filter_bm25_compatible_nodes(nodes: list[BaseNode]) -> list[BaseNode]:
    """过滤出与 BM25 索引构建兼容的节点，跳过空内容或元数据异常的节点。"""
    compatible_nodes: list[BaseNode] = []
    skipped: list[str] = []

    for node in nodes or []:
        try:
            content = node.get_content(metadata_mode=MetadataMode.EMBED)
            if not isinstance(content, str) or not content.strip():
                skipped.append(getattr(node, "node_id", "<unknown>"))
                continue

            metadata_dict_to_node(node_to_metadata_dict(node))
            compatible_nodes.append(node)
        except Exception:
            skipped.append(getattr(node, "node_id", "<unknown>"))

    if skipped:
        preview = ", ".join(skipped[:3])
        print(
            "Skip BM25-incompatible nodes before retriever build: "
            f"{preview}; skipped={len(skipped)}"
        )

    return compatible_nodes


def chinese_tokenizer(text: str) -> List[str]:
    """
    功能：
    - 对中文文本执行分词，供 BM25 索引与检索使用。

    输入：
    - text(str): 原始查询或文档文本。

    执行逻辑：
    1. 调用 jieba.cut 切词。
    2. 将生成器结果转换为列表返回。

    输出：
    - List[str]: 分词结果列表。
    """
    return list(jieba.cut(text))


def clamp_top_k_to_corpus(vector_index, top_k: int) -> int:
    """
    功能：
    - 约束 top_k 不超过当前语料规模，避免检索层在小语料下异常。

    输入：
    - vector_index: 向量索引实例。
    - top_k(int): 期望召回数。

    执行逻辑：
    1. 读取 docstore 和 vector_store 的可用数量。
    2. 以较小语料规模作为有效上限。
    3. 对异常场景回退到安全最小值。

    输出：
    - int: 安全可用的 top_k。
    """
    try:
        sizes = []

        # 以文档库规模作为上限候选。
        doc_sz = len(vector_index.docstore.docs)
        sizes.append(doc_sz)

        # 额外读取向量库规模，确保双存储都不会超界。
        vs = getattr(vector_index, "vector_store", None) or getattr(vector_index, "_vector_store", None)
        col = getattr(vs, "_collection", None) if vs is not None else None
        if col is not None and hasattr(col, "count"):
            sizes.append(int(col.count()))

        effective = min(sizes) if sizes else int(top_k)
        return max(1, min(int(top_k), int(effective)))
    except Exception:
        return max(1, int(top_k))


class SafeVectorIndexRetriever(VectorIndexRetriever):
    """在标准 VectorIndexRetriever 基础上加固：剔除失效向量 id 和维度不兼容的历史 embedding。"""

    def _filter_stale_query_result_ids(self, query_result: VectorStoreQueryResult) -> VectorStoreQueryResult:
        """
        功能：
        - 过滤 vector_store 返回结果中不存在于 index_struct.nodes_dict 的陈旧 node_id。

        背景：
        - 历史导入/删除操作可能导致 vector_store 里残留已失效的向量 id。
        - LlamaIndex 原生 VectorIndexRetriever 遇到这类 id 会直接抛 KeyError，导致整次查询失败。
        - 这里提前剔除，保证检索链路对历史脏数据具备容错能力。
        """
        if query_result.nodes is not None or not query_result.ids:
            return query_result

        index_struct = getattr(self._index, "index_struct", None)
        nodes_dict = getattr(index_struct, "nodes_dict", {}) or {}
        valid_ids: list[str] = []
        valid_similarities: list[float] = []
        skipped_ids: list[str] = []

        for position, node_id in enumerate(query_result.ids):
            if node_id in nodes_dict:
                valid_ids.append(node_id)
                if query_result.similarities is not None and position < len(query_result.similarities):
                    valid_similarities.append(query_result.similarities[position])
            else:
                skipped_ids.append(node_id)

        if skipped_ids:
            preview = ", ".join(skipped_ids[:3])
            print(
                "Skip stale vector ids not found in index_struct.nodes_dict: "
                f"{preview}; skipped={len(skipped_ids)}"
            )

        similarities = valid_similarities if query_result.similarities is not None else None
        return VectorStoreQueryResult(nodes=None, similarities=similarities, ids=valid_ids)

    def _prune_incompatible_vector_embeddings(self, query_embedding) -> int:
        """剔除与当前查询向量维度不一致的历史 embedding，避免向量检索时因维度不匹配报错。"""
        if query_embedding is None:
            return 0

        try:
            expected_dim = len(query_embedding)
        except TypeError:
            return 0

        if expected_dim <= 0:
            return 0

        vector_data = getattr(self._vector_store, "data", None)
        embedding_dict = getattr(vector_data, "embedding_dict", None)
        if not isinstance(embedding_dict, dict) or not embedding_dict:
            return 0

        metadata_dict = getattr(vector_data, "metadata_dict", None)
        ref_doc_dict = getattr(vector_data, "text_id_to_ref_doc_id", None)
        invalid_ids: list[str] = []

        for node_id, embedding in embedding_dict.items():
            try:
                current_dim = len(embedding)
            except TypeError:
                current_dim = -1
            if current_dim != expected_dim:
                invalid_ids.append(node_id)

        if not invalid_ids:
            return 0

        for node_id in invalid_ids:
            embedding_dict.pop(node_id, None)
            if isinstance(metadata_dict, dict):
                metadata_dict.pop(node_id, None)
            if isinstance(ref_doc_dict, dict):
                ref_doc_dict.pop(node_id, None)

        preview = ", ".join(invalid_ids[:3])
        print(
            "Pruned incompatible vector embeddings before retrieval: "
            f"expected_dim={expected_dim}, removed={len(invalid_ids)}, sample={preview}"
        )
        return len(invalid_ids)

    def _get_nodes_with_embeddings(self, query_bundle_with_embeddings):
        """在获取节点前先剔除失效向量 id 和不兼容 embedding，再走 LlamaIndex 原生查询流程。

        说明：本版 LlamaIndex 的父类 ``_get_nodes_with_embeddings`` 已通过
        ``_build_node_list_from_query_result`` 统一完成 docstore 回填与计分。
        这里只在其之前插入 stale-id / 不兼容 embedding 的加固过滤，然后委托父类
        原生流程完成节点组装，避免依赖各版本内部私有方法。
        """
        query = self._build_vector_store_query(query_bundle_with_embeddings)
        self._prune_incompatible_vector_embeddings(getattr(query, "query_embedding", None))
        query_result = self._vector_store.query(query, **self._kwargs)
        query_result = self._filter_stale_query_result_ids(query_result)

        nodes = self._build_node_list_from_query_result(query_result)
        log_vector_store_query_result(query_result)
        return nodes

    async def _aget_nodes_with_embeddings(self, query_bundle_with_embeddings):
        """异步获取节点：加固过滤后委托父类原生流程完成节点组装。"""
        query = self._build_vector_store_query(query_bundle_with_embeddings)
        self._prune_incompatible_vector_embeddings(getattr(query, "query_embedding", None))
        query_result = await self._vector_store.aquery(query, **self._kwargs)
        query_result = self._filter_stale_query_result_ids(query_result)

        nodes = self._build_node_list_from_query_result(query_result)
        log_vector_store_query_result(query_result)
        return nodes


class SimpleBM25Retriever(BM25Retriever):
    @classmethod
    def from_defaults(cls, index, similarity_top_k, **kwargs) -> "BM25Retriever":
        """
        功能：
        - 创建适配中文与小语料场景的 BM25 检索器实例。

        输入：
        - index: 索引实例（用于读取 docstore）。
        - similarity_top_k(int): 目标召回数量。
        - **kwargs: 透传给 BM25Retriever 的扩展参数。

        执行逻辑：
        1. 基于 docstore 语料量限制 top_k。
        2. 使用 chinese_tokenizer 作为分词器。
        3. 返回标准 BM25Retriever 对象。

        输出：
        - BM25Retriever: 初始化后的 BM25 检索器。
        """
        docstore = index.docstore
        nodes = filter_bm25_compatible_nodes(list(docstore.docs.values()))

        # 约束 top_k 不超过语料规模，否则 bm25s 库内部会抛 ValueError。
        corpus_size = len(nodes)
        similarity_top_k = max(1, min(int(similarity_top_k), int(corpus_size)))

        # BM25Retriever 基于 bm25s 自建语料索引，不接受 metadata filters；
        # kb_id 维度过滤由 SimpleHybridRetriever 在融合层兜底完成。
        # 显式剥离 filters，避免透传给底层 from_defaults 触发
        # `unexpected keyword argument 'filters'`。
        forward_kwargs = {key: value for key, value in kwargs.items() if key != "filters"}

        return BM25Retriever.from_defaults(
            nodes=nodes,
            similarity_top_k=similarity_top_k,
            verbose=True,
            tokenizer=chinese_tokenizer,
            **forward_kwargs,
        )


class SimpleHybridRetriever(BaseRetriever):
    """
    功能：
    - 融合向量检索与 BM25 检索，返回去重后的 Top-K 结果。
    """

    def __init__(self, vector_index, top_k=2):
        """
        输入：
        - vector_index: 向量索引实例。
        - top_k(int): 最终返回节点数。

        执行逻辑：
        1. 约束 top_k 到语料范围。
        2. 初始化向量检索器。
        3. 初始化 BM25 检索器。
        """
        top_k = clamp_top_k_to_corpus(vector_index, top_k)
        self.top_k = top_k

        # 向量检索负责语义召回。
        self.vector_retriever = SafeVectorIndexRetriever(
            index=vector_index, similarity_top_k=top_k, verbose=True,
        )

        # BM25 检索负责关键词匹配召回。
        self.bm25_retriever = SimpleBM25Retriever.from_defaults(
            index=vector_index, similarity_top_k=top_k,
        )

        super().__init__()

    def _retrieve(self, query, **kwargs):
        """
        功能：
        - 执行混合检索并返回去重后的结果。

        输入：
        - query: 查询文本。
        - **kwargs: 透传检索参数。

        执行逻辑：
        1. 先执行 BM25 检索并进行分数归一化。
        2. 再执行向量检索。
        3. 合并结果并按 node_id 去重，截断到 top_k。

        输出：
        - list: 检索节点列表。
        """
        bm25_nodes = self.bm25_retriever.retrieve(query, **kwargs)

        # BM25 原始分数在不同查询之间不可直接比较，需先归一化。
        min_score = min(item.score for item in bm25_nodes)
        max_score = max(item.score for item in bm25_nodes)

        if max_score != min_score:
            normalized_data = [(item.score - min_score) / (max_score - min_score) for item in bm25_nodes]
            for item, normalized_score in zip(bm25_nodes, normalized_data):
                item.score = normalized_score
        else:
            # 分数完全相同的极端情况，统一赋默认值避免后续排序不稳定。
            for item in bm25_nodes:
                item.score = 0.5

        vector_nodes = self.vector_retriever.retrieve(query, **kwargs)

        # 合并两路召回并去重，优先保留先出现的高相关结果。
        all_nodes = []
        node_ids = set()
        count = 0
        for n in vector_nodes + bm25_nodes:
            if n.node.node_id not in node_ids:
                all_nodes.append(n)
                node_ids.add(n.node.node_id)
                count += 1
            if count >= self.top_k:
                break
        for node in all_nodes:
            print(f"Hybrid Retrieved Node: {node.node_id} - Score: {node.score:.2f} - {node.text[:10]}...\n-----")
        return all_nodes

from llama_index.core.retrievers import QueryFusionRetriever
from enum import Enum

class FUSION_MODES(str, Enum):
    """融合检索模式枚举，直接映射 LlamaIndex 支持的 mode。"""

    RECIPROCAL_RANK = "reciprocal_rerank"  # apply reciprocal rank fusion
    RELATIVE_SCORE = "relative_score"  # apply relative score fusion
    DIST_BASED_SCORE = "dist_based_score"  # apply distance-based score fusion
    SIMPLE = "simple"  # simple re-ordering of results based on original scores


class SimpleFusionRetriever(QueryFusionRetriever):
    """
    功能：
    - 使用 QueryFusionRetriever 融合向量检索与 BM25 检索结果。
    """

    def __init__(self, vector_index, top_k=2, mode=FUSION_MODES.DIST_BASED_SCORE, kb_ids: list[str] | None = None):
        """
        输入：
        - vector_index: 向量索引实例。
        - top_k(int): 最终召回数量。
        - mode(FUSION_MODES): 融合策略。

        执行逻辑：
        1. 构建向量检索器与 BM25 检索器。
        2. 注入固定权重并禁用多查询扩展（num_queries=1）。
        3. 初始化 QueryFusionRetriever。
        """
        top_k = clamp_top_k_to_corpus(vector_index, top_k)
        self.top_k = top_k
        self.mode = mode
        self._kb_ids: set[str] | None = set(kb_ids) if kb_ids else None
        self._kb_filters = build_kb_metadata_filters(kb_ids)

        self.vector_retriever = SafeVectorIndexRetriever(
            index=vector_index, similarity_top_k=top_k, verbose=True, filters=self._kb_filters,
        )

        self.bm25_retriever = SimpleBM25Retriever.from_defaults(
            index=vector_index, similarity_top_k=top_k, filters=self._kb_filters,
        )

        super().__init__(
            [self.vector_retriever, self.bm25_retriever],
            retriever_weights=[0.6, 0.4],
            similarity_top_k=top_k,
            num_queries=1,  # set this to 1 to disable query generation
            mode=mode,
            use_async=True,
            verbose=True,
        )


    def _node_allowed_by_kb(self, node) -> bool:
        """判断节点是否属于当前查询限定的知识库范围。"""
        if not self._kb_ids:
            return True
        kb_id = getattr(getattr(node, "node", None), "metadata", {}).get("kb_id")
        if kb_id is None:
            return "default" in self._kb_ids
        return kb_id in self._kb_ids

    def _filter_nodes_by_kb(self, nodes):
        """在融合检索器返回层兜底过滤 kb_id，避免后置过滤遗漏。"""
        if not self._kb_ids:
            return nodes
        return [node for node in nodes if self._node_allowed_by_kb(node)]

    def _retrieve(self, query_bundle):
        """同步融合检索后按 kb_id 过滤结果。"""
        return self._filter_nodes_by_kb(super()._retrieve(query_bundle))

    async def _aretrieve(self, query_bundle):
        """异步融合检索后按 kb_id 过滤结果。"""
        return self._filter_nodes_by_kb(await super()._aretrieve(query_bundle))
