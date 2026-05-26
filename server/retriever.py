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
from llama_index.retrievers.bm25 import BM25Retriever

# BM25Retriever 默认分词器对中文支持不足：
# https://github.com/run-llama/llama_index/issues/13866

import jieba
from typing import List


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

        # 限制 top_k，避免 bm25s 在语料极小时抛 ValueError。
        try:
            corpus_size = len(docstore.docs)
        except Exception:
            corpus_size = None

        if corpus_size is not None:
            similarity_top_k = max(1, min(int(similarity_top_k), int(corpus_size)))

        return BM25Retriever.from_defaults(
            docstore=docstore,
            similarity_top_k=similarity_top_k,
            verbose=True,
            tokenizer=chinese_tokenizer,
            **kwargs
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
        self.vector_retriever = VectorIndexRetriever(
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

    def __init__(self, vector_index, top_k=2, mode=FUSION_MODES.DIST_BASED_SCORE):
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

        self.vector_retriever = VectorIndexRetriever(
            index=vector_index, similarity_top_k=top_k, verbose=True,
        )

        self.bm25_retriever = SimpleBM25Retriever.from_defaults(
            index=vector_index, similarity_top_k=top_k,
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
