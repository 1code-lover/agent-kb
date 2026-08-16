"""模型本地目录路径解析工具。"""

from __future__ import annotations

import os


def resolve_local_model_path(model_dir: str | None, model_path: str) -> str | None:
    """拼接本地模型路径，兼容相对开发目录和 packaged 绝对目录。"""
    if model_dir is None:
        return None
    if os.path.isabs(model_dir):
        return os.path.join(model_dir, model_path)
    return os.path.join(".", model_dir, model_path)
