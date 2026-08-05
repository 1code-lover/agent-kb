"""Folder Registry 分支补充测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.folder_registry import (
    KBFolderRegistry,
    folder_path_from_relative_path,
    normalize_relative_path,
    resolve_relative_path_from_file_path,
    resolve_relative_path_from_metadata,
)
from server.kb_errors import KBValidationError


@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        "   ",
        "/absolute/path.md",
        r"C:\absolute\path.md",
        "../escape.md",
        "a/../../escape.md",
    ],
)
def test_normalize_relative_path_rejects_invalid_inputs(relative_path: str) -> None:
    """相对路径规范化应拒绝空值、绝对路径与越界片段。"""
    with pytest.raises(KBValidationError):
        normalize_relative_path(relative_path)


def test_folder_path_from_relative_path_returns_root_or_parent() -> None:
    """folder_path 推导应在根目录文件和子目录文件之间保持稳定。"""
    assert folder_path_from_relative_path("readme.md") == ""
    assert folder_path_from_relative_path(r"design\specs\api.md") == "design/specs"


def test_resolve_relative_path_from_file_path_returns_none_for_outside_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """绝对路径不在目标知识库目录下时应返回 None。"""
    kb_dir = tmp_path / "data" / "kb-a"
    kb_dir.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside" / "a.md"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert resolve_relative_path_from_file_path(str(outside), "kb-a") is None


def test_resolve_relative_path_from_file_path_returns_normalized_relative_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """落盘路径在知识库目录内时应被反推出稳定相对路径。"""
    kb_dir = tmp_path / "data" / "kb-a" / "design"
    kb_dir.mkdir(parents=True, exist_ok=True)
    doc = kb_dir / "spec.md"
    doc.write_text("spec", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert resolve_relative_path_from_file_path(str(doc), "kb-a") == "design/spec.md"


def test_resolve_relative_path_from_metadata_prefers_metadata_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """metadata 中已有 relative_path 时应优先使用并规范化。"""
    monkeypatch.chdir(tmp_path)
    metadata = {
        "relative_path": r"notes\daily\2026-07-30.md",
        "file_path": str(tmp_path / "data" / "kb-a" / "ignored.md"),
    }

    assert resolve_relative_path_from_metadata(metadata, "kb-a") == "notes/daily/2026-07-30.md"


def test_resolve_relative_path_from_metadata_falls_back_to_file_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """metadata 缺少 relative_path 时应回退到 file_path 反推。"""
    doc = tmp_path / "data" / "kb-a" / "ops" / "runbook.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("runbook", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert resolve_relative_path_from_metadata({"file_path": str(doc)}, "kb-a") == "ops/runbook.md"


def test_ensure_folder_chain_updates_existing_source_root(tmp_path: Path) -> None:
    """重复补链时应刷新既有目录节点的 source_root 与更新时间。"""
    registry = KBFolderRegistry(base_dir=tmp_path / "storage" / "kb_folders")

    first = registry.ensure_folder_chain("kb-a", "design/specs/api.md", source_root="batch-a")
    second = registry.ensure_folder_chain("kb-a", "design/specs/guide.md", source_root="batch-b")

    items = {item["path"]: item for item in registry.list_folders("kb-a")}
    assert [item["path"] for item in first] == ["design", "design/specs"]
    assert [item["path"] for item in second] == ["design", "design/specs"]
    assert items["design"]["source_root"] == "batch-b"
    assert items["design/specs"]["source_root"] == "batch-b"
    assert items["design"]["updated_at"] >= items["design"]["created_at"]


def test_replace_from_relative_paths_with_empty_input_clears_registry(tmp_path: Path) -> None:
    """用空文档集合重建时应清空目标知识库的目录注册表。"""
    registry = KBFolderRegistry(base_dir=tmp_path / "storage" / "kb_folders")

    registry.replace_from_relative_paths("kb-a", ["design/specs/a.md", "ops/runbook.md"])
    replaced = registry.replace_from_relative_paths("kb-a", [])

    assert replaced == []
    assert registry.list_folders("kb-a") == []
