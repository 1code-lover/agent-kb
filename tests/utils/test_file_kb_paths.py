"""KB 目录路径工具测试。

本文件先定义多知识库目录化存储的路径安全契约：
1. kb_id 只能使用小写字母、数字和中划线，且首尾必须是字母或数字。
2. data/{kb_id}/ 必须解析为 data 根目录内的绝对路径。
3. 所有文件路径在落盘或删除前必须通过目录边界校验。
"""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.kb_errors import KBValidationError
from server.utils.file import (
    ensure_path_within,
    get_data_root,
    get_kb_data_dir,
    get_kb_storage_dir,
    get_save_dir,
    get_storage_root,
    sanitize_filename,
    save_uploaded_file,
    validate_kb_id,
)


def test_validate_kb_id_accepts_lowercase_digits_and_hyphen():
    """合法 kb_id 应保持原值返回。"""
    assert validate_kb_id("product-docs") == "product-docs"
    assert validate_kb_id("kb1") == "kb1"
    assert validate_kb_id("a") == "a"


@pytest.mark.parametrize(
    "kb_id",
    [
        "bad_id",
        "Bad",
        "-bad",
        "bad-",
        "../escape",
        "a/b",
        "a\\b",
        "a:b",
        ".",
        "..",
        "",
        "a" * 65,
    ],
)
def test_validate_kb_id_rejects_unsafe_values(kb_id):
    """非法 kb_id 必须被稳定异常阻断。"""
    with pytest.raises(KBValidationError):
        validate_kb_id(kb_id)


@pytest.mark.parametrize("kb_id", ["CON", "nul", "com1", "LPT9"])
def test_validate_kb_id_rejects_windows_reserved_names(kb_id):
    """Windows 保留名即使大小写不同也不能作为目录名。"""
    with pytest.raises(KBValidationError):
        validate_kb_id(kb_id)


def test_get_data_root_uses_configured_data_dir(tmp_path, monkeypatch):
    """data 根目录应基于当前工作目录解析为绝对路径。"""
    monkeypatch.chdir(tmp_path)

    assert get_data_root() == (tmp_path / "data").resolve()


def test_get_kb_data_dir_resolves_inside_data_root(tmp_path, monkeypatch):
    """KB 数据目录应解析到 data/{kb_id}。"""
    monkeypatch.chdir(tmp_path)

    kb_dir = get_kb_data_dir("kb-a")

    assert kb_dir == (tmp_path / "data" / "kb-a").resolve()
    assert not kb_dir.exists()


def test_get_kb_data_dir_can_create_directory(tmp_path, monkeypatch):
    """create=True 时应创建 KB 目录。"""
    monkeypatch.chdir(tmp_path)

    kb_dir = get_kb_data_dir("kb-a", create=True)

    assert kb_dir.is_dir()
    assert kb_dir == (tmp_path / "data" / "kb-a").resolve()


def test_ensure_path_within_accepts_child_path(tmp_path):
    """目标路径位于 base 内时应返回规范化路径。"""
    base = tmp_path / "data" / "kb-a"
    target = base / "file.txt"

    assert ensure_path_within(base, target) == target.resolve()


def test_ensure_path_within_rejects_path_traversal(tmp_path):
    """目录穿越后落到其他 KB 时必须失败。"""
    base = tmp_path / "data" / "kb-a"
    target = base / ".." / "kb-b" / "file.txt"

    with pytest.raises(KBValidationError):
        ensure_path_within(base, target)


def test_ensure_path_within_rejects_same_prefix_sibling(tmp_path):
    """不能用字符串前缀误判 data/kb-a2 为 data/kb-a 子目录。"""
    base = tmp_path / "data" / "kb-a"
    target = tmp_path / "data" / "kb-a2" / "file.txt"

    with pytest.raises(KBValidationError):
        ensure_path_within(base, target)


def test_get_save_dir_returns_data_root_string(tmp_path, monkeypatch):
    """默认上传目录应与 data 根目录保持一致。"""
    monkeypatch.chdir(tmp_path)

    assert get_save_dir() == str((tmp_path / "data").resolve())


def test_validate_kb_id_rejects_non_string_and_surrounding_spaces():
    """非字符串和带首尾空格的 kb_id 都必须被拒绝。"""
    with pytest.raises(KBValidationError, match="字符串"):
        validate_kb_id(None)

    with pytest.raises(KBValidationError, match="前后空格"):
        validate_kb_id(" kb-a ")


def test_get_kb_storage_dir_uses_storage_root_for_default_kb(tmp_path, monkeypatch):
    """default 知识库应继续沿用共享 storage 根目录。"""
    monkeypatch.chdir(tmp_path)

    kb_dir = get_kb_storage_dir("default", create=True)

    assert get_storage_root() == (tmp_path / "storage").resolve()
    assert kb_dir == (tmp_path / "storage").resolve()
    assert kb_dir.is_dir()


def test_get_kb_storage_dir_creates_namespaced_directory_for_non_default_kb(tmp_path, monkeypatch):
    """非 default 知识库应落在 storage/kbs/{kb_id} 下。"""
    monkeypatch.chdir(tmp_path)

    kb_dir = get_kb_storage_dir("kb-a", create=True)

    assert kb_dir == (tmp_path / "storage" / "kbs" / "kb-a").resolve()
    assert kb_dir.is_dir()


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("../note.md", "note.md"),
        (r"..\draft.txt", "draft.txt"),
        (".env", "uploaded_file"),
        ("", "uploaded_file"),
    ],
)
def test_sanitize_filename_handles_traversal_hidden_and_empty_names(raw_name, expected):
    """文件名清洗应阻断目录穿越、隐藏文件和空文件名。"""
    assert sanitize_filename(raw_name) == expected


def test_save_uploaded_file_writes_bytes_with_sanitized_name(tmp_path):
    """保存上传文件时应使用清洗后的文件名并写入原始字节。"""
    uploaded = SimpleNamespace(name="../unsafe.txt", getbuffer=lambda: b"hello")

    target = save_uploaded_file(uploaded, tmp_path / "uploads")

    assert target == (tmp_path / "uploads" / "unsafe.txt").resolve()
    assert target.read_bytes() == b"hello"


def test_save_uploaded_file_accepts_fastapi_uploadfile_shape(tmp_path):
    """兼容 FastAPI UploadFile 风格对象：优先 filename，其次 file.read。"""
    uploaded = SimpleNamespace(filename="../scan.pdf", file=BytesIO(b"%PDF-1.7 mock"))

    target = save_uploaded_file(uploaded, tmp_path / "uploads")

    assert target == (tmp_path / "uploads" / "scan.pdf").resolve()
    assert target.read_bytes() == b"%PDF-1.7 mock"
