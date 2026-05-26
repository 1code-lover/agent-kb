"""
模块功能：
- 创建并返回重排模型（SentenceTransformerRerank）。

执行逻辑：
1. 根据模型名称读取配置路径。
2. 优先加载本地模型目录中的重排模型。
3. 返回可用于 query_engine 的重排器实例。
"""

import os
from llama_index.core.postprocessor import SentenceTransformerRerank
from config import DEFAULT_RERANKER_MODEL, RERANKER_MODEL_TOP_N, RERANKER_MODEL_PATH, MODEL_DIR
from server.utils.hf_mirror import use_hf_mirror


def create_reranker_model(model_name=DEFAULT_RERANKER_MODEL, top_n=RERANKER_MODEL_TOP_N) -> SentenceTransformerRerank:
    """
    创建重排模型实例。

    Args:
        model_name: 重排模型名称键。
        top_n: 重排后保留的节点数量。

    Returns:
        SentenceTransformerRerank | None: 成功返回模型实例，失败返回 None。
    """
    try:
        use_hf_mirror()
        model_path = RERANKER_MODEL_PATH[model_name]
        if MODEL_DIR is not None:
            path = f"./{MODEL_DIR}/{model_path}"
            if os.path.exists(path):
                # 本地路径命中时优先加载，避免冷启动下载模型。
                model_path = path
        rerank_model = SentenceTransformerRerank(model=model_path, top_n=top_n)
        print(f"created rerank model: {model_name}")
        return rerank_model
    except Exception as e:
        return None