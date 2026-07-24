"""知识库 Folder Registry。"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.kb_errors import KBValidationError
from server.utils.file import get_kb_data_dir, validate_kb_id

_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def normalize_relative_path(relative_path: str) -> str:
    """规范化知识库内相对路径，拒绝绝对路径与越界片段。"""
    if not isinstance(relative_path, str):
        raise KBValidationError("relative_path 必须是字符串")

    raw = relative_path.strip()
    if not raw:
        raise KBValidationError("relative_path 不能为空")
    if raw.startswith(("/", "\\")) or _WINDOWS_DRIVE_PATTERN.match(raw):
        raise KBValidationError(f"relative_path 不能是绝对路径: {relative_path}")

    parts: list[str] = []
    for part in raw.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise KBValidationError(f"relative_path 不能越界: {relative_path}")
        parts.append(part)

    if not parts:
        raise KBValidationError("relative_path 不能为空")
    return "/".join(parts)


def folder_path_from_relative_path(relative_path: str | None) -> str | None:
    """从文档相对路径推导 folder_path。"""
    if relative_path is None:
        return None
    normalized = normalize_relative_path(relative_path)
    parent = Path(normalized).parent.as_posix()
    return "" if parent == "." else parent


def resolve_relative_path_from_file_path(file_path: str | None, kb_id: str) -> str | None:
    """根据落盘绝对路径反推知识库内相对路径。"""
    if not file_path:
        return None

    path = Path(file_path).resolve()
    kb_dir = get_kb_data_dir(kb_id, create=False)
    try:
        return path.relative_to(kb_dir).as_posix()
    except ValueError:
        return None


def resolve_relative_path_from_metadata(metadata: dict[str, Any], kb_id: str) -> str | None:
    """优先读取 metadata 中的 relative_path，否则回退到 file_path 反推。"""
    relative_path = metadata.get("relative_path")
    if relative_path:
        return normalize_relative_path(relative_path)
    return resolve_relative_path_from_file_path(metadata.get("file_path"), kb_id)


class KBFolderRegistry:
    """按知识库拆分持久化的 Folder 最小注册表。"""

    def __init__(self, base_dir: Path | None = None):
        self._base_dir = base_dir or Path("storage/kb_folders")
        self._lock = threading.RLock()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _storage_path(self, kb_id: str) -> Path:
        safe_kb_id = validate_kb_id(kb_id)
        return self._base_dir / f"{safe_kb_id}.json"

    def _read_unlocked(self, kb_id: str) -> list[dict[str, Any]]:
        path = self._storage_path(kb_id)
        if not path.exists():
            return []
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw or "[]")

    def _write_unlocked(self, kb_id: str, data: list[dict[str, Any]]) -> None:
        path = self._storage_path(kb_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            last_exc: PermissionError | None = None
            for attempt in range(5):
                try:
                    os.replace(tmp_path, path)
                    last_exc = None
                    break
                except PermissionError as exc:
                    last_exc = exc
                    time.sleep(0.02 * (attempt + 1))
            if last_exc is not None:
                raise last_exc
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def list_folders(self, kb_id: str) -> list[dict[str, Any]]:
        """列出指定知识库的 folder 节点。"""
        with self._lock:
            return self._read_unlocked(kb_id)

    def ensure_folder_chain(self, kb_id: str, relative_path: str, source_root: str | None = None) -> list[dict[str, Any]]:
        """根据文档相对路径补齐父级 folder 链。"""
        normalized = normalize_relative_path(relative_path)
        folder_paths = self._build_folder_paths(normalized)
        now = _utc_now_iso()

        with self._lock:
            items = self._read_unlocked(kb_id)
            by_path = {item["path"]: item for item in items}
            changed = False
            for folder_path in folder_paths:
                record = by_path.get(folder_path)
                if record is None:
                    by_path[folder_path] = self._build_folder_record(kb_id, folder_path, now, source_root=source_root)
                    changed = True
                else:
                    record["updated_at"] = now
                    if source_root is not None:
                        record["source_root"] = source_root
                    changed = True
            ordered = self._sort_records(by_path.values())
            if changed:
                self._write_unlocked(kb_id, ordered)
            return [by_path[path] for path in folder_paths]

    def replace_from_relative_paths(self, kb_id: str, relative_paths: list[str], source_root: str | None = None) -> list[dict[str, Any]]:
        """根据当前文档集合重建指定知识库的 folder registry。"""
        now = _utc_now_iso()
        by_path: dict[str, dict[str, Any]] = {}
        for relative_path in relative_paths:
            normalized = normalize_relative_path(relative_path)
            for folder_path in self._build_folder_paths(normalized):
                by_path.setdefault(
                    folder_path,
                    self._build_folder_record(kb_id, folder_path, now, source_root=source_root),
                )

        ordered = self._sort_records(by_path.values())
        with self._lock:
            self._write_unlocked(kb_id, ordered)
        return ordered

    def _build_folder_paths(self, relative_path: str) -> list[str]:
        parts = Path(relative_path).parts[:-1]
        current: list[str] = []
        folder_paths: list[str] = []
        for part in parts:
            current.append(part)
            folder_paths.append("/".join(current))
        return folder_paths

    def _build_folder_record(
        self,
        kb_id: str,
        folder_path: str,
        now: str,
        *,
        source_root: str | None = None,
    ) -> dict[str, Any]:
        parent_path = Path(folder_path).parent.as_posix()
        parent_path = "" if parent_path == "." else parent_path
        parent_folder_id = None if not parent_path else self._folder_id(kb_id, parent_path)
        return {
            "folder_id": self._folder_id(kb_id, folder_path),
            "kb_id": validate_kb_id(kb_id),
            "parent_folder_id": parent_folder_id,
            "name": Path(folder_path).name,
            "path": folder_path,
            "depth": len(Path(folder_path).parts),
            "source_root": source_root,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

    def _folder_id(self, kb_id: str, folder_path: str) -> str:
        return f"{validate_kb_id(kb_id)}::{folder_path}"

    def _sort_records(self, items: Any) -> list[dict[str, Any]]:
        return sorted(items, key=lambda item: (item["depth"], item["path"]))
