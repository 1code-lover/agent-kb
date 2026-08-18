"""模型本地目录路径解析工具。"""

from __future__ import annotations

import os


def resolve_local_model_path(model_dir: str | None, model_path: str) -> str | None:
    """拼接本地模型路径，兼容相对开发目录和 packaged 绝对目录。"""
    if model_dir is None:
        return None

    normalized_parts = [part for part in str(model_path).replace("\\", "/").split("/") if part]
    if os.path.isabs(model_dir):
        return os.path.join(model_dir, *normalized_parts)
    return os.path.join(".", model_dir, *normalized_parts)
