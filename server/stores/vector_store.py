"""
模块功能：
- 按配置创建向量存储实例（Chroma/Elasticsearch/LanceDB/Simple）。

执行逻辑：
1. 根据 type 路由到对应向量数据库实现。
2. 对 Chroma 查询参数做兼容修补，避免空过滤器触发异常。
3. 根据运行环境初始化全局 VECTOR_STORE。
"""

import os
import config


def create_vector_store(type=config.DEFAULT_VS_TYPE):
    """
    创建指定类型的向量存储。

    Args:
        type: 向量存储类型标识（chroma/es/lancedb/simple）。

    Returns:
        VectorStore: 对应类型的向量存储实例。

    Raises:
        ValueError: 传入不支持的向量存储类型时抛出。
    """
    # 开发模式强制使用 simple，忽略 type 参数
    if config.DEV_MODE:
        from llama_index.core.vector_stores import SimpleVectorStore
        persist_path = os.path.join(config.STORAGE_DIR, "vector")
        if os.path.exists(persist_path):
            return SimpleVectorStore.from_persist_dir(persist_path)
        else:
            return SimpleVectorStore()
    
    # 生产模式根据配置选择
    if type == "chroma":
        # Chroma 适合本地持久化场景，默认作为生产环境主向量库。

        import chromadb
        from llama_index.vector_stores.chroma import ChromaVectorStore

        db = chromadb.PersistentClient(path=".chroma")
        chroma_collection = db.get_or_create_collection("think")

        try:
            _orig_query = chroma_collection.query

            def _safe_query(*args, **kwargs):
                """
                对 Chroma 查询参数做兼容性清洗，避免空过滤器触发异常。

                Returns:
                    Any: 原始 query 的返回结果。
                """
                # Chroma 的 where/where_document 不能传空字典，需改成"未传参"语义。
                if kwargs.get("where") == {}:
                    kwargs.pop("where", None)
                if kwargs.get("where_document") == {}:
                    kwargs.pop("where_document", None)
                return _orig_query(*args, **kwargs)
            chroma_collection.query = _safe_query
        except Exception as e:
            # 修补失败不阻断服务启动，最多影响部分过滤查询兼容性。
            print(f"[warn] failed to patch chroma_collection.query: {e}")

        chroma_vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        return chroma_vector_store
    elif type == "es":
        # Elasticsearch 方案保留用于可扩展部署场景。

        from llama_index.vector_stores.elasticsearch import ElasticsearchStore
        from llama_index.vector_stores.elasticsearch import AsyncDenseVectorStrategy

        es_vector_store = ElasticsearchStore(
            es_url="http://localhost:9200",
            index_name="think",
            retrieval_strategy=AsyncDenseVectorStrategy(hybrid=False),
        )
        return es_vector_store
    elif type == "lancedb":
        # LanceDB 适合本地嵌入式场景，支持混合检索扩展。
        from llama_index.vector_stores.lancedb import LanceDBVectorStore
        from lancedb.rerankers import LinearCombinationReranker
        reranker = LinearCombinationReranker(weight=0.9)

        lance_vector_store = LanceDBVectorStore(
            uri=".lancedb", mode="overwrite", query_type="vector", reranker=reranker
        )
        return lance_vector_store
    else:
        raise ValueError(f"Invalid vector store type: {type}")


# 延迟初始化，避免模块加载时依赖未就绪
_VECTOR_STORE = None


def get_vector_store():
    """
    功能：
    获取向量存储实例（延迟初始化）

    输出：
    - VectorStore: 向量存储实例

    执行逻辑：
    1. 首次调用时创建实例
    2. 后续调用返回缓存实例
    """
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        _VECTOR_STORE = create_vector_store()
    return _VECTOR_STORE


# 保持向后兼容
VECTOR_STORE = None
