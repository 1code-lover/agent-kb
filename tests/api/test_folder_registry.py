"""Folder Registry 最小能力测试。"""

from __future__ import annotations

from pathlib import Path

from server.folder_registry import KBFolderRegistry


def test_replace_from_relative_paths_writes_isolated_registry_per_kb(tmp_path: Path) -> None:
    """不同知识库应写入各自独立的 folder registry 文件。"""
    registry = KBFolderRegistry(base_dir=tmp_path / "storage" / "kb_folders")

    registry.replace_from_relative_paths("kb-a", ["design/specs/a.md", "design/roadmap.md"])
    registry.replace_from_relative_paths("kb-b", ["ops/runbook.md"])

    assert (tmp_path / "storage" / "kb_folders" / "kb-a.json").is_file()
    assert (tmp_path / "storage" / "kb_folders" / "kb-b.json").is_file()
    assert [item["path"] for item in registry.list_folders("kb-a")] == ["design", "design/specs"]
    assert [item["path"] for item in registry.list_folders("kb-b")] == ["ops"]


def test_ensure_folder_chain_normalizes_relative_path_and_parent_chain(tmp_path: Path) -> None:
    """Windows 风格相对路径也应被规范化为稳定 folder 链。"""
    registry = KBFolderRegistry(base_dir=tmp_path / "storage" / "kb_folders")

    created = registry.ensure_folder_chain("kb-a", r"notes\daily\2026-07-24.md")

    assert [item["path"] for item in created] == ["notes", "notes/daily"]
    assert created[0]["parent_folder_id"] is None
    assert created[1]["parent_folder_id"] == created[0]["folder_id"]


def test_replace_from_relative_paths_prunes_stale_folders(tmp_path: Path) -> None:
    """重建 folder registry 时应移除已不存在文档留下的旧目录。"""
    registry = KBFolderRegistry(base_dir=tmp_path / "storage" / "kb_folders")

    registry.replace_from_relative_paths("kb-a", ["design/specs/a.md"])
    registry.replace_from_relative_paths("kb-a", ["ops/runbook.md"])

    assert [item["path"] for item in registry.list_folders("kb-a")] == ["ops"]
