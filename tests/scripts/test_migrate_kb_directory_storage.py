"""data 根目录旧文件迁移脚本测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import migrate_kb_directory_storage as migrate


def test_dry_run_lists_only_root_files(tmp_path: Path) -> None:
    source = tmp_path / "data"
    source.mkdir()
    (source / "legacy.txt").write_text("legacy", encoding="utf-8")
    (source / "kb-a").mkdir()
    (source / "kb-a" / "nested.txt").write_text("nested", encoding="utf-8")

    plan = migrate.dry_run(source, "default")

    assert [item["source_path"] for item in plan["items"]] == [str((source / "legacy.txt").resolve())]
    assert not (source / "default").exists()


def test_apply_backs_up_moves_and_writes_manifest(tmp_path: Path) -> None:
    source = tmp_path / "data"
    backup_root = tmp_path / "backups"
    source.mkdir()
    old = source / "legacy.txt"
    old.write_text("legacy", encoding="utf-8")

    manifest_path = migrate.apply(source, "default", backup_root=backup_root)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = manifest["items"][0]
    assert not old.exists()
    assert (source / "default" / "legacy.txt").read_text(encoding="utf-8") == "legacy"
    assert Path(item["backup_path"]).read_text(encoding="utf-8") == "legacy"
    assert item["sha256_before"] == item["sha256_after"]
    assert manifest["note"].startswith("apply 只迁移原始文件")


def test_verify_manifest_detects_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "data"
    source.mkdir()
    old = source / "legacy.txt"
    old.write_text("legacy", encoding="utf-8")
    manifest_path = migrate.apply(source, "default", backup_root=tmp_path / "backups")
    (source / "default" / "legacy.txt").write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA256"):
        migrate.verify_manifest(manifest_path)


def test_rollback_restores_source_from_manifest(tmp_path: Path) -> None:
    source = tmp_path / "data"
    source.mkdir()
    old = source / "legacy.txt"
    old.write_text("legacy", encoding="utf-8")
    manifest_path = migrate.apply(source, "default", backup_root=tmp_path / "backups")

    migrate.rollback(manifest_path)

    assert (source / "legacy.txt").read_text(encoding="utf-8") == "legacy"
    assert not (source / "default" / "legacy.txt").exists()
