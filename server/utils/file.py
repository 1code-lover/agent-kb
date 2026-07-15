"""文件与知识库目录路径工具。

模块功能：
- 提供兼容旧代码的全局 data 目录获取能力。
- 校验知识库 ID，并解析 data/{kb_id}/ 的安全路径。
- 清洗上传文件名，防止路径穿越和越界写入。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from config import DATA_DIR
from server.kb_errors import KBValidationError

_KB_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def get_save_dir() -> str:
    """获取旧版全局上传保存目录。

    Returns:
        str: 当前工作目录下配置的 data 目录字符串路径。旧调用点仍依赖字符串返回。
    """
    return str(get_data_root())


def get_data_root() -> Path:
    """返回 data 根目录的绝对规范化路径。"""
    return (Path.cwd() / DATA_DIR).resolve()


def validate_kb_id(kb_id: str) -> str:
    """校验并返回规范化知识库 ID。

    kb_id 只能包含小写字母、数字和中划线，长度 1 到 64，且首尾必须是字母或数字。
    Windows 保留名无论大小写均禁止，避免在 Windows 文件系统上落盘失败。
    """
    if not isinstance(kb_id, str):
        raise KBValidationError("知识库 ID 必须是字符串")

    value = kb_id.strip()
    if value != kb_id:
        raise KBValidationError("知识库 ID 不能包含首尾空白字符")

    if not _KB_ID_PATTERN.fullmatch(value):
        raise KBValidationError(
            "知识库 ID 只能包含小写字母、数字和中划线，长度 1 到 64，且首尾必须是字母或数字"
        )

    if value.upper() in _WINDOWS_RESERVED_NAMES:
        raise KBValidationError(f"知识库 ID 不能使用 Windows 保留名: {value}")

    return value


def ensure_path_within(base: str | os.PathLike[str], target: str | os.PathLike[str]) -> Path:
    """确认目标路径位于 base 目录内，并返回目标的 resolved Path。"""
    base_path = Path(base).resolve()
    target_path = Path(target).resolve()
    try:
        target_path.relative_to(base_path)
    except ValueError as exc:
        raise KBValidationError(f"路径越界: {target_path} 不在 {base_path} 内") from exc
    return target_path


def get_kb_data_dir(kb_id: str, create: bool = False) -> Path:
    """返回 data/{kb_id} 的安全绝对路径。"""
    safe_kb_id = validate_kb_id(kb_id)
    data_root = get_data_root()
    kb_dir = ensure_path_within(data_root, data_root / safe_kb_id)
    if create:
        kb_dir.mkdir(parents=True, exist_ok=True)
    return kb_dir


def sanitize_filename(filename: str) -> str:
    """清洗上传文件名，防止路径穿越攻击。"""
    filename = os.path.basename(filename or "")
    filename = filename.replace("..", "").replace("/", "").replace("\\", "")
    if not filename or filename.startswith("."):
        filename = "uploaded_file"
    return filename


def save_uploaded_file(uploaded_file: Any, save_dir: str | os.PathLike[str]) -> Path:
    """保存上传文件到指定目录，并返回最终落盘路径。

    Args:
        uploaded_file: 需包含 name 和 getbuffer() 接口的上传文件对象。
        save_dir: 目标保存目录。

    Returns:
        Path: 保存后的安全路径。
    """
    save_path = Path(save_dir).resolve()
    save_path.mkdir(parents=True, exist_ok=True)

    safe_filename = sanitize_filename(uploaded_file.name)
    target = ensure_path_within(save_path, save_path / safe_filename)

    with target.open("wb") as f:
        f.write(uploaded_file.getbuffer())

    print(f"已保存: {target}")
    return target
