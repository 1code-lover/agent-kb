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
from config import DEFAULT_EMBEDDING_MODEL, EMBEDDING_MODEL_PATH, MODEL_DIR
from server.utils.hf_mirror import use_hf_mirror
from server.utils.model_paths import resolve_local_model_path


def _remote_download_allowed(allow_remote_download=None):
    """读取运行时是否允许 embedding 初始化走远程下载。"""
    if allow_remote_download is not None:
        return bool(allow_remote_download)
    import config

    return bool(getattr(config, "EMBEDDING_ALLOW_REMOTE_DOWNLOAD", False))


def get_embedding_model_diagnostics(model_name=DEFAULT_EMBEDDING_MODEL, allow_remote_download=None):
    """
    返回 embedding 模型加载前的路径与下载诊断。

    Args:
        model_name: 配置中的 embedding 模型名称键。

    Returns:
        dict: 当前模型映射、本地缓存路径、远程回退和建议动作。
    """
    import config

    known_models = list(EMBEDDING_MODEL_PATH.keys())
    model_path = EMBEDDING_MODEL_PATH.get(model_name)
    local_path = None
    local_path_exists = False
    if model_path and MODEL_DIR is not None:
        local_path = resolve_local_model_path(MODEL_DIR, model_path)
        local_path_exists = os.path.exists(local_path)

    allow_remote = (not local_path_exists) and _remote_download_allowed(allow_remote_download)
    recommendations = []
    if model_name not in EMBEDDING_MODEL_PATH:
        recommendations.append(f"Select one of supported embedding models: {', '.join(known_models)}.")
    elif not local_path_exists:
        recommendations.append(
            f"Local embedding model cache is missing at {local_path}; runtime embedding initialization will not use remote download unless EMBEDDING_ALLOW_REMOTE_DOWNLOAD=1."
        )
        recommendations.append("Pre-download the model into localmodels/ to avoid slow or hanging cold starts.")
        if allow_remote:
            recommendations.append(
                f"Remote download is explicitly enabled; startup may download {model_path} from HuggingFace mirror."
            )

    return {
        "model_name": model_name,
        "known_models": known_models,
        "hf_model_path": model_path,
        "model_dir": MODEL_DIR,
        "local_path": local_path,
        "local_path_exists": local_path_exists,
        "load_source": "local" if local_path_exists else "remote",
        "allow_remote_download": allow_remote,
        "hf_endpoint": getattr(config, "HF_ENDPOINT", ""),
        "recommendations": recommendations,
    }


def create_embedding_model(model_name=DEFAULT_EMBEDDING_MODEL):
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
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        use_hf_mirror()
        diagnostics = get_embedding_model_diagnostics(model_name)
        if diagnostics["hf_model_path"] is None:
            raise ValueError(f"Unknown embedding model: {model_name}")
        if not diagnostics["local_path_exists"] and not diagnostics["allow_remote_download"]:
            raise RuntimeError(
                "Local embedding model cache is missing at "
                f"{diagnostics['local_path']}; run `python -m scripts.prepare_embedding_model_cache --download` "
                "with the project runtime (desktop/build scripts can pin it via KB_PYTHON), or set "
                "EMBEDDING_ALLOW_REMOTE_DOWNLOAD=1 to allow runtime remote download."
            )
        model_path = diagnostics["local_path"] if diagnostics["local_path_exists"] else diagnostics["hf_model_path"]
        embed_model = HuggingFaceEmbedding(model_name=model_path)
        Settings.embed_model = embed_model
        print(f"created embed model: {model_path}")
    except Exception as e:
        print(f"An error occurred while creating the embedding model: {type(e).__name__}: {e}")
        Settings._embed_model = None

    return getattr(Settings, "_embed_model", None)
