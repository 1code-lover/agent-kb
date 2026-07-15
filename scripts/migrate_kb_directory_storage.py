"""将 data 根目录旧文件迁移到 data/{kb_id}/。

本脚本只移动原始文件，不修改 storage/ 向量索引；旧索引中的
metadata/file_path/kb_id 一致性需要通过重导或重建索引另行处理。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def discover_root_files(source: str | Path) -> list[Path]:
    """只发现 data/ 根目录直属文件，不递归进入 data/{kb_id}/。"""
    source_path = Path(source).resolve()
    if not source_path.exists():
        return []
    return sorted(path for path in source_path.iterdir() if path.is_file())


def dry_run(source: str | Path, target_kb: str = "default") -> dict[str, Any]:
    """生成迁移计划，不改动文件系统。"""
    source_path = Path(source).resolve()
    items = []
    for file_path in discover_root_files(source_path):
        items.append(
            {
                "source_path": str(file_path),
                "target_path": str((source_path / target_kb / file_path.name).resolve()),
                "size": file_path.stat().st_size,
                "target_kb": target_kb,
            }
        )
    return {
        "mode": "dry-run",
        "source": str(source_path),
        "target_kb": target_kb,
        "items": items,
        "note": "dry-run 只计划原始文件迁移，不修改 storage/ 索引或 metadata。",
    }


def apply(source: str | Path, target_kb: str = "default", backup_root: str | Path = "backups/kb-directory-storage") -> Path:
    """执行迁移，备份源文件、校验 SHA256 并写入 manifest。"""
    source_path = Path(source).resolve()
    backup_dir = Path(backup_root).resolve() / _timestamp()
    backup_dir.mkdir(parents=True, exist_ok=False)
    target_dir = source_path / target_kb
    target_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for file_path in discover_root_files(source_path):
        target_path = (target_dir / file_path.name).resolve()
        backup_path = (backup_dir / file_path.name).resolve()
        if target_path.exists():
            raise FileExistsError(f"目标文件已存在: {target_path}")

        before = sha256_file(file_path)
        shutil.copy2(file_path, backup_path)
        if sha256_file(backup_path) != before:
            raise ValueError(f"备份 SHA256 不一致: {file_path}")
        shutil.move(str(file_path), str(target_path))
        after = sha256_file(target_path)
        if after != before:
            raise ValueError(f"迁移后 SHA256 不一致: {target_path}")
        items.append(
            {
                "source_path": str(file_path),
                "target_path": str(target_path),
                "backup_path": str(backup_path),
                "sha256_before": before,
                "sha256_after": after,
                "size": target_path.stat().st_size,
                "migrated_at": datetime.now(timezone.utc).isoformat(),
                "target_kb": target_kb,
            }
        )

    manifest = {
        "version": 1,
        "mode": "apply",
        "source": str(source_path),
        "target_kb": target_kb,
        "items": items,
        "note": "apply 只迁移原始文件，不修改 storage/ 向量索引，也不更新旧节点 file_path 或 kb_id metadata。",
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def verify_manifest(manifest: str | Path) -> bool:
    """按 manifest 校验目标文件 SHA256。"""
    manifest_path = Path(manifest).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in data.get("items", []):
        target_path = Path(item["target_path"])
        if not target_path.exists():
            raise FileNotFoundError(f"目标文件不存在: {target_path}")
        actual = sha256_file(target_path)
        if actual != item.get("sha256_before") or actual != item.get("sha256_after"):
            raise ValueError(f"SHA256 校验失败: {target_path}")
    return True


def rollback(manifest: str | Path) -> bool:
    """按 manifest 从备份恢复源文件，并删除迁移后的目标文件。"""
    manifest_path = Path(manifest).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in data.get("items", []):
        source_path = Path(item["source_path"])
        target_path = Path(item["target_path"])
        backup_path = Path(item["backup_path"])
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")
        source_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, source_path)
        if sha256_file(source_path) != item.get("sha256_before"):
            raise ValueError(f"恢复后 SHA256 不一致: {source_path}")
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="将 data/ 根目录旧文件迁移到 data/{kb_id}/")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    parser.add_argument("--source", default="data")
    parser.add_argument("--target-kb", default="default")
    parser.add_argument("--backup-dir", default="backups/kb-directory-storage")
    parser.add_argument("--manifest")
    args = parser.parse_args()

    if args.dry_run:
        print(json.dumps(dry_run(args.source, args.target_kb), ensure_ascii=False, indent=2))
    elif args.apply:
        manifest_path = apply(args.source, args.target_kb, args.backup_dir)
        print(f"manifest: {manifest_path}")
        print("迁移仅移动原始文件，不修改索引 metadata/file_path/kb_id。")
    elif args.verify:
        if not args.manifest:
            raise SystemExit("--verify 需要 --manifest")
        verify_manifest(args.manifest)
        print("manifest 校验通过")
    elif args.rollback:
        if not args.manifest:
            raise SystemExit("--rollback 需要 --manifest")
        rollback(args.manifest)
        print("rollback 完成")


if __name__ == "__main__":
    main()
