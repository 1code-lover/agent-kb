"""
模块功能：
- 创建并注册 embedding 模型，供索引构建和查询检索复用。

执行逻辑：
1. 根据模型名称读取配置映射路径。
2. 若本地模型目录存在则优先使用本地路径。
3. 初始化 HuggingFaceEmbedding 并写入 Settings.embed_model。
4. 失败时回退为 None，避免上层误用半初始化对象。
"""

import os
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from config import DEFAULT_EMBEDDING_MODEL, EMBEDDING_MODEL_PATH, MODEL_DIR
from server.utils.hf_mirror import use_hf_mirror


def create_embedding_model(model_name=DEFAULT_EMBEDDING_MODEL) -> HuggingFaceEmbedding:
    """
    创建 embedding 模型并注册到全局 Settings。

    Args:
        model_name: 配置中的 embedding 模型名称键。

    Returns:
        HuggingFaceEmbedding | None: 创建成功返回模型实例，失败返回 None。

    Note:
        若检测到本地模型目录存在同名路径，会优先加载本地模型以减少网络依赖。
    """
    try:
        use_hf_mirror()
        model_path = EMBEDDING_MODEL_PATH[model_name]
        if MODEL_DIR is not None:
            path = f"./{MODEL_DIR}/{model_path}"
            if os.path.exists(path):
                # 本地模型已准备好时优先使用，避免运行时拉取远端模型。
                model_path = path
        embed_model = HuggingFaceEmbedding(model_name=model_path)
        Settings.embed_model = embed_model
        print(f"created embed model: {model_path}")
    except Exception as e:
        print(f"An error occurred while creating the embedding model: {type(e).__name__}: {e}")
        Settings.embed_model = None

    return Settings.embed_model