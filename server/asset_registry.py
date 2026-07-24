"""知识库 Asset Registry。"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from server.utils.file import validate_kb_id


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


class KBAssetRegistry:
    """按知识库拆分持久化的资产注册表。"""

    def __init__(self, base_dir: Path | None = None):
        self._base_dir = base_dir or Path("storage/kb_assets")
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

    def _merge_assets(
        self,
        *,
        kb_id: str,
        existing_items: Iterable[dict[str, Any]],
        incoming_items: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        safe_kb_id = validate_kb_id(kb_id)
        now = _utc_now_iso()
        by_id: dict[str, dict[str, Any]] = {}

        for item in existing_items:
            asset_id = item.get("asset_id")
            if isinstance(asset_id, str) and asset_id:
                by_id[asset_id] = dict(item)

        for item in incoming_items:
            asset_id = item.get("asset_id")
            if not isinstance(asset_id, str) or not asset_id:
                continue
            existing = by_id.get(asset_id)
            record = dict(existing or {})
            record.update(item)
            record["kb_id"] = safe_kb_id
            record["created_at"] = record.get("created_at") or (existing or {}).get("created_at") or now
            record["updated_at"] = now
            by_id[asset_id] = record

        return sorted(
            by_id.values(),
            key=lambda item: (
                item.get("relative_path") or "",
                item.get("source_doc_relative_path") or "",
                item.get("asset_role") or "",
                item.get("asset_id") or "",
            ),
        )

    def list_assets(self, kb_id: str) -> list[dict[str, Any]]:
        """列出指定知识库的全部资产。"""
        with self._lock:
            return self._read_unlocked(kb_id)

    def get_asset(self, kb_id: str, asset_id: str) -> dict[str, Any] | None:
        """按资产 ID 读取单个资产。"""
        with self._lock:
            for item in self._read_unlocked(kb_id):
                if item.get("asset_id") == asset_id:
                    return dict(item)
        return None

    def upsert_assets(self, kb_id: str, assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """按 asset_id upsert 资产记录。"""
        with self._lock:
            merged = self._merge_assets(kb_id=kb_id, existing_items=self._read_unlocked(kb_id), incoming_items=assets)
            self._write_unlocked(kb_id, merged)
            return merged

    def replace_embedded_assets(
        self,
        kb_id: str,
        source_doc_relative_paths: Iterable[str],
        assets: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """按 source_doc_relative_path 替换 embedded 资产，避免文档重导入后残留旧记录。"""
        path_set = {
            path.strip()
            for path in source_doc_relative_paths
            if isinstance(path, str) and path.strip()
        }
        with self._lock:
            existing = self._read_unlocked(kb_id)
            retained = [
                item
                for item in existing
                if not (
                    item.get("asset_role") == "embedded"
                    and item.get("source_doc_relative_path") in path_set
                )
            ]
            merged = self._merge_assets(kb_id=kb_id, existing_items=retained, incoming_items=assets)
            self._write_unlocked(kb_id, merged)
            return merged

    def delete_kb(self, kb_id: str) -> None:
        """删除指定知识库的资产注册表文件。"""
        with self._lock:
            path = self._storage_path(kb_id)
            if path.exists():
                path.unlink()
