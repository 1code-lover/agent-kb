"""
模块功能：
- 创建并返回 ThinkRAG 的查询引擎实例。

执行逻辑：
1. 根据配置决定是否启用重排器（reranker）。
2. 构建融合检索器（向量检索 + BM25）。
3. 组装 LlamaIndex 的 RetrieverQueryEngine 并返回。

关键依赖：
- server.retriever.SimpleFusionRetriever
- server.models.reranker.create_reranker_model
- server.prompt 中的问答与 refine 模板
"""

import config as config
from server.models.reranker import create_reranker_model
from server.prompt import text_qa_template, refine_template
from server.retriever import SimpleFusionRetriever
from llama_index.core.query_engine import RetrieverQueryEngine


def create_query_engine(
    index,
    top_k=config.TOP_K,
    response_mode=config.RESPONSE_MODE,
    use_reranker=config.USE_RERANKER,
    top_n=config.RERANKER_MODEL_TOP_N,
    reranker=config.DEFAULT_RERANKER_MODEL,
):
    """
    功能：
    - 构建一个带混合检索与可选重排能力的查询引擎。

    输入：
    - index: LlamaIndex 的向量索引实例。
    - top_k(int): 检索召回数量上限。
    - response_mode(str): LlamaIndex 响应合成模式。
    - use_reranker(bool): 是否启用重排模型。
    - top_n(int): 重排后保留的候选数量。
    - reranker(str): 重排模型名称。

    执行逻辑：
    1. 按 use_reranker 动态创建 node_postprocessors。
    2. 使用 SimpleFusionRetriever 构建检索器。
    3. 用统一 Prompt 模板组装 RetrieverQueryEngine。

    输出：
    - RetrieverQueryEngine: 可直接执行 query/chat 的引擎实例。
    """
    # 仅在启用重排时注册后处理器，避免不必要的模型开销。
    node_postprocessors = [create_reranker_model(model_name=reranker, top_n=top_n)] if use_reranker else []
    retriever = SimpleFusionRetriever(vector_index=index, top_k=top_k)

    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        text_qa_template=text_qa_template,
        refine_template=refine_template,
        node_postprocessors=node_postprocessors,
        response_mode=response_mode,  # https://docs.llamaindex.ai/en/stable/api_reference/response_synthesizers/
        verbose=True,
        streaming=True,
    )

    return query_engine
