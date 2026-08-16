"""
公共模型加载工具

提供本地模型路径解析和加载逻辑，避免 embedding.py 和 reranker.py 重复。
"""

import os
import logging
from typing import Optional
import config
from server.utils.model_paths import resolve_local_model_path

logger = logging.getLogger(__name__)

# 模块级变量，记录是否已设置过 HuggingFace 镜像
_hf_mirror_set = False


def resolve_model_path(
    model_name: str,
    model_path_map: dict[str, str],
    model_dir: Optional[str] = config.MODEL_DIR,
    allow_remote: bool = True,
) -> str:
    """
    解析模型路径，优先使用本地目录。
    
    Args:
        model_name: 模型名称（如 "bge-small-zh-v1.5"）
        model_path_map: 模型名称到 HuggingFace 路径的映射
        model_dir: 本地模型目录
        allow_remote: 是否允许回退到远程下载（离线环境设为 False）
    
    Returns:
        解析后的模型路径（本地路径或 HuggingFace 路径）
    
    Raises:
        ValueError: 模型名称不在映射表中
        FileNotFoundError: 本地模型不存在且不允许远程下载
    """
    if model_name not in model_path_map:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(model_path_map.keys())}")
    
    hf_path = model_path_map[model_name]
    
    # 尝试本地路径
    if model_dir is not None:
        local_path = resolve_local_model_path(model_dir, hf_path)
        if os.path.exists(local_path):
            logger.info(f"Using local model: {local_path}")
            return local_path
    
    # 本地不存在，检查是否允许远程下载
    if not allow_remote:
        raise FileNotFoundError(
            f"Local model not found: {os.path.join('.', model_dir or '', hf_path)}, "
            f"remote download disabled (allow_remote=False)"
        )
    
    logger.warning(f"Local model not found, falling back to HuggingFace: {hf_path}")
    return hf_path


def setup_hf_mirror():
    """
    设置 HuggingFace 镜像（单次初始化，避免重复设置）。
    
    注意：此函数仅适用于单进程场景，多进程场景下 _hf_mirror_set 变量不共享。
    """
    global _hf_mirror_set
    if _hf_mirror_set:
        return
    
    hf_endpoint = config.HF_ENDPOINT
    if hf_endpoint:
        os.environ["HF_ENDPOINT"] = hf_endpoint
        logger.info(f"Using HuggingFace mirror: {hf_endpoint}")
    _hf_mirror_set = True
