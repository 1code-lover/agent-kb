"""文件与知识库目录工具。

职责：
- 统一解析 data / storage 根目录；
- 提供按知识库划分的数据目录与存储目录；
- 提供上传文件保存与路径越界校验能力。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from config import DATA_DIR, STORAGE_DIR
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
    """返回默认上传保存目录字符串。"""
    return str(get_data_root())


def get_data_root() -> Path:
    """返回 data 根目录的绝对路径。"""
    return (Path.cwd() / DATA_DIR).resolve()


def get_storage_root() -> Path:
    """返回 storage 根目录的绝对路径。"""
    return (Path.cwd() / STORAGE_DIR).resolve()


def validate_kb_id(kb_id: str) -> str:
    """校验知识库 ID。

    约束：
    - 仅允许小写字母、数字和中划线；
    - 长度 1 到 64；
    - 不能包含首尾空格；
    - 不能使用 Windows 保留文件名。
    """
    if not isinstance(kb_id, str):
        raise KBValidationError("知识库 ID 必须是字符串")

    value = kb_id.strip()
    if value != kb_id:
        raise KBValidationError("知识库 ID 不能包含前后空格")

    if not _KB_ID_PATTERN.fullmatch(value):
        raise KBValidationError("知识库 ID 仅允许小写字母、数字和中划线，长度为 1 到 64")

    if value.upper() in _WINDOWS_RESERVED_NAMES:
        raise KBValidationError(f"知识库 ID 不能使用 Windows 保留名称: {value}")

    return value


def ensure_path_within(base: str | os.PathLike[str], target: str | os.PathLike[str]) -> Path:
    """确保目标路径位于指定基目录内，并返回解析后的绝对路径。"""
    base_path = Path(base).resolve()
    target_path = Path(target).resolve()
    try:
        target_path.relative_to(base_path)
    except ValueError as exc:
        raise KBValidationError(f"路径越界: {target_path} 不在 {base_path} 下") from exc
    return target_path


def get_kb_data_dir(kb_id: str, create: bool = False) -> Path:
    """返回 data/{kb_id} 目录。"""
    safe_kb_id = validate_kb_id(kb_id)
    data_root = get_data_root()
    kb_dir = ensure_path_within(data_root, data_root / safe_kb_id)
    if create:
        kb_dir.mkdir(parents=True, exist_ok=True)
    return kb_dir


def get_kb_storage_dir(kb_id: str, create: bool = False) -> Path:
    """返回指定知识库的索引存储目录。

    兼容策略：
    - default 知识库沿用历史 storage/ 根目录；
    - 其他知识库存放在 storage/kbs/{kb_id}/。
    """
    safe_kb_id = validate_kb_id(kb_id)
    storage_root = get_storage_root()
    if safe_kb_id == "default":
        kb_dir = storage_root
    else:
        kbs_root = ensure_path_within(storage_root, storage_root / "kbs")
        kb_dir = ensure_path_within(kbs_root, kbs_root / safe_kb_id)
    if create:
        kb_dir.mkdir(parents=True, exist_ok=True)
    return kb_dir


def sanitize_filename(filename: str) -> str:
    """清洗上传文件名，避免目录穿越与隐藏文件名。"""
    cleaned = os.path.basename(filename or "")
    cleaned = cleaned.replace("..", "").replace("/", "").replace("\\", "")
    if not cleaned or cleaned.startswith("."):
        cleaned = "uploaded_file"
    return cleaned


def _resolve_uploaded_filename(uploaded_file: Any) -> str:
    """兼容不同上传对象的文件名字段。"""
    raw_name = getattr(uploaded_file, "name", None) or getattr(uploaded_file, "filename", None)
    return sanitize_filename(raw_name)


def _read_uploaded_bytes(uploaded_file: Any) -> bytes:
    """兼容 BytesIO、FastAPI UploadFile 等上传对象的读取方式。"""
    readers = [
        getattr(uploaded_file, "getbuffer", None),
        getattr(uploaded_file, "read", None),
        getattr(getattr(uploaded_file, "file", None), "read", None),
    ]
    for reader in readers:
        if not callable(reader):
            continue
        content = reader()
        if isinstance(content, str):
            return content.encode("utf-8")
        if content is None:
            return b""
        return bytes(content)
    raise KBValidationError("上传文件对象不支持读取")


def save_uploaded_file(uploaded_file: Any, save_dir: str | os.PathLike[str]) -> Path:
    """将上传文件安全保存到指定目录。"""
    save_path = Path(save_dir).resolve()
    save_path.mkdir(parents=True, exist_ok=True)

    safe_filename = _resolve_uploaded_filename(uploaded_file)
    target = ensure_path_within(save_path, save_path / safe_filename)

    with target.open("wb") as handle:
        handle.write(_read_uploaded_bytes(uploaded_file))

    print(f"文件已保存: {target}")
    return target
